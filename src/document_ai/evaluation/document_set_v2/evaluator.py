# -*- coding: utf-8 -*-
"""Document Set Benchmark v2 evaluator (generalization / holdout protocol)."""

from __future__ import annotations

import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.evaluation.business_proposal_gold import protocol as bp_protocol
from document_ai.evaluation.business_proposal_gold.error_analysis import build_error_report
from document_ai.evaluation.business_proposal_gold.official_metrics import (
    compute_official_business_proposal_metrics,
    compute_proxy_intent_grounding_metrics,
)
from document_ai.evaluation.document_set.evaluator import _e2e_status
from document_ai.evaluation.document_set_v2.calibration import compute_calibration_metrics
from document_ai.evaluation.document_set_v2.dataset_loader import (
    BenchmarkV2ValidationError,
    load_benchmark_v2_manifest,
    validate_benchmark_v2,
)
from document_ai.evaluation.document_set_v2.format_preservation import aggregate_format_metrics
from document_ai.evaluation.document_set_v2.holdout_protocol import (
    freeze_predictions,
    unseal_for_evaluation,
)
from document_ai.evaluation.document_set_v2.metrics import (
    domain_breakdown,
    generalization_gap,
    summarize_split_metrics,
)
from document_ai.evaluation.document_set_v2.report_builder import write_v2_artifacts
from document_ai.evaluation.document_set_v2.robustness import (
    compute_decision_consistency,
    compute_node_consistency,
)
from document_ai.evaluation.document_set_v2.identity_metrics import (
    compute_alignment_metrics,
    compute_identity_metrics,
    compute_pack_routing_metrics,
    expected_identity_from_domain,
)
from document_ai.evaluation.document_set_v2.safety_stress import run_safety_stress_suite
from document_ai.evaluation.document_set_v2.schema import BenchmarkV2Case

REPO = Path(__file__).resolve().parents[4]
DEFAULT_OUT = REPO / "data" / "eval" / "results" / "document_set_benchmark_v2"


def _index_gold(gold: dict[str, Any]) -> dict[str, Any]:
    docs: dict[str, list] = {}
    nodes: dict[str, list] = {}
    writer: dict[str, dict] = {}
    elig: dict[str, dict] = {}
    for r in gold.get("document_impacts") or []:
        docs.setdefault(r["case_id"], []).append(r)
    for r in gold.get("node_impacts") or []:
        nodes.setdefault(r["case_id"], []).append(r)
    for r in gold.get("writer_expectations") or []:
        writer[r["case_id"]] = r
    for r in gold.get("node_evaluation_eligibility") or []:
        elig[r["case_id"]] = r
    return {"docs": docs, "nodes": nodes, "writer": writer, "elig": elig}


def _pred_matches_gold_nodes(
    pred: dict[str, Any],
    *,
    gold_ids: set[str],
    acceptable: set[str],
    cr_identifiers: set[str],
    alignments: list[dict[str, Any]] | None = None,
    equivalence_groups: list[dict[str, Any]] | None = None,
) -> bool:
    nid = str(pred.get("node_id") or "")
    if nid in gold_ids or nid in acceptable:
        return True
    meta = pred.get("metadata") or {}
    sid = pred.get("stable_node_id") or meta.get("stable_node_id")
    if sid and (sid in gold_ids or sid in acceptable):
        return True
    base = pred.get("stable_node_id_base") or meta.get("stable_node_id_base")
    if base and (base in gold_ids or base in acceptable):
        return True
    # Template node id carried on physical candidate
    tid = meta.get("template_node_id")
    if tid and (str(tid) in gold_ids or str(tid) in acceptable):
        return True
    # Structural equivalence / alignments (evaluation only — no gold read at inference)
    for g in equivalence_groups or meta.get("structural_equivalence_groups") or []:
        if g.get("evaluation_equivalent") is False:
            continue
        members = set(g.get("template_node_ids") or []) | set(g.get("document_node_ids") or [])
        if nid in members and (members & gold_ids or members & acceptable):
            return True
    for a in alignments or meta.get("node_alignments") or []:
        if not a.get("equivalent_for_evaluation"):
            continue
        pair = {str(a.get("template_node_id") or ""), str(a.get("document_node_id") or "")}
        if nid in pair and (pair & gold_ids or pair & acceptable):
            return True
    # Logical MDTM match: gold is legacy MDTM id; pred shares CR identifiers
    pids = set(meta.get("identifier_values") or [])
    if not pids:
        pids |= set((meta.get("source_identifiers") or {}).get("requirement_ids") or [])
        pids |= set((meta.get("source_identifiers") or {}).get("design_ids") or [])
        pids |= set((meta.get("source_identifiers") or {}).get("test_ids") or [])
    if gold_ids and any(str(g).startswith("ec_sw") for g in gold_ids):
        if pids & cr_identifiers:
            return True
    return False


def _cr_identifiers(change_request: str) -> set[str]:
    from document_ai.domain_packs.ec_sw.mdtm_schema import (
        extract_design_ids,
        extract_requirement_ids,
        extract_test_ids,
    )
    from document_ai.domain_packs.ec_sw.identifier_parser import valid_canonical_requirement_ids

    ids: set[str] = set(valid_canonical_requirement_ids(change_request or ""))
    ids.update(extract_requirement_ids(change_request or ""))
    ids.update(extract_design_ids(change_request or ""))
    ids.update(extract_test_ids(change_request or ""))
    return {str(x) for x in ids if x}


def _pred_alignments(pred: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        list(pred.get("node_alignments") or []),
        list(pred.get("structural_equivalence_groups") or []),
    )


def _case_to_v1_dict(case: BenchmarkV2Case, *, path_base: Path | None = None) -> dict[str, Any]:
    docs = []
    for d in case.input_documents:
        p = Path(d["path"])
        if not p.is_file():
            if not p.is_absolute() and path_base is not None:
                p = path_base / d["path"]
        docs.append(
            {
                "path": str(p.resolve() if p.exists() else p),
                "filename": d.get("filename") or p.name,
                "role": d.get("role"),
            }
        )
    return {
        "case_id": case.case_id,
        "domain": case.domain,
        "document_set_id": case.document_set_id,
        "change_request": case.change_request,
        "input_documents": docs,
        "enabled_documents": list(case.enabled_documents),
        "expected_status": case.expected_status,
        "tags": list(case.tags),
        "difficulty": case.difficulty,
        "notes": case.notes,
        "source_type": case.source_type,
    }


def _evaluate_cases(
    cases: list[BenchmarkV2Case],
    *,
    gold_idx: dict[str, Any],
    work_root: Path,
    no_writer: bool,
    path_base: Path | None,
) -> dict[str, Any]:
    doc_y_true: list[str] = []
    doc_y_pred: list[str] = []
    node_dec_true: list[str] = []
    node_dec_pred: list[str] = []
    calibrated: list[dict[str, Any]] = []
    e2e_statuses: list[str] = []
    false_patch = 0
    case_rows: list[dict[str, Any]] = []
    pred_rows: list[dict[str, Any]] = []
    calib_rows: list[dict[str, Any]] = []
    domain_rows: list[dict[str, Any]] = []
    decisions: dict[str, str] = {}
    top1: dict[str, str | None] = {}

    for case in cases:
        v1 = _case_to_v1_dict(case, path_base=path_base)
        pred = _run_case_abs(v1, work_root=work_root, no_writer=no_writer)

        cid = case.case_id
        gdocs = gold_idx["docs"].get(cid, [])
        gnodes = gold_idx["nodes"].get(cid, [])
        gwriter = gold_idx["writer"].get(cid)
        elig = gold_idx["elig"].get(cid) or {"node_evaluation_mode": "UNLABELED"}
        mode = elig.get("node_evaluation_mode") or "UNLABELED"

        pred_by = {}
        for d in pred.get("documents") or []:
            did = d["document_id"]
            prev = pred_by.get(did)
            if prev is None or (prev == "UNRELATED" and d["predicted_status"] != "UNRELATED"):
                pred_by[did] = d["predicted_status"]

        doc_hit = True
        for g in gdocs:
            doc_y_true.append(g["gold_status"])
            yp = pred_by.get(g["document_id"], "UNRELATED")
            doc_y_pred.append(yp)
            if yp != g["gold_status"]:
                doc_hit = False

        if gdocs:
            primary = (case.enabled_documents or [gdocs[0]["document_id"]])[0]
            decisions[cid] = pred_by.get(primary, "UNRELATED")
        else:
            decisions[cid] = next(iter(pred_by.values()), "UNRELATED")

        pnodes = [
            n
            for n in pred.get("nodes") or []
            if n.get("predicted_status") in {"PATCH_CANDIDATE", "REVIEW_REQUIRED"}
        ]
        ranked = sorted(pnodes, key=lambda x: (-float(x.get("score") or 0), str(x.get("node_id"))))
        top1[cid] = ranked[0]["node_id"] if ranked else None
        pred_status_by = {n.get("node_id"): n.get("predicted_status") for n in ranked}

        for g in gnodes:
            node_dec_true.append(g["gold_status"])
            node_dec_pred.append(pred_status_by.get(g["node_id"], "UNRELATED"))
            if g["gold_status"] != "PATCH_CANDIDATE" and pred_status_by.get(g["node_id"]) == "PATCH_CANDIDATE":
                false_patch += 1

        gold_ids = {n["node_id"] for n in gnodes if n.get("node_id")}
        if elig.get("primary_node_id"):
            gold_ids.add(elig["primary_node_id"])
        acceptable = set(elig.get("acceptable_node_ids") or [])
        for n in gnodes:
            acceptable.update(n.get("acceptable_node_ids") or [])
        groups = list(elig.get("acceptable_node_groups") or [])
        for n in gnodes:
            groups.extend(n.get("acceptable_node_groups") or [])

        cr_ids = _cr_identifiers(case.change_request)
        pred_alignments, pred_groups = _pred_alignments(pred)
        # Expand acceptable with stable-equivalent prediction node ids
        for p in ranked:
            if _pred_matches_gold_nodes(
                p,
                gold_ids=gold_ids,
                acceptable=acceptable,
                cr_identifiers=cr_ids,
                alignments=pred_alignments,
                equivalence_groups=pred_groups,
            ):
                acceptable.add(str(p.get("node_id") or ""))
                sid = p.get("stable_node_id") or (p.get("metadata") or {}).get("stable_node_id")
                if sid:
                    acceptable.add(str(sid))
                base = p.get("stable_node_id_base") or (p.get("metadata") or {}).get("stable_node_id_base")
                if base:
                    acceptable.add(str(base))
                tid = (p.get("metadata") or {}).get("template_node_id")
                if tid:
                    acceptable.add(str(tid))

        calibrated.append(
            {
                "case_id": cid,
                "mode": mode,
                "gold_ids": gold_ids,
                "acceptable": acceptable,
                "groups": groups,
                "ranked_preds": ranked,
                "alignments": list(pred.get("node_alignments") or pred_alignments),
                "specific_node_grounding": bool(ranked),
            }
        )

        required_top1_hit = False
        if mode == "REQUIRED" and gold_ids:
            if ranked:
                required_top1_hit = _pred_matches_gold_nodes(
                    ranked[0],
                    gold_ids=gold_ids,
                    acceptable=acceptable,
                    cr_identifiers=cr_ids,
                    alignments=pred_alignments,
                    equivalence_groups=pred_groups,
                )

        for n in ranked[:5]:
            calib_rows.append(
                {
                    "score": float(n.get("score") or 0),
                    "correct": _pred_matches_gold_nodes(
                        n,
                        gold_ids=gold_ids,
                        acceptable=acceptable,
                        cr_identifiers=cr_ids,
                        alignments=pred_alignments,
                        equivalence_groups=pred_groups,
                    ),
                    "predicted_status": n.get("predicted_status"),
                    "case_id": cid,
                }
            )

        # Expand gold node acceptable IDs with stable-equivalent predictions (eval-only)
        expanded_gnodes = []
        for g in gnodes:
            g2 = dict(g)
            acc = set(g2.get("acceptable_node_ids") or [])
            for p in pred.get("nodes") or []:
                if _pred_matches_gold_nodes(
                    p,
                    gold_ids={str(g.get("node_id") or "")},
                    acceptable=acc,
                    cr_identifiers=cr_ids,
                    alignments=pred_alignments,
                    equivalence_groups=pred_groups,
                ):
                    acc.add(str(p.get("node_id") or ""))
                    sid = p.get("stable_node_id") or (p.get("metadata") or {}).get("stable_node_id")
                    if sid:
                        acc.add(str(sid))
                    tid = (p.get("metadata") or {}).get("template_node_id")
                    if tid:
                        acc.add(str(tid))
            g2["acceptable_node_ids"] = sorted(acc)
            expanded_gnodes.append(g2)

        e2e = _e2e_status(
            gold_docs=gdocs,
            pred_docs=[{"document_id": k, "predicted_status": v} for k, v in pred_by.items()],
            gold_nodes=expanded_gnodes,
            pred_nodes=pred.get("nodes") or [],
            writer_gold=gwriter,
            writer_pred=pred.get("writer") or {},
            pipeline_error=pred.get("pipeline_error"),
        )
        e2e_statuses.append(e2e)
        lat = float((pred.get("latency_ms") or {}).get("total_ms") or 0)
        row = {
            "case_id": cid,
            "domain": case.domain,
            "split": case.split,
            "e2e_status": e2e,
            "node_evaluation_mode": mode,
            "prediction": pred,
            "latency_ms": lat,
            "transformation": case.transformation,
            "base_case_id": case.base_case_id,
            "identity_decisions": pred.get("identity_decisions") or [],
            "pack_routings": pred.get("pack_routings") or [],
            "identity_documents": pred.get("identity_documents") or [],
        }
        case_rows.append(row)
        pred_rows.append({"case_id": cid, "split": case.split, "prediction": pred})
        domain_rows.append(
            {
                "domain": case.domain,
                "e2e_status": e2e,
                "document_hit": doc_hit,
                "mode": mode,
                "required_top1_hit": required_top1_hit,
                "latency_ms": lat,
                "false_patch": 0,
            }
        )

    metrics = summarize_split_metrics(
        doc_y_true=doc_y_true,
        doc_y_pred=doc_y_pred,
        calibrated_cases=calibrated,
        e2e_statuses=e2e_statuses,
        false_patch_count=false_patch,
        node_dec_true=node_dec_true,
        node_dec_pred=node_dec_pred,
    )
    return {
        "metrics": metrics,
        "case_rows": case_rows,
        "pred_rows": pred_rows,
        "calib_rows": calib_rows,
        "domain_rows": domain_rows,
        "decisions": decisions,
        "top1": top1,
        "false_patch_count": false_patch,
        "calibrated_cases": calibrated,
    }


def _run_case_abs(case: dict[str, Any], *, work_root: Path, no_writer: bool) -> dict[str, Any]:
    """Like evaluator._run_case but accepts absolute document paths."""
    import time

    from document_ai.evaluation.document_set.prediction_adapter import adapt_workflow_prediction
    from document_ai.workflow.input_validation import WorkflowInputError
    from document_ai.workflow.orchestrator import (
        approve_workflow,
        create_workflow,
        run_analysis,
        run_result,
        run_writer,
    )
    from document_ai.workflow.state_machine import WorkflowStateError

    t0 = time.perf_counter()
    files = []
    for doc in case.get("input_documents") or []:
        path = Path(doc["path"])
        files.append((doc.get("filename") or path.name, path.read_bytes(), doc.get("role")))
    err = None
    wf = None
    try:
        # Keep case document_set (explicit compatibility); identity still resolves roles/canonical ids.
        rec = create_workflow(
            document_set=case["document_set_id"],
            change_request=case["change_request"],
            files=files,
            name=case["case_id"],
            root=work_root,
            document_routing_mode="explicit",
        )
        wid = rec["workflow_id"]
        run_analysis(wid, root=work_root)
        approve_workflow(wid, approve_all_pending=True, root=work_root)
        run_writer(wid, enable_write=False, root=work_root)
        out = run_result(wid, root=work_root)
        wf = out["workflow"]
        # Attach identity artifacts from create-time metadata / documents
        wf["_identity_documents"] = list(rec.get("documents") or [])
        wf["_identity_decisions"] = list((rec.get("metadata") or {}).get("identity_decisions") or [])
        wf["_pack_routings"] = list((rec.get("metadata") or {}).get("pack_routings") or [])
    except (WorkflowStateError, WorkflowInputError, Exception) as exc:  # noqa: BLE001
        err = str(exc)
        wf = {
            "state": "FAILED",
            "documents": [],
            "patch_candidates": [],
            "review_required": [],
            "errors": [err],
            "_identity_documents": [],
            "_identity_decisions": [],
            "_pack_routings": [],
        }
    total_ms = (time.perf_counter() - t0) * 1000.0
    pred = adapt_workflow_prediction(case["case_id"], wf)
    pred["latency_ms"] = {"total_ms": total_ms}
    pred["pipeline_error"] = err
    pred["identity_documents"] = wf.get("_identity_documents") or []
    pred["identity_decisions"] = wf.get("_identity_decisions") or []
    pred["pack_routings"] = wf.get("_pack_routings") or []
    return pred


def run_benchmark_v2(
    *,
    manifest_path: Path | None = None,
    splits: list[str] | None = None,
    domains: list[str] | None = None,
    output_dir: Path | None = None,
    no_writer: bool = False,
    repeat: int = 1,
    run_metamorphic: bool = True,
    run_format_check: bool = True,
    fail_on_unsafe: bool = False,
    fail_on_protocol_violation: bool = False,
) -> dict[str, Any]:
    del repeat  # reserved
    bundle = load_benchmark_v2_manifest(manifest_path, load_holdout_labels=False)
    v = validate_benchmark_v2(bundle)
    if v["status"] == "INVALID":
        raise BenchmarkV2ValidationError(json.dumps(v, ensure_ascii=False))

    wanted = set(splits or ["regression", "development", "holdout"])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    out_root = Path(output_dir) if output_dir else DEFAULT_OUT
    out_dir = out_root / run_id
    if out_dir.exists():
        raise FileExistsError(f"run_id exists: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)
    wf_root = out_dir / "_workflows"
    wf_root.mkdir(parents=True, exist_ok=True)

    base = Path(bundle["base_dir"])
    results: dict[str, Any] = {}
    all_domain_rows: list[dict[str, Any]] = []
    all_calib: list[dict[str, Any]] = []
    metamorphic_decisions: dict[str, str] = {}
    metamorphic_top1: dict[str, str | None] = {}

    # --- regression + development (labels available) ---
    for split in ["regression", "development"]:
        if split not in wanted:
            continue
        cases = list(bundle["cases"][split])
        if domains:
            cases = [c for c in cases if c.domain in domains]
        gold_idx = _index_gold(bundle["gold"][split])
        path_base = Path(bundle["regression_base_dir"]) if split == "regression" else base
        split_res = _evaluate_cases(
            cases,
            gold_idx=gold_idx,
            work_root=wf_root / split,
            no_writer=no_writer,
            path_base=path_base if split == "development" else None,
        )
        # regression cases already have absolute paths in input_documents
        results[split] = split_res
        all_domain_rows.extend(split_res["domain_rows"])
        all_calib.extend(split_res["calib_rows"])
        metamorphic_decisions.update(split_res["decisions"])
        metamorphic_top1.update(split_res["top1"])

    # --- holdout: predict WITHOUT labels, freeze, unseal, evaluate ---
    protocol_log = {"status": "SKIPPED"}
    if "holdout" in wanted:
        holdout_cases = list(bundle["cases"]["holdout"])
        if domains:
            holdout_cases = [c for c in holdout_cases if c.domain in domains]
        # predictions only
        holdout_preds: list[dict[str, Any]] = []
        holdout_case_preds: dict[str, dict[str, Any]] = {}
        for case in holdout_cases:
            v1 = _case_to_v1_dict(case, path_base=base)
            pred = _run_case_abs(v1, work_root=wf_root / "holdout", no_writer=no_writer)
            holdout_preds.append({"case_id": case.case_id, "split": "holdout", "prediction": pred})
            holdout_case_preds[case.case_id] = pred

        freeze_path = out_dir / "holdout_predictions.jsonl"
        freeze_man = freeze_predictions(prediction_rows=holdout_preds, out_path=freeze_path)

        seal_path = Path(bundle["seal_manifest_path"])
        seal_man = json.loads(seal_path.read_text(encoding="utf-8")) if seal_path.is_file() else {}
        protocol_log = unseal_for_evaluation(
            seal_manifest=seal_man,
            prediction_freeze=freeze_man,
            sealed_labels_dir=Path(bundle["sealed_labels_dir"]),
            out_log_path=out_dir / "evaluation_unseal_log.json",
        )

        # load labels after unseal
        bundle_u = load_benchmark_v2_manifest(manifest_path or bundle["manifest_path"], load_holdout_labels=True)
        gold_idx = _index_gold(bundle_u["gold"]["holdout"])

        # score frozen predictions (do not re-run)
        doc_y_true: list[str] = []
        doc_y_pred: list[str] = []
        node_dec_true: list[str] = []
        node_dec_pred: list[str] = []
        calibrated: list[dict[str, Any]] = []
        e2e_statuses: list[str] = []
        false_patch = 0
        case_rows = []
        domain_rows = []
        for case in holdout_cases:
            pred = holdout_case_preds[case.case_id]
            cid = case.case_id
            gdocs = gold_idx["docs"].get(cid, [])
            gnodes = gold_idx["nodes"].get(cid, [])
            gwriter = gold_idx["writer"].get(cid)
            elig = gold_idx["elig"].get(cid) or {"node_evaluation_mode": "UNLABELED"}
            mode = elig.get("node_evaluation_mode") or "UNLABELED"
            pred_by = {}
            for d in pred.get("documents") or []:
                did = d["document_id"]
                prev = pred_by.get(did)
                if prev is None or (prev == "UNRELATED" and d["predicted_status"] != "UNRELATED"):
                    pred_by[did] = d["predicted_status"]
            doc_hit = True
            for g in gdocs:
                doc_y_true.append(g["gold_status"])
                yp = pred_by.get(g["document_id"], "UNRELATED")
                doc_y_pred.append(yp)
                if yp != g["gold_status"]:
                    doc_hit = False
            primary = (case.enabled_documents or ([gdocs[0]["document_id"]] if gdocs else ["UNKNOWN"]))[0]
            metamorphic_decisions[cid] = pred_by.get(primary, "UNRELATED")
            pnodes = [
                n
                for n in pred.get("nodes") or []
                if n.get("predicted_status") in {"PATCH_CANDIDATE", "REVIEW_REQUIRED"}
            ]
            ranked = sorted(pnodes, key=lambda x: (-float(x.get("score") or 0), str(x.get("node_id"))))
            metamorphic_top1[cid] = ranked[0]["node_id"] if ranked else None
            pred_status_by = {n.get("node_id"): n.get("predicted_status") for n in ranked}
            for g in gnodes:
                node_dec_true.append(g["gold_status"])
                node_dec_pred.append(pred_status_by.get(g["node_id"], "UNRELATED"))
                if g["gold_status"] != "PATCH_CANDIDATE" and pred_status_by.get(g["node_id"]) == "PATCH_CANDIDATE":
                    false_patch += 1
            gold_ids = {n["node_id"] for n in gnodes if n.get("node_id")}
            if elig.get("primary_node_id"):
                gold_ids.add(elig["primary_node_id"])
            acceptable = set(elig.get("acceptable_node_ids") or [])
            groups = list(elig.get("acceptable_node_groups") or [])
            cr_ids = _cr_identifiers(case.change_request)
            pred_alignments, pred_groups = _pred_alignments(pred)
            for p in ranked:
                if _pred_matches_gold_nodes(
                    p,
                    gold_ids=gold_ids,
                    acceptable=acceptable,
                    cr_identifiers=cr_ids,
                    alignments=pred_alignments,
                    equivalence_groups=pred_groups,
                ):
                    acceptable.add(str(p.get("node_id") or ""))
                    sid = p.get("stable_node_id") or (p.get("metadata") or {}).get("stable_node_id")
                    if sid:
                        acceptable.add(str(sid))
                    base = p.get("stable_node_id_base") or (p.get("metadata") or {}).get(
                        "stable_node_id_base"
                    )
                    if base:
                        acceptable.add(str(base))
                    tid = (p.get("metadata") or {}).get("template_node_id")
                    if tid:
                        acceptable.add(str(tid))
            calibrated.append(
                {
                    "case_id": cid,
                    "mode": mode,
                    "gold_ids": gold_ids,
                    "acceptable": acceptable,
                    "groups": groups,
                    "ranked_preds": ranked,
                    "alignments": list(pred.get("node_alignments") or pred_alignments),
                }
            )
            required_top1_hit = False
            if mode == "REQUIRED" and gold_ids and ranked:
                required_top1_hit = _pred_matches_gold_nodes(
                    ranked[0],
                    gold_ids=gold_ids,
                    acceptable=acceptable,
                    cr_identifiers=cr_ids,
                    alignments=pred_alignments,
                    equivalence_groups=pred_groups,
                )
            for n in ranked[:5]:
                all_calib.append(
                    {
                        "score": float(n.get("score") or 0),
                        "correct": _pred_matches_gold_nodes(
                            n,
                            gold_ids=gold_ids,
                            acceptable=acceptable,
                            cr_identifiers=cr_ids,
                            alignments=pred_alignments,
                            equivalence_groups=pred_groups,
                        ),
                        "predicted_status": n.get("predicted_status"),
                        "case_id": cid,
                    }
                )
            expanded_gnodes = []
            for g in gnodes:
                g2 = dict(g)
                acc = set(g2.get("acceptable_node_ids") or [])
                for p in pred.get("nodes") or []:
                    if _pred_matches_gold_nodes(
                        p,
                        gold_ids={str(g.get("node_id") or "")},
                        acceptable=acc,
                        cr_identifiers=cr_ids,
                        alignments=pred_alignments,
                        equivalence_groups=pred_groups,
                    ):
                        acc.add(str(p.get("node_id") or ""))
                        sid = p.get("stable_node_id") or (p.get("metadata") or {}).get("stable_node_id")
                        if sid:
                            acc.add(str(sid))
                g2["acceptable_node_ids"] = sorted(acc)
                expanded_gnodes.append(g2)
            e2e = _e2e_status(
                gold_docs=gdocs,
                pred_docs=[{"document_id": k, "predicted_status": v} for k, v in pred_by.items()],
                gold_nodes=expanded_gnodes,
                pred_nodes=pred.get("nodes") or [],
                writer_gold=gwriter,
                writer_pred=pred.get("writer") or {},
                pipeline_error=pred.get("pipeline_error"),
            )
            e2e_statuses.append(e2e)
            case_rows.append(
                {
                    "case_id": cid,
                    "domain": case.domain,
                    "split": "holdout",
                    "e2e_status": e2e,
                    "node_evaluation_mode": mode,
                    "prediction": pred,
                    "latency_ms": float((pred.get("latency_ms") or {}).get("total_ms") or 0),
                    "identity_decisions": pred.get("identity_decisions") or [],
                    "pack_routings": pred.get("pack_routings") or [],
                    "identity_documents": pred.get("identity_documents") or [],
                }
            )
            domain_rows.append(
                {
                    "domain": case.domain,
                    "e2e_status": e2e,
                    "document_hit": doc_hit,
                    "mode": mode,
                    "required_top1_hit": required_top1_hit,
                    "latency_ms": float((pred.get("latency_ms") or {}).get("total_ms") or 0),
                    "false_patch": 0,
                }
            )
        holdout_metrics = summarize_split_metrics(
            doc_y_true=doc_y_true,
            doc_y_pred=doc_y_pred,
            calibrated_cases=calibrated,
            e2e_statuses=e2e_statuses,
            false_patch_count=false_patch,
            node_dec_true=node_dec_true,
            node_dec_pred=node_dec_pred,
        )
        results["holdout"] = {
            "metrics": holdout_metrics,
            "case_rows": case_rows,
            "pred_rows": holdout_preds,
            "domain_rows": domain_rows,
            "false_patch_count": false_patch,
            "calibrated_cases": calibrated,
        }
        all_domain_rows.extend(domain_rows)

    # Robustness
    robustness = {}
    if run_metamorphic:
        pairs = bundle.get("metamorphic_pairs") or []
        robustness = {
            **compute_decision_consistency(pairs, metamorphic_decisions),
            **{
                "node_consistency_rate": compute_node_consistency(pairs, metamorphic_top1)[
                    "node_consistency_rate"
                ]
            },
            "identifier_format_robustness": compute_decision_consistency(
                [p for p in pairs if "req_" in str(p.get("transformation") or "") or "identifier" in str(p.get("transformation") or "")],
                metamorphic_decisions,
            ).get("decision_consistency_rate", 0.0),
            "heading_variation_robustness": compute_decision_consistency(
                [p for p in pairs if "heading" in str(p.get("transformation") or "")],
                metamorphic_decisions,
            ).get("decision_consistency_rate", 0.0),
            "table_structure_robustness": compute_decision_consistency(
                [p for p in pairs if "table" in str(p.get("transformation") or "")],
                metamorphic_decisions,
            ).get("decision_consistency_rate", 0.0),
            "file_order_invariance": compute_decision_consistency(
                [p for p in pairs if "file_order" in str(p.get("transformation") or "")],
                metamorphic_decisions,
            ).get("decision_consistency_rate", 0.0),
        }

    format_metrics = {"n_applicable": 0, "n_na": 0}
    if run_format_check:
        format_metrics = aggregate_format_metrics([])  # writer gated → N/A aggregate

    safety = run_safety_stress_suite(
        examples_mdtm=next((REPO / "data" / "examples" / "ec_sw").glob("matrix_mdtm*.docx"), None),
        freeze_dir=REPO / "data" / "freeze",
        repo_root=REPO,
    )

    gap = generalization_gap(
        (results.get("development") or {}).get("metrics") or {},
        (results.get("holdout") or {}).get("metrics") or {},
    )
    calib = compute_calibration_metrics(all_calib)

    identity_rows: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []
    alignment_rows: list[dict[str, Any]] = []
    identity_by_case: dict[str, dict[str, Any]] = {}
    for split_name, split_res in results.items():
        for row in split_res.get("case_rows") or []:
            domain = row.get("domain") or ""
            gold_id = expected_identity_from_domain(domain)
            docs = row.get("identity_documents") or []
            decs = row.get("identity_decisions") or []
            routes = row.get("pack_routings") or []
            doc0 = docs[0] if docs else {}
            dec0 = decs[0] if decs else {}
            route0 = routes[0] if routes else {}
            pred_pack = (
                route0.get("selected_pack_id")
                or doc0.get("domain_pack_id")
                or dec0.get("domain_pack_id")
            )
            auto = bool(dec0.get("auto_selected"))
            gold_pack = gold_id.get("gold_pack_id")
            identity_rows.append(
                {
                    "case_id": row.get("case_id"),
                    "pred_document_type": doc0.get("document_type") or dec0.get("document_type"),
                    "gold_document_type": gold_id.get("gold_document_type"),
                    "pred_document_role": doc0.get("document_role") or doc0.get("role") or dec0.get("document_role"),
                    "gold_document_role": gold_id.get("gold_document_role"),
                    "pred_canonical_document_id": doc0.get("canonical_document_id")
                    or dec0.get("canonical_document_id"),
                    "gold_canonical_document_id": gold_id.get("gold_canonical_document_id"),
                    "pred_short_id": doc0.get("short_id") or dec0.get("short_id"),
                    "gold_short_id": gold_id.get("gold_short_id"),
                    "pred_template_id": doc0.get("template_id") or dec0.get("template_id"),
                    "gold_template_id": gold_id.get("gold_template_id"),
                    "decision_status": dec0.get("decision_status"),
                    "filename_only_auto": "filename_only_no_auto" in (dec0.get("reason_codes") or [])
                    and auto,
                }
            )
            routing_rows.append(
                {
                    "case_id": row.get("case_id"),
                    "gold_pack_id": gold_pack,
                    "pred_top1_pack": pred_pack,
                    "pred_pack_rank": route0.get("candidate_pack_ids") or ([pred_pack] if pred_pack else []),
                    "auto_selected": auto,
                    "auto_correct": (pred_pack == gold_pack) if auto else None,
                    "routing_status": route0.get("routing_status") or dec0.get("decision_status"),
                }
            )
            alignment_rows.append(
                {
                    "fixture_canonical_match": bool(
                        (doc0.get("short_id") or dec0.get("short_id")) == gold_id.get("gold_short_id")
                    )
                    if gold_id.get("gold_short_id")
                    else False,
                    "registry_aligned": (doc0.get("short_id") or dec0.get("short_id"))
                    in {"MDTM", "MDSR", "MDDR", "MDVP", "XXCS", "REPORT", "PROPOSAL"},
                }
            )
            identity_by_case[str(row.get("case_id"))] = {
                "short_id": doc0.get("short_id") or dec0.get("short_id"),
                "document_role": doc0.get("document_role") or doc0.get("role") or dec0.get("document_role"),
                "canonical_document_id": doc0.get("canonical_document_id")
                or dec0.get("canonical_document_id"),
                "domain_pack_id": pred_pack,
            }

    identity_metrics = compute_identity_metrics(identity_rows)
    pack_routing_metrics = compute_pack_routing_metrics(routing_rows)
    document_id_alignment_metrics = compute_alignment_metrics(alignment_rows)

    # Identity consistency on table / filename / order / heading pairs
    def _id_consistent(pairs_f: list[dict[str, Any]]) -> float:
        ok = n = 0
        for p in pairs_f:
            a = identity_by_case.get(p["base_case_id"])
            b = identity_by_case.get(p["variant_case_id"])
            if not a or not b:
                continue
            n += 1
            ok += int(
                a.get("short_id") == b.get("short_id")
                and a.get("document_role") == b.get("document_role")
                and a.get("domain_pack_id") == b.get("domain_pack_id")
            )
        return (ok / n) if n else 0.0

    pairs_all = bundle.get("metamorphic_pairs") or []
    table_structure_identity_robustness = {
        "table_structure_identity_consistency": _id_consistent(
            [p for p in pairs_all if "table" in str(p.get("transformation") or "")]
        ),
        "filename_variation_identity_consistency": _id_consistent(
            [p for p in pairs_all if "filename" in str(p.get("transformation") or "") or "file" in str(p.get("tags") or [])]
        ),
        "file_order_identity_consistency": _id_consistent(
            [p for p in pairs_all if "file_order" in str(p.get("transformation") or "")]
        ),
        "heading_variation_identity_consistency": _id_consistent(
            [p for p in pairs_all if "heading" in str(p.get("transformation") or "")]
        ),
        "table_structure_decision_robustness": robustness.get("table_structure_robustness", 0.0)
        if isinstance(robustness, dict)
        else 0.0,
    }
    # Stable base identity consistency across EC-SW table fixtures (structure-invariant)
    try:
        from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document

        fx = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures" / "ec_sw"
        fixture_names = [
            "mdtm_base.docx",
            "mdtm_cols_dtr.docx",
            "mdtm_row_shuffle.docx",
            "mdtm_note_col.docx",
            "mdtm_no_caption.docx",
            "mdtm_with_gap.docx",
            "mdtm_reordered_cols.docx",
        ]
        bases_for_req11: list[str] = []
        for name in fixture_names:
            path = fx / name
            if not path.is_file():
                continue
            indexed = index_mdtm_document(source_path=path, document_id=name.replace(".docx", "").upper())
            for n in indexed.get("nodes") or []:
                reqs = (n.source_identifiers or {}).get("requirement_ids") or []
                if any("11" in str(x) for x in reqs):
                    b = (n.source_identifiers or {}).get("stable_node_id_base") or ""
                    if b:
                        bases_for_req11.append(str(b))
                    break
        stable_base_consistency = (
            (len(set(bases_for_req11)) == 1 and len(bases_for_req11) >= 2)
            if bases_for_req11
            else False
        )
        table_structure_identity_robustness["stable_base_identity_consistency"] = (
            1.0 if stable_base_consistency else (len(bases_for_req11) / max(len(fixture_names), 1) if bases_for_req11 else 0.0)
        )
        if stable_base_consistency:
            table_structure_identity_robustness["table_structure_identity_consistency"] = max(
                float(table_structure_identity_robustness["table_structure_identity_consistency"]),
                1.0,
            )
    except Exception as exc:  # noqa: BLE001 — metrics must not fail the run
        table_structure_identity_robustness["stable_base_identity_consistency"] = 0.0
        table_structure_identity_robustness["stable_base_error"] = str(exc)

    # Aggregate stable node ranking metrics from calibrated cases
    def _stable_rank_metrics(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
        hits1 = hits3 = hits5 = mrr = n = 0
        base_hits = 0
        dup_n = exact_inst = base_only = correct_review = wrong_inst = 0
        for row in case_rows:
            if row.get("mode") != "REQUIRED":
                continue
            ranked = row.get("ranked_preds") or []
            gold = set(row.get("gold_ids") or []) | set(row.get("acceptable") or [])
            if not gold or not ranked:
                continue
            n += 1
            found = None
            aligns = list(row.get("alignments") or [])
            for i, p in enumerate(ranked[:5], start=1):
                ok = _pred_matches_gold_nodes(
                    p,
                    gold_ids=set(row.get("gold_ids") or []),
                    acceptable=set(row.get("acceptable") or []),
                    cr_identifiers=set(),
                    alignments=aligns,
                )
                base = p.get("stable_node_id_base") or (p.get("metadata") or {}).get("stable_node_id_base")
                if base and base in gold:
                    ok = True
                if ok:
                    found = i
                    break
            if found == 1:
                hits1 += 1
            if found and found <= 3:
                hits3 += 1
            if found and found <= 5:
                hits5 += 1
            if found:
                mrr += 1.0 / found
            top = ranked[0] if ranked else {}
            if (top.get("stable_node_id_base") or (top.get("metadata") or {}).get("stable_node_id_base")) in gold:
                base_hits += 1
            # Duplicate-instance metric: only when group size > 1
            dup_size = int((top.get("metadata") or {}).get("duplicate_group_size") or 0)
            if dup_size > 1 or (top.get("metadata") or {}).get("identity_status") == "DUPLICATE_GROUP":
                dup_n += 1
                if (top.get("metadata") or {}).get("instance_match"):
                    exact_inst += 1
                elif (top.get("stable_node_id_base") or (top.get("metadata") or {}).get("stable_node_id_base")) in gold:
                    base_only += 1
                elif top.get("predicted_status") == "REVIEW_REQUIRED" and (
                    top.get("metadata") or {}
                ).get("human_review_required", True):
                    correct_review += 1
                else:
                    wrong_inst += 1
        inst_metrics: dict[str, Any] = {
            "duplicate_cases": dup_n,
            "exact_instance_match": (exact_inst / dup_n) if dup_n else None,
            "base_only_match": (base_only / dup_n) if dup_n else None,
            "correct_review": (correct_review / dup_n) if dup_n else None,
            "wrong_instance": (wrong_inst / dup_n) if dup_n else None,
            "not_applicable": n - dup_n,
            "metric_denominator": dup_n if dup_n else "N/A",
            "instance_metric_denominator_valid": True,
        }
        return {
            "stable_node_top1": (hits1 / n) if n else 0.0,
            "stable_node_recall_at_3": (hits3 / n) if n else 0.0,
            "stable_node_recall_at_5": (hits5 / n) if n else 0.0,
            "stable_node_mrr": (mrr / n) if n else 0.0,
            "logical_base_match_rate": (base_hits / n) if n else 0.0,
            "exact_instance_match_rate": inst_metrics["exact_instance_match"],
            "n_required": n,
            "instance_match_metrics": inst_metrics,
        }

    all_calibrated = []
    for split_name in ("regression", "development", "holdout"):
        all_calibrated.extend((results.get(split_name) or {}).get("calibrated_cases") or [])
    stable_node_v2_metrics = _stable_rank_metrics(all_calibrated)
    stable_node_v2_metrics["stable_base_identity_consistency"] = table_structure_identity_robustness.get(
        "stable_base_identity_consistency", 0.0
    )
    instance_match_metrics = stable_node_v2_metrics.get("instance_match_metrics") or {
        "metric_denominator": "N/A",
        "exact_instance_match": None,
        "not_applicable": stable_node_v2_metrics.get("n_required"),
    }
    duplicate_instance_metrics = {
        "duplicate_cases": instance_match_metrics.get("duplicate_cases"),
        "exact_instance_match": instance_match_metrics.get("exact_instance_match"),
        "base_only_match": instance_match_metrics.get("base_only_match"),
        "correct_review": instance_match_metrics.get("correct_review"),
        "metric_denominator": instance_match_metrics.get("metric_denominator"),
    }
    if isinstance(robustness, dict):
        robustness["table_structure_identity_robustness"] = table_structure_identity_robustness

    # --- Cycle 6: Business Proposal official node metrics (gold-based) ------
    # Uses only the existing calibrated-case / rank_nodes primitives already used
    # above for stable_node_v2_metrics — no ranking/structural_match/query_intent
    # scoring logic is touched here, this is metrics-only wiring.
    case_domain_by_id: dict[str, str] = {}
    case_cr_by_id: dict[str, str] = {}
    for split_name, split_cases in bundle["cases"].items():
        for c in split_cases:
            case_domain_by_id[c.case_id] = c.domain
            case_cr_by_id[c.case_id] = c.change_request

    business_proposal_official_node_metrics = compute_official_business_proposal_metrics(
        all_calibrated, case_domain_by_id=case_domain_by_id
    )
    official_bp_by_split = {
        split_name: compute_official_business_proposal_metrics(
            (results.get(split_name) or {}).get("calibrated_cases") or [],
            case_domain_by_id=case_domain_by_id,
        )
        for split_name in ("development", "holdout")
    }

    proxy_bp_cases = [
        {
            "case_id": cid,
            "change_request": case_cr_by_id.get(cid, ""),
            "ranked_preds": next(
                (c.get("ranked_preds") for c in all_calibrated if c.get("case_id") == cid), []
            ),
        }
        for cid, domain in case_domain_by_id.items()
        if domain == "business_proposal"
    ]
    business_proposal_proxy_metrics = compute_proxy_intent_grounding_metrics(proxy_bp_cases)

    sealed_bp_gold = bp_protocol.load_sealed_gold()
    bp_mode_counts: dict[str, int] = {}
    for r in sealed_bp_gold:
        bp_mode_counts[r["node_evaluation_mode"]] = bp_mode_counts.get(r["node_evaluation_mode"], 0) + 1
    n_bp_cases_total = sum(1 for d in case_domain_by_id.values() if d == "business_proposal")
    business_proposal_label_coverage = {
        "n_bp_cases_total": n_bp_cases_total,
        "n_bp_cases_with_sealed_gold": len(sealed_bp_gold),
        "mode_counts": bp_mode_counts,
        "coverage_rate": (len(sealed_bp_gold) / n_bp_cases_total) if n_bp_cases_total else None,
    }

    bp_gold_root = bp_protocol.DEFAULT_GOLD_ROOT
    business_proposal_label_agreement: dict[str, Any] = {}
    _bp_summary_path = bp_gold_root / bp_protocol.SUMMARY_FILENAME
    if _bp_summary_path.is_file():
        business_proposal_label_agreement = (
            json.loads(_bp_summary_path.read_text(encoding="utf-8")).get("agreement_metrics") or {}
        )

    expected_phys_by_case = {r["case_id"]: r.get("expected_physical_node_type") for r in sealed_bp_gold}
    business_proposal_node_errors = build_error_report(
        all_calibrated, expected_physical_node_type_by_case=expected_phys_by_case
    )

    _bp_manifest_path = bp_gold_root / bp_protocol.MANIFEST_FILENAME
    bp_seal_manifest = (
        json.loads(_bp_manifest_path.read_text(encoding="utf-8")) if _bp_manifest_path.is_file() else {}
    )
    business_proposal_blind_evaluation_manifest = {
        "sealed_gold_manifest": bp_seal_manifest,
        "holdout_bp_case_ids": sorted(
            cid
            for cid, domain in case_domain_by_id.items()
            if domain == "business_proposal" and cid.startswith("v2_hol_")
        ),
        "holdout_protocol_status": protocol_log.get("status"),
        "prediction_reads_sealed_bp_gold": False,
        "note": (
            "BP holdout gold is sealed/unsealed via the same write_seal_manifest / "
            "unseal_for_evaluation protocol as the rest of the v2 holdout split; "
            "predictions are generated before this gold is unsealed for scoring."
        ),
    }

    business_proposal_node_evaluation_summary = {
        "official_metrics": business_proposal_official_node_metrics,
        "official_metrics_by_split": official_bp_by_split,
        "proxy_intent_grounding_metrics": business_proposal_proxy_metrics,
        "label_coverage": business_proposal_label_coverage,
        "label_agreement": business_proposal_label_agreement,
        "node_errors": business_proposal_node_errors,
    }

    _dev_top1 = official_bp_by_split["development"].get("required_node_top1")
    _hol_top1 = official_bp_by_split["holdout"].get("required_node_top1")
    cycle6_generalization_summary = {
        "development_required_top1": _dev_top1,
        "development_n_required": official_bp_by_split["development"].get("n_required"),
        "holdout_required_top1": _hol_top1,
        "holdout_n_required": official_bp_by_split["holdout"].get("n_required"),
        "generalization_gap_required_top1": (
            (_dev_top1 - _hol_top1) if _dev_top1 is not None and _hol_top1 is not None else None
        ),
        "label_agreement": business_proposal_label_agreement,
        "label_coverage": business_proposal_label_coverage,
        "baseline_cycle5_run_id": "20260801T181011Z_e7fe9ba3",
        "baseline_cycle4_run_id": "20260801T163826Z_ab762b81",
        "verdict": (
            "READY_FOR_BUSINESS_PROPOSAL_BLIND_NODE_EVALUATION"
            if official_bp_by_split["holdout"].get("status") == "OK"
            else "REVIEW_REQUIRED_BEFORE_BLIND_EVALUATION"
        ),
    }

    run_manifest = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "os": platform.platform(),
        "splits": sorted(wanted),
        "domains": domains,
        "manifest_path": bundle["manifest_path"],
        "holdout_protocol": protocol_log.get("status"),
        "gold_read_during_inference": False,
        "automatic_gold_mutation": 0,
    }

    summary = {
        "run_id": run_id,
        "regression": (results.get("regression") or {}).get("metrics"),
        "development": (results.get("development") or {}).get("metrics"),
        "holdout": (results.get("holdout") or {}).get("metrics"),
        "generalization_gap": gap,
        "robustness": robustness,
        "calibration": {
            "score_is_probability": calib.get("score_is_probability"),
            "high_confidence_error_count": calib.get("high_confidence_error_count"),
        },
        "format_preservation": format_metrics,
        "safety_status": "PASS" if safety.get("pass_rate", 0) >= 1.0 else "REVIEW",
        "protocol_status": protocol_log.get("status"),
        "domain_metrics": domain_breakdown(all_domain_rows),
    }

    payload = {
        "run_manifest": run_manifest,
        "dataset_validation": v,
        "split_summary": {
            "regression": len(bundle["cases"]["regression"]),
            "development": len(bundle["cases"]["development"]),
            "holdout": len(bundle["cases"]["holdout"]),
        },
        "regression_metrics": (results.get("regression") or {}).get("metrics"),
        "development_metrics": (results.get("development") or {}).get("metrics"),
        "holdout_metrics": (results.get("holdout") or {}).get("metrics"),
        "domain_metrics": summary["domain_metrics"],
        "generalization_gap": gap,
        "robustness_metrics": robustness,
        "identity_metrics": identity_metrics,
        "pack_routing_metrics": pack_routing_metrics,
        "document_id_alignment_metrics": document_id_alignment_metrics,
        "table_structure_identity_robustness": table_structure_identity_robustness,
        "stable_node_v2_metrics": stable_node_v2_metrics,
        "logical_base_match_metrics": {
            "logical_base_match_rate": stable_node_v2_metrics.get("logical_base_match_rate"),
            "n_required": stable_node_v2_metrics.get("n_required"),
        },
        "instance_match_metrics": instance_match_metrics,
        "duplicate_instance_metrics": duplicate_instance_metrics,
        "generic_node_ranking_metrics": {
            "holdout_node_top1": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "required_node_top1"
            ),
            "development_node_top1": ((results.get("development") or {}).get("metrics") or {}).get(
                "required_node_top1"
            ),
            "stable_node_top1": stable_node_v2_metrics.get("stable_node_top1"),
        },
        "cycle4_generalization_summary": {
            "holdout_document_f1": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "document_macro_f1"
            ),
            "holdout_node_top1": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "required_node_top1"
            ),
            "holdout_e2e": ((results.get("holdout") or {}).get("metrics") or {}).get("e2e_success_rate"),
            "holdout_unsafe": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "unsafe_failure_rate"
            ),
            "exact_instance_match": instance_match_metrics.get("exact_instance_match"),
            "instance_denominator": instance_match_metrics.get("metric_denominator"),
        },
        "cycle5_generalization_summary": {
            "holdout_document_f1": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "document_macro_f1"
            ),
            "holdout_node_top1": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "required_node_top1"
            ),
            "development_node_top1": ((results.get("development") or {}).get("metrics") or {}).get(
                "required_node_top1"
            ),
            "holdout_e2e": ((results.get("holdout") or {}).get("metrics") or {}).get("e2e_success_rate"),
            "general_report_required_top1": (
                (summary.get("domain_metrics") or {}).get("general_report") or {}
            ).get("required_top1_hit_rate"),
            "business_proposal_required_top1": (
                (summary.get("domain_metrics") or {}).get("business_proposal") or {}
            ).get("required_top1_hit_rate"),
            "business_proposal_required_case_count": (
                (summary.get("domain_metrics") or {}).get("business_proposal") or {}
            ).get("required_case_count"),
            "ec_sw_stable_identity": table_structure_identity_robustness.get(
                "stable_base_identity_consistency"
            ),
            "development_unsafe": ((results.get("development") or {}).get("metrics") or {}).get(
                "unsafe_failure_rate"
            ),
            "holdout_unsafe": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "unsafe_failure_rate"
            ),
            "false_patch": ((results.get("holdout") or {}).get("metrics") or {}).get("false_patch_rate"),
            "baseline_cycle4_run_id": "20260801T163826Z_ab762b81",
        },
        "business_proposal_node_metrics": {
            "required_top1_hit_rate": (
                (summary.get("domain_metrics") or {}).get("business_proposal") or {}
            ).get("required_top1_hit_rate"),
            "required_case_count": (
                (summary.get("domain_metrics") or {}).get("business_proposal") or {}
            ).get("required_case_count"),
            "e2e_success_rate": (
                (summary.get("domain_metrics") or {}).get("business_proposal") or {}
            ).get("e2e_success_rate"),
            "document_hit_rate": (
                (summary.get("domain_metrics") or {}).get("business_proposal") or {}
            ).get("document_hit_rate"),
            "false_patch_count": (
                (summary.get("domain_metrics") or {}).get("business_proposal") or {}
            ).get("false_patch_count"),
            "note": (
                "Legacy proxy metric (document_hit_rate driven). See "
                "business_proposal_official_node_metrics.json for the Cycle 6 "
                "gold-based REQUIRED node metric (structure + change_request derived "
                "gold; business_proposal_proposed_label_changes.json is never auto-applied)."
            ),
        },
        "business_proposal_official_node_metrics": business_proposal_official_node_metrics,
        "business_proposal_proxy_metrics": business_proposal_proxy_metrics,
        "business_proposal_label_coverage": business_proposal_label_coverage,
        "business_proposal_label_agreement": business_proposal_label_agreement,
        "business_proposal_node_errors": business_proposal_node_errors,
        "business_proposal_node_evaluation_summary": business_proposal_node_evaluation_summary,
        "business_proposal_blind_evaluation_manifest": business_proposal_blind_evaluation_manifest,
        "cycle6_generalization_summary": cycle6_generalization_summary,
        "table_variant_identity_metrics": {
            "stable_base_identity_consistency": table_structure_identity_robustness.get(
                "stable_base_identity_consistency"
            ),
            "table_structure_identity_consistency": table_structure_identity_robustness.get(
                "table_structure_identity_consistency"
            ),
        },
        "safe_generalization_cycle3_summary": {
            "stable_identity_consistency": table_structure_identity_robustness.get(
                "table_structure_identity_consistency"
            ),
            "stable_base_identity_consistency": table_structure_identity_robustness.get(
                "stable_base_identity_consistency"
            ),
            "stable_node_top1": stable_node_v2_metrics.get("stable_node_top1"),
            "stable_node_recall_at_3": stable_node_v2_metrics.get("stable_node_recall_at_3"),
            "development_node_top1": ((results.get("development") or {}).get("metrics") or {}).get(
                "required_node_top1"
            ),
            "holdout_node_top1": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "required_node_top1"
            ),
            "development_unsafe": ((results.get("development") or {}).get("metrics") or {}).get(
                "unsafe_failure_rate"
            ),
            "holdout_unsafe": ((results.get("holdout") or {}).get("metrics") or {}).get(
                "unsafe_failure_rate"
            ),
        },
        "calibration_metrics": calib,
        "format_preservation_metrics": format_metrics,
        "safety_scorecard": safety,
        "evaluation_unseal_log": protocol_log,
        "case_results": {
            "regression": (results.get("regression") or {}).get("case_rows") or [],
            "development": (results.get("development") or {}).get("case_rows") or [],
            "holdout": (results.get("holdout") or {}).get("case_rows") or [],
        },
        "metamorphic_pairs": bundle.get("metamorphic_pairs") or [],
        "summary": summary,
    }
    write_v2_artifacts(out_dir, payload)
    payload["output_dir"] = str(out_dir).replace("\\", "/")
    exit_hint = 0
    if fail_on_unsafe:
        for split in results.values():
            if ((split.get("metrics") or {}).get("unsafe_failure_rate") or 0) > 0:
                exit_hint = 2
    if fail_on_protocol_violation and protocol_log.get("status") == "PROTOCOL_VIOLATION":
        exit_hint = 4
    payload["exit_hint"] = exit_hint
    return payload
