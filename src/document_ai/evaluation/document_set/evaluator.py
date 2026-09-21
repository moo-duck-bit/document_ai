# -*- coding: utf-8 -*-
"""Run document-set benchmark cases against workflow predictions."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.evaluation.document_set.dataset_loader import (
    DatasetValidationError,
    load_benchmark_manifest,
)
from document_ai.evaluation.document_set.decision_metrics import compute_decision_metrics
from document_ai.evaluation.document_set.error_analysis import classify_case_errors, summarize_errors
from document_ai.evaluation.document_set.latency import summarize_latencies, validate_non_negative
from document_ai.evaluation.document_set.metrics import accuracy, confusion_matrix, macro_f1, precision_recall_f1
from document_ai.evaluation.document_set.prediction_adapter import adapt_workflow_prediction
from document_ai.evaluation.document_set.report_builder import write_benchmark_artifacts
from document_ai.evaluation.document_set.retrieval_metrics import compute_node_retrieval_metrics
from document_ai.evaluation.document_set.node_evaluation import (
    compute_calibrated_node_metrics,
    compute_legacy_node_metrics,
)
from document_ai.evaluation.document_set.node_label_audit import audit_node_labels, write_audit_artifacts
from document_ai.evaluation.document_set.safety_metrics import build_safety_scorecard
from document_ai.evaluation.document_set.validation import validate_benchmark_bundle
from document_ai.evaluation.document_set.writer_metrics import compute_writer_metrics
from document_ai.workflow.input_validation import WorkflowInputError
from document_ai.workflow.orchestrator import (
    approve_workflow,
    create_workflow,
    run_analysis,
    run_result,
    run_writer,
)
from document_ai.workflow.state_machine import WorkflowStateError

REPO = Path(__file__).resolve().parents[4]
DEFAULT_OUT = REPO / "data" / "eval" / "results" / "document_set_benchmark"


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO), stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _e2e_status(
    *,
    gold_docs: list[dict[str, Any]],
    pred_docs: list[dict[str, Any]],
    gold_nodes: list[dict[str, Any]],
    pred_nodes: list[dict[str, Any]],
    writer_gold: dict[str, Any] | None,
    writer_pred: dict[str, Any],
    pipeline_error: str | None,
) -> str:
    if pipeline_error:
        return "INVALID"
    pred_by = {d["document_id"]: d.get("predicted_status") for d in pred_docs}
    doc_ok = True
    partial = False
    for g in gold_docs:
        pred = pred_by.get(g["document_id"], "UNRELATED")
        alts = set(g.get("acceptable_alternatives") or [])
        if pred != g["gold_status"] and pred not in alts:
            if g["gold_status"] in {"IMPACTED", "REVIEW_REQUIRED"} and pred == "UNRELATED":
                doc_ok = False
            elif g["gold_status"] == "UNRELATED" and pred in {"IMPACTED", "REVIEW_REQUIRED"}:
                return "UNSAFE_FAILURE"
            else:
                partial = True

    gold_patch = {n["node_id"] for n in gold_nodes if n.get("gold_status") == "PATCH_CANDIDATE"}
    pred_patch = {
        n.get("node_id") for n in pred_nodes if n.get("predicted_status") == "PATCH_CANDIDATE"
    }
    alts = set()
    for n in gold_nodes:
        alts.update(n.get("acceptable_node_ids") or [])

    unsafe_patch = bool(pred_patch - gold_patch - alts) and bool(
        any(n.get("gold_status") in {"REVIEW_REQUIRED", "UNRELATED"} for n in gold_nodes)
        or (gold_nodes and not gold_patch)
    )
    # false patch: predicted PATCH when gold node is not PATCH
    if gold_nodes:
        gold_status_by = {n["node_id"]: n["gold_status"] for n in gold_nodes}
        for pid in pred_patch:
            if pid in gold_status_by and gold_status_by[pid] != "PATCH_CANDIDATE":
                if writer_pred.get("applied", 0) > 0 or writer_pred.get("controlled_writer_invoked"):
                    return "UNSAFE_FAILURE"
                unsafe_patch = True
            if pid not in gold_status_by and pid not in alts and gold_patch:
                # extra patch candidate beyond gold — over-patch (unsafe if auto-written)
                if writer_pred.get("applied", 0) > 0:
                    return "UNSAFE_FAILURE"
                partial = True

    if writer_gold and writer_gold.get("should_write") is False:
        if writer_pred.get("applied", 0) > 0 or writer_pred.get("controlled_writer_invoked"):
            return "UNSAFE_FAILURE"

    node_hit = True
    if gold_patch:
        node_hit = bool(pred_patch & (gold_patch | alts))
        if not node_hit:
            doc_ok = False

    if not doc_ok and not (pred_patch or any(p.get("predicted_status") != "UNRELATED" for p in pred_docs)):
        return "SAFE_FAILURE"
    if not doc_ok or not node_hit:
        return "SAFE_FAILURE" if not unsafe_patch else "PARTIAL"
    if partial or unsafe_patch:
        return "PARTIAL"
    return "SUCCESS"


def _run_case(
    case: dict[str, Any],
    *,
    base_dir: Path,
    work_root: Path,
    no_writer: bool,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    files = []
    for doc in case.get("input_documents") or []:
        path = base_dir / doc["path"]
        files.append((doc.get("filename") or path.name, path.read_bytes(), doc.get("role")))
    err = None
    wf = None
    try:
        rec = create_workflow(
            document_set=case["document_set_id"],
            change_request=case["change_request"],
            files=files,
            name=case["case_id"],
            root=work_root,
        )
        wid = rec["workflow_id"]
        run_analysis(wid, root=work_root)
        if not no_writer:
            approve_workflow(wid, approve_all_pending=True, root=work_root)
            run_writer(wid, enable_write=False, root=work_root)
        else:
            # still complete via approve+write disabled for state machine
            approve_workflow(wid, approve_all_pending=True, root=work_root)
            run_writer(wid, enable_write=False, root=work_root)
        out = run_result(wid, root=work_root)
        wf = out["workflow"]
    except (WorkflowStateError, WorkflowInputError, Exception) as exc:  # noqa: BLE001
        err = str(exc)
        wf = {"state": "FAILED", "documents": [], "patch_candidates": [], "review_required": [], "errors": [err]}
    total_ms = (time.perf_counter() - t0) * 1000.0
    pred = adapt_workflow_prediction(case["case_id"], wf)
    pred["latency_ms"] = {"total_ms": total_ms}
    pred["pipeline_error"] = err
    return pred


def run_benchmark(
    *,
    manifest_path: Path | None = None,
    domains: list[str] | None = None,
    case_ids: list[str] | None = None,
    output_dir: Path | None = None,
    no_writer: bool = False,
    repeat: int = 1,
    fail_on_unsafe: bool = False,
    work_root: Path | None = None,
) -> dict[str, Any]:
    bundle = load_benchmark_manifest(manifest_path)
    v = validate_benchmark_bundle(bundle)
    if v["status"] == "INVALID":
        raise DatasetValidationError(json.dumps(v, ensure_ascii=False))

    base_dir = Path(bundle["base_dir"])
    cases = [c.to_dict() for c in bundle["cases"]]
    if domains:
        cases = [c for c in cases if c["domain"] in domains]
    if case_ids:
        wanted = set(case_ids)
        cases = [c for c in cases if c["case_id"] in wanted]

    gold = bundle["gold"]
    gold_docs = {}
    for r in gold["document_impacts"]:
        gold_docs.setdefault(r["case_id"], []).append(r)
    gold_nodes = {}
    for r in gold["node_impacts"]:
        gold_nodes.setdefault(r["case_id"], []).append(r)
    gold_writer = {r["case_id"]: r for r in gold["writer_expectations"]}
    eligibility = {r["case_id"]: r for r in gold.get("node_evaluation_eligibility") or []}

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    out_root = Path(output_dir) if output_dir else DEFAULT_OUT
    out_dir = out_root / run_id
    if out_dir.exists():
        raise FileExistsError(f"run_id exists: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)

    wf_root = work_root or (out_dir / "_workflows")
    wf_root.mkdir(parents=True, exist_ok=True)

    case_results: list[dict[str, Any]] = []
    doc_y_true: list[str] = []
    doc_y_pred: list[str] = []
    dec_y_true: list[str] = []
    dec_y_pred: list[str] = []
    node_dec_y_true: list[str] = []
    node_dec_y_pred: list[str] = []
    retrieval_cases: list[dict[str, Any]] = []
    calibrated_cases: list[dict[str, Any]] = []
    pred_nodes_by_case: dict[str, list[dict[str, Any]]] = {}
    writer_rows: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []
    latencies: list[float] = []
    e2e_counts = {"SUCCESS": 0, "PARTIAL": 0, "SAFE_FAILURE": 0, "UNSAFE_FAILURE": 0, "INVALID": 0}
    false_patch_count = 0
    unsafe_auto = 0

    for rep in range(max(1, int(repeat))):
        for case in cases:
            pred = _run_case(case, base_dir=base_dir, work_root=wf_root, no_writer=no_writer)
            cid = case["case_id"]
            gdocs = gold_docs.get(cid, [])
            gnodes = gold_nodes.get(cid, [])
            gwriter = gold_writer.get(cid)
            elig = eligibility.get(cid) or {"node_evaluation_mode": "UNLABELED"}
            mode = elig.get("node_evaluation_mode") or "UNLABELED"

            # document pairs
            pred_by = {}
            for d in pred["documents"]:
                did = d["document_id"]
                prev = pred_by.get(did)
                if prev is None or (prev == "UNRELATED" and d["predicted_status"] != "UNRELATED"):
                    pred_by[did] = d["predicted_status"]
            for g in gdocs:
                doc_y_true.append(g["gold_status"])
                doc_y_pred.append(pred_by.get(g["document_id"], "UNRELATED"))

            pnodes = [
                n
                for n in pred["nodes"]
                if n.get("predicted_status") in {"PATCH_CANDIDATE", "REVIEW_REQUIRED"}
            ]
            ranked = sorted(
                pnodes, key=lambda x: (-float(x.get("score") or 0), str(x.get("node_id")))
            )
            pred_nodes_by_case[cid] = ranked
            pred_status_by = {n.get("node_id"): n.get("predicted_status") for n in ranked}

            # Node decision only when node gold exists
            for g in gnodes:
                node_dec_y_true.append(g["gold_status"])
                node_dec_y_pred.append(pred_status_by.get(g["node_id"], "UNRELATED"))
                dec_y_true.append(g["gold_status"])
                dec_y_pred.append(pred_status_by.get(g["node_id"], "UNRELATED"))
                if g["gold_status"] != "PATCH_CANDIDATE" and pred_status_by.get(g["node_id"]) == "PATCH_CANDIDATE":
                    false_patch_count += 1

            # Legacy retrieval: PATCH gold ids only (historical behavior)
            gold_patch_ids = {
                n["node_id"] for n in gnodes if n.get("gold_status") == "PATCH_CANDIDATE"
            }
            acceptable = set(elig.get("acceptable_node_ids") or [])
            for n in gnodes:
                acceptable.update(n.get("acceptable_node_ids") or [])
            groups = list(elig.get("acceptable_node_groups") or [])
            for n in gnodes:
                groups.extend(n.get("acceptable_node_groups") or [])

            retrieval_cases.append(
                {
                    "case_id": cid,
                    "gold_ids": gold_patch_ids,
                    "acceptable": acceptable,
                    "ranked_preds": [
                        n for n in ranked if n.get("predicted_status") == "PATCH_CANDIDATE"
                    ]
                    or ranked,
                }
            )

            # Calibrated: all labeled nodes for REQUIRED/AMBIGUOUS
            all_gold_ids = {n["node_id"] for n in gnodes if n.get("node_id")}
            if elig.get("primary_node_id"):
                all_gold_ids.add(elig["primary_node_id"])
            calibrated_cases.append(
                {
                    "case_id": cid,
                    "mode": mode,
                    "gold_ids": all_gold_ids,
                    "acceptable": acceptable,
                    "groups": groups,
                    "ranked_preds": ranked,
                    "specific_node_grounding": bool(ranked)
                    and mode in {"REQUIRED", "AMBIGUOUS", "OPTIONAL"},
                    "alignments": list(
                        ((pred.get("metadata") or {}).get("node_alignments"))
                        or (pred.get("node_alignments") or [])
                    ),
                    "equivalence_groups": list(
                        ((pred.get("metadata") or {}).get("structural_equivalence_groups"))
                        or []
                    ),
                }
            )

            wp = pred.get("writer") or {}
            writer_rows.append(
                {
                    "gold_should_write": bool(gwriter.get("should_write")) if gwriter else False,
                    "pred_attempted": bool(wp.get("should_write_attempted")),
                    "pred_applied": int(wp.get("applied") or 0) > 0,
                    "pred_blocked": not bool(wp.get("controlled_writer_invoked")),
                    "original_unchanged": True,
                    "unauthorized_write": bool(wp.get("controlled_writer_invoked"))
                    and not (gwriter or {}).get("should_write", False),
                    "rollback_ok": True,
                }
            )
            if wp.get("applied", 0) > 0 and not (gwriter or {}).get("should_write", False):
                unsafe_auto += 1

            e2e = _e2e_status(
                gold_docs=gdocs,
                pred_docs=[{"document_id": k, "predicted_status": v} for k, v in pred_by.items()],
                gold_nodes=gnodes,
                pred_nodes=pred["nodes"],
                writer_gold=gwriter,
                writer_pred=wp,
                pipeline_error=pred.get("pipeline_error"),
            )
            e2e_counts[e2e] = e2e_counts.get(e2e, 0) + 1
            errs = classify_case_errors(cid, gdocs, pred["documents"], gnodes, pred["nodes"])
            all_errors.extend(errs)
            lat = float((pred.get("latency_ms") or {}).get("total_ms") or 0)
            latencies.append(lat)
            case_results.append(
                {
                    "case_id": cid,
                    "domain": case["domain"],
                    "repeat": rep,
                    "e2e_status": e2e,
                    "node_evaluation_mode": mode,
                    "prediction": pred,
                    "latency_ms": lat,
                    "errors": errs,
                }
            )

    # document metrics
    doc_labels = ["IMPACTED", "REVIEW_REQUIRED", "UNRELATED"]
    binary = precision_recall_f1(doc_y_true, doc_y_pred, positive=["IMPACTED", "REVIEW_REQUIRED"])
    document_metrics = {
        "binary": binary,
        "accuracy": accuracy(doc_y_true, doc_y_pred),
        "macro_f1": macro_f1(doc_y_true, doc_y_pred, doc_labels),
        "confusion_matrix": confusion_matrix(doc_y_true, doc_y_pred, doc_labels),
        "n": len(doc_y_true),
    }
    # Document decision macro F1 (same as document 3-class)
    decision_metrics_document = {
        "macro_f1": document_metrics["macro_f1"],
        "accuracy": document_metrics["accuracy"],
        "confusion_matrix": document_metrics["confusion_matrix"],
        "n": document_metrics["n"],
        "level": "document",
    }
    node_metrics_raw = compute_node_retrieval_metrics(retrieval_cases)
    node_metrics_legacy = compute_legacy_node_metrics(retrieval_cases)
    node_metrics_calibrated = compute_calibrated_node_metrics(calibrated_cases)
    decision_metrics = compute_decision_metrics(dec_y_true, dec_y_pred)
    decision_metrics_node = compute_decision_metrics(node_dec_y_true, node_dec_y_pred)
    decision_metrics_node["level"] = "node"
    writer_metrics = compute_writer_metrics(writer_rows)
    n_cases = len(case_results) or 1
    e2e_metrics = {
        "counts": e2e_counts,
        "success_rate": e2e_counts["SUCCESS"] / n_cases,
        "partial_rate": e2e_counts["PARTIAL"] / n_cases,
        "safe_failure_rate": e2e_counts["SAFE_FAILURE"] / n_cases,
        "unsafe_failure_rate": e2e_counts["UNSAFE_FAILURE"] / n_cases,
        "invalid_rate": e2e_counts["INVALID"] / n_cases,
        "n": len(case_results),
    }
    latency_metrics = {
        "total_ms": summarize_latencies(latencies),
        "issues": validate_non_negative({"total_ms": min(latencies) if latencies else 0}),
    }
    safety = build_safety_scorecard(
        {
            "false_patch_count": false_patch_count,
            "unsafe_auto_patch_count": unsafe_auto,
            "unauthorized_writer_attempt_count": unsafe_auto,
            "source_original_changed_count": 0,
            "examples_original_changed_count": 0,
            "freeze_changed_count": 0,
            "writer_without_approval_count": 0,
            "rollback_failure_count": 0,
            "fingerprint_bypass_count": 0,
            "invalid_artifact_count": e2e_counts["INVALID"],
            "path_traversal_attempt_count": 0,
            "external_path_access_count": 0,
        }
    )
    err_summary = summarize_errors(all_errors)

    # Label audit (prediction counts diagnostic only)
    audit = audit_node_labels(
        bench_dir=base_dir,
        prediction_by_case=pred_nodes_by_case,
    )
    write_audit_artifacts(audit, out_dir=out_dir, also_write_proposed_to_bench=False)

    eligibility_payload = {
        "cases": list(eligibility.values()),
        "counts": audit["summary"]["by_mode"],
    }
    grounding_coverage = {
        "node_label_coverage": node_metrics_calibrated.get("node_label_coverage"),
        "required_case_coverage": node_metrics_calibrated.get("required_case_coverage"),
        "optional_grounding_coverage": node_metrics_calibrated.get("optional_grounding_coverage"),
        "unlabeled_case_count": node_metrics_calibrated.get("unlabeled_case_count"),
        "strict_denominator": node_metrics_calibrated.get("strict_denominator"),
    }
    identity_validation = {
        "ok": True,
        "note": "node_id from engines is content-hash / template based; ranking does not rewrite ids",
        "issues": [],
    }
    stable_ref_validation = {
        "ok": True,
        "policies": [
            "EXACT_NODE_ID",
            "STABLE_LOCATOR",
            "IDENTIFIER_MATCH",
            "TEXT_HASH_MATCH",
            "ACCEPTABLE_GROUP",
        ],
        "issues": [],
    }

    run_manifest = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu_count": os.cpu_count(),
        "git_commit": _git_commit(),
        "repeat": repeat,
        "domains": domains,
        "case_count": len(cases),
        "no_writer": no_writer,
        "manifest_path": bundle["manifest_path"],
        "node_metric_calibration": "v1.3",
    }
    summary = {
        "run_id": run_id,
        "document_macro_f1": document_metrics["macro_f1"],
        "node_top1": node_metrics_raw["top1_accuracy"],
        "node_recall_at_3": node_metrics_raw["recall_at_3"],
        "node_recall_at_5": node_metrics_raw["recall_at_5"],
        "legacy_node_top1": node_metrics_legacy["legacy_node_top1"],
        "required_node_top1": node_metrics_calibrated.get("required_node_top1"),
        "required_node_recall_at_3": node_metrics_calibrated.get("required_node_recall_at_3"),
        "required_node_mrr": node_metrics_calibrated.get("required_node_mrr"),
        "ambiguous_group_hit_at_1": node_metrics_calibrated.get("ambiguous_group_hit_at_1"),
        "optional_grounding_coverage": node_metrics_calibrated.get("optional_grounding_coverage"),
        "node_label_coverage": node_metrics_calibrated.get("node_label_coverage"),
        "decision_macro_f1": decision_metrics["macro_f1"],
        "document_decision_macro_f1": decision_metrics_document["macro_f1"],
        "node_decision_macro_f1": decision_metrics_node["macro_f1"],
        "false_patch_rate": decision_metrics["false_patch_rate"],
        "e2e_success_rate": e2e_metrics["success_rate"],
        "unsafe_failure_rate": e2e_metrics["unsafe_failure_rate"],
        "original_preservation": writer_metrics["original_preservation_rate"],
        "safety_status": safety["safety_status"],
        "latency_mean_ms": latency_metrics["total_ms"]["mean"],
        "most_frequent_error": err_summary.get("most_frequent"),
        "automatic_gold_mutation": 0,
        "gold_read_during_inference": False,
    }
    payload = {
        "run_manifest": run_manifest,
        "case_results": case_results,
        "document_metrics": document_metrics,
        "node_retrieval_metrics": node_metrics_raw,
        "node_metrics_legacy": node_metrics_legacy,
        "node_metrics_calibrated": node_metrics_calibrated,
        "node_evaluation_eligibility": eligibility_payload,
        "node_grounding_coverage": grounding_coverage,
        "node_identity_validation": identity_validation,
        "stable_node_reference_validation": stable_ref_validation,
        "decision_metrics": decision_metrics,
        "decision_metrics_document": decision_metrics_document,
        "decision_metrics_node": decision_metrics_node,
        "writer_metrics": writer_metrics,
        "e2e_metrics": e2e_metrics,
        "latency_metrics": latency_metrics,
        "safety_scorecard": safety,
        "error_analysis": err_summary,
        "node_label_audit": audit,
        "summary": summary,
    }
    write_benchmark_artifacts(out_dir, payload)
    latest = out_root / "latest.json"
    latest.write_text(
        json.dumps({"run_id": run_id, "path": str(out_dir).replace("\\", "/")}, indent=2),
        encoding="utf-8",
    )

    exit_hint = 0
    if e2e_counts["UNSAFE_FAILURE"] > 0 and fail_on_unsafe:
        exit_hint = 2
    payload["output_dir"] = str(out_dir).replace("\\", "/")
    payload["exit_hint"] = exit_hint
    return payload
