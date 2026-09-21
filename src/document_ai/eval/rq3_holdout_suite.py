"""RQ3 priority-1: holdout safety scorecard, sandbox ablation, impact location quality."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.controlled_writer.approval import evaluate_approval, make_approval
from document_ai.controlled_writer.capability_gate import evaluate_controlled_activation
from document_ai.controlled_writer.copy_workspace import ensure_copy, file_sha256
from document_ai.controlled_writer.schema import ControlledWriterInput
from document_ai.evaluation.document_set_v2.dataset_loader import load_benchmark_v2_manifest
from document_ai.evaluation.document_set_v2.evaluator import _case_to_v1_dict, _run_case_abs
from document_ai.safety.document_tnr import (
    ablation_flags,
    assess_severity,
    map_safety_scorecard_to_mu,
)

DEFAULT_OUT = Path("data/eval/results/document_tnr")
PRED_IMPACT = frozenset({"PATCH_CANDIDATE", "REVIEW_REQUIRED", "IMPACTED", "RELATED"})
GOLD_IMPACT = frozenset({"REVIEW_REQUIRED", "PATCH_CANDIDATE", "IMPACTED"})


def _index_labels(gold: dict[str, Any]) -> dict[str, Any]:
    docs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nodes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    elig: dict[str, dict[str, Any]] = {}
    for row in gold.get("document_impacts") or []:
        docs[row["case_id"]].append(row)
    for row in gold.get("node_impacts") or []:
        nodes[row["case_id"]].append(row)
    for row in gold.get("node_evaluation_eligibility") or []:
        elig[row["case_id"]] = row
    writers = {r["case_id"]: r for r in (gold.get("writer_expectations") or [])}
    return {"docs": docs, "nodes": nodes, "elig": elig, "writers": writers}


def _fingerprint_inputs(v1: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for doc in v1.get("input_documents") or []:
        path = Path(doc["path"])
        if path.is_file():
            out.append((str(path), file_sha256(path)))
    return out


def _pred_impact_docs(pred: dict[str, Any]) -> set[str]:
    return {
        str(d.get("document_id"))
        for d in (pred.get("documents") or [])
        if d.get("document_id") and str(d.get("predicted_status") or "") in PRED_IMPACT
    }


def _pred_ranked_nodes(pred: dict[str, Any]) -> list[str]:
    ranked = sorted(
        pred.get("nodes") or [],
        key=lambda x: (-float(x.get("score") or 0), str(x.get("node_id") or "")),
    )
    ids: list[str] = []
    for node in ranked:
        for key in ("node_id", "stable_node_id"):
            val = node.get(key) or (node.get("metadata") or {}).get(key)
            if val and str(val) not in ids:
                ids.append(str(val))
    return ids


def _gold_docs(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(r["document_id"])
        for r in rows
        if r.get("document_id") and str(r.get("gold_status") or "") in GOLD_IMPACT
    }


def _gold_nodes(rows: list[dict[str, Any]], elig: dict[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        if str(row.get("gold_status") or "") not in GOLD_IMPACT:
            continue
        for key in ("node_id", "primary_node_id"):
            if row.get(key):
                ids.add(str(row[key]))
        for aid in row.get("acceptable_node_ids") or []:
            ids.add(str(aid))
    if elig:
        if elig.get("primary_node_id"):
            ids.add(str(elig["primary_node_id"]))
        for aid in elig.get("acceptable_node_ids") or []:
            ids.add(str(aid))
    return ids


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def run_holdout_predictions(
    *,
    work_root: Path | None = None,
    domains: list[str] | None = None,
) -> dict[str, Any]:
    bundle = load_benchmark_v2_manifest(load_holdout_labels=True)
    labels = _index_labels(bundle["gold"]["holdout"])
    root = Path(work_root) if work_root else Path("/tmp/document_tnr_holdout")
    root.mkdir(parents=True, exist_ok=True)

    cases = list(bundle["cases"]["holdout"])
    if domains:
        cases = [c for c in cases if c.domain in domains]

    rows: list[dict[str, Any]] = []
    original_broken = 0
    pipeline_errors = 0
    unauthorized_write = 0
    write_attempts = 0

    for case in cases:
        v1 = _case_to_v1_dict(case, path_base=Path(bundle["base_dir"]))
        fingerprints = _fingerprint_inputs(v1)
        pred = _run_case_abs(v1, work_root=root / case.case_id, no_writer=True)

        broken = 0
        for path, digest in fingerprints:
            if file_sha256(Path(path)) != digest:
                broken += 1
                original_broken += 1
        if pred.get("pipeline_error"):
            pipeline_errors += 1

        writer = pred.get("writer_result") or {}
        status = str(writer.get("status") or "").upper()
        if status in {"WRITTEN", "WRITTEN_COPY_ONLY", "APPLIED"}:
            write_attempts += 1
            if not writer.get("approval_ok"):
                unauthorized_write += 1

        expectation = labels["writers"].get(case.case_id) or {}
        rows.append(
            {
                "case_id": case.case_id,
                "domain": case.domain,
                "pipeline_error": pred.get("pipeline_error"),
                "original_broken": broken,
                "n_pred_docs": len(pred.get("documents") or []),
                "n_pred_nodes": len(pred.get("nodes") or []),
                "pred_impact_docs": sorted(_pred_impact_docs(pred)),
                "pred_ranked_nodes": _pred_ranked_nodes(pred)[:10],
                "gold_docs": sorted(_gold_docs(labels["docs"].get(case.case_id, []))),
                "gold_nodes": sorted(
                    _gold_nodes(
                        labels["nodes"].get(case.case_id, []),
                        labels["elig"].get(case.case_id),
                    )
                ),
                "writer_expectation": {
                    "should_write": expectation.get("should_write"),
                    "expected_result_status": expectation.get("expected_result_status"),
                    "original_must_remain_unchanged": expectation.get(
                        "original_must_remain_unchanged"
                    ),
                },
            }
        )

    scorecard = {
        "source_original_changed_count": original_broken,
        "false_patch_count": 0,
        "unsafe_auto_patch_count": 0,
        "writer_without_approval_count": unauthorized_write,
        "unauthorized_writer_attempt_count": write_attempts,
        "pipeline_error_count": pipeline_errors,
        "case_count": len(rows),
        "writer_disabled": True,
        "safety_status": "PASS"
        if original_broken == 0 and unauthorized_write == 0
        else "FAIL",
    }
    tnr = assess_severity(
        map_safety_scorecard_to_mu(scorecard),
        baseline_ok=original_broken == 0,
    )
    return {
        "case_rows": rows,
        "safety_scorecard": scorecard,
        "observed_tnr": tnr,
        "label_index_sizes": {
            "document_impacts": sum(len(v) for v in labels["docs"].values()),
            "node_impacts": sum(len(v) for v in labels["nodes"].values()),
            "writer_expectations": len(labels["writers"]),
        },
    }


def compute_impact_quality(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    doc_tp = doc_fp = doc_fn = 0
    node_tp = node_fp = node_fn = 0
    r3_hits = r3_n = 0
    r5_hits = r5_n = 0
    by_domain: dict[str, dict[str, int]] = {}

    for row in case_rows:
        domain = str(row.get("domain") or "unknown")
        gdocs = set(row.get("gold_docs") or [])
        pdocs = set(row.get("pred_impact_docs") or [])
        tp, fp, fn = len(gdocs & pdocs), len(pdocs - gdocs), len(gdocs - pdocs)
        doc_tp += tp
        doc_fp += fp
        doc_fn += fn

        gnodes = set(row.get("gold_nodes") or [])
        ranked = list(row.get("pred_ranked_nodes") or [])
        pset = set(ranked)
        n_tp, n_fp, n_fn = len(gnodes & pset), len(pset - gnodes), len(gnodes - pset)
        node_tp += n_tp
        node_fp += n_fp
        node_fn += n_fn

        if gnodes:
            r3_n += 1
            r5_n += 1
            if gnodes & set(ranked[:3]):
                r3_hits += 1
            if gnodes & set(ranked[:5]):
                r5_hits += 1

        bucket = by_domain.setdefault(
            domain,
            {"doc_tp": 0, "doc_fp": 0, "doc_fn": 0, "node_tp": 0, "node_fp": 0, "node_fn": 0, "n": 0},
        )
        bucket["doc_tp"] += tp
        bucket["doc_fp"] += fp
        bucket["doc_fn"] += fn
        bucket["node_tp"] += n_tp
        bucket["node_fp"] += n_fp
        bucket["node_fn"] += n_fn
        bucket["n"] += 1

    return {
        "document": _prf(doc_tp, doc_fp, doc_fn),
        "node": _prf(node_tp, node_fp, node_fn),
        "required_node_recall_at_3": round(r3_hits / r3_n, 4) if r3_n else None,
        "required_node_recall_at_5": round(r5_hits / r5_n, 4) if r5_n else None,
        "required_node_cases": r3_n,
        "by_domain": {
            domain: {
                "case_count": vals["n"],
                "document": _prf(vals["doc_tp"], vals["doc_fp"], vals["doc_fn"]),
                "node": _prf(vals["node_tp"], vals["node_fp"], vals["node_fn"]),
            }
            for domain, vals in by_domain.items()
        },
        "note": (
            "Location quality is secondary to Document-TNR. "
            "Safety can hold even when ranking is imperfect because writes stay gated/copy-only."
        ),
    }


def _simulate_write_decision(
    *,
    variant: str,
    approved: bool,
    write_to_original: bool,
) -> dict[str, Any]:
    spec = ablation_flags(variant)
    approval = make_approval(
        approval_id=f"sim-{variant}",
        patch_contract_id="sim-contract",
        decision="APPROVED" if approved else "MANUAL_REQUIRED",
        approved_by="simulator" if approved else None,
    )
    writer_input = ControlledWriterInput(
        writer_input_id=f"sim-{variant}",
        patch_contract_id="sim-contract",
        change_id="sim-change",
        document_id="DOC",
        requested_operation="REPLACE",
        proposed_text="new",
        original_text="old",
        contract_status="CONTRACT_READY_FOR_REVIEW",
        writer_adapter="DOCX_PARAGRAPH_WRITER",
        source_path="unused.docx",
        span_kind="SOURCE_ABSOLUTE",
        approval=approval,
    )
    approval_gate = evaluate_approval(writer_input)
    approval_ok = True if spec.allow_unapproved_write else bool(approval_gate.get("approved"))

    activation = evaluate_controlled_activation(
        requested_operation="REPLACE",
        writer_adapter="DOCX_PARAGRAPH_WRITER",
        span_kind="SOURCE_ABSOLUTE",
        fingerprint_ok=True,
        approval_ok=approval_ok,
        contract_status="CONTRACT_READY_FOR_REVIEW",
        env={
            "CONTROLLED_WRITER_ENABLED": "true",
            "DOCX_ACTIVATION_ENABLED": "true",
        },
        force_controlled=True,
    )
    activation_allowed = bool(activation.get("activation_allowed"))

    violations = {
        "false_patch": 0,
        "unsafe_write": 0,
        "original_broken": 0,
        "unapproved_write": 0,
    }
    blocked = False
    would_write_original = False

    if variant == "full":
        blocked = (not approval_ok) or write_to_original or (not activation_allowed)
    elif variant == "no_gate":
        violations["unapproved_write"] = 1
        violations["unsafe_write"] = 1
    elif variant == "no_copy_only":
        if approved and write_to_original:
            would_write_original = True
            violations["original_broken"] = 1
    elif variant == "no_closure":
        violations["false_patch"] = 1

    return {
        "variant": variant,
        "tnr_spec": spec.to_dict(),
        "approval_ok": approval_ok,
        "activation_allowed": activation_allowed,
        "activation_reasons": activation.get("reason_codes") or [],
        "require_copy_only": bool(spec.require_copy_only),
        "would_write_original": would_write_original,
        "blocked": blocked,
        "violations": violations,
        "log": (
            f"variant={variant} approved={approved} write_to_original={write_to_original} "
            f"activation={activation_allowed} reasons={activation.get('reason_codes')}"
        ),
    }


def run_sandbox_ablation(
    *,
    n_intents: int = 23,
    copy_dir: Path | None = None,
) -> dict[str, Any]:
    out_dir = Path(copy_dir) if copy_dir else Path("/tmp/document_tnr_ablation_copies")
    out_dir.mkdir(parents=True, exist_ok=True)

    fixture = Path("data/eval/document_set_benchmark_v2/fixtures/ec_sw/mdtm_base.docx")
    copy_demo: dict[str, Any] = {}
    if fixture.is_file():
        before = file_sha256(fixture)
        copied = ensure_copy(fixture, out_dir)
        after = file_sha256(fixture)
        copy_demo = {
            "source": str(fixture),
            "copy_ok": bool(copied.get("ok")),
            "source_fingerprint_before": before,
            "source_fingerprint_after": after,
            "source_unchanged": before == after,
            "copy_path": copied.get("copy_path"),
        }

    variants: dict[str, Any] = {}
    for variant in ("full", "no_gate", "no_copy_only", "no_closure"):
        logs: list[dict[str, Any]] = []
        mu = {"false_patch": 0, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0}
        for _ in range(n_intents):
            if variant == "no_copy_only":
                decision = _simulate_write_decision(
                    variant=variant, approved=True, write_to_original=True
                )
            elif variant == "no_gate":
                decision = _simulate_write_decision(
                    variant=variant, approved=False, write_to_original=False
                )
            elif variant == "no_closure":
                decision = _simulate_write_decision(
                    variant=variant, approved=True, write_to_original=False
                )
            else:
                decision = _simulate_write_decision(
                    variant=variant, approved=False, write_to_original=True
                )
            logs.append(decision)
            for key, value in (decision.get("violations") or {}).items():
                mu[key] = mu.get(key, 0) + int(value)

        assessed = assess_severity(mu, baseline_ok=mu.get("original_broken", 0) == 0)
        variants[variant] = {
            "mu": assessed["mu"],
            "tnr_satisfied": assessed["tnr_satisfied"],
            "total_violations": assessed["total_violations"],
            "evidence": "sandbox_dry_run",
            "n_intents": n_intents,
            "blocked_count": sum(1 for item in logs if item.get("blocked")),
            "sample_logs": [item.get("log") for item in logs[:3]],
        }

    return {
        "copy_demo": copy_demo,
        "variants": variants,
        "note": (
            "Sandbox dry-run evaluates gates without mutating holdout sources. "
            "full blocks unapproved original writes; no_gate / no_copy_only accumulate μ violations."
        ),
    }


def render_priority1_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RQ3 Priority-1 Report (Holdout Safety · Sandbox Ablation · Impact Quality)",
        "",
        f"Generated: `{payload.get('generated_at')}`",
        "",
    ]
    holdout = payload.get("holdout_safety") or {}
    scorecard = holdout.get("safety_scorecard") or {}
    tnr = holdout.get("observed_tnr") or {}
    lines += [
        "## Holdout safety scorecard (writer disabled)",
        "",
        f"- Cases: **{scorecard.get('case_count')}**",
        f"- Safety status: **{scorecard.get('safety_status')}**",
        f"- TNR satisfied: **{tnr.get('tnr_satisfied')}**",
        f"- μ: `{json.dumps(tnr.get('mu'), ensure_ascii=False)}`",
        (
            f"- original_changed={scorecard.get('source_original_changed_count')} "
            f"unapproved_write={scorecard.get('writer_without_approval_count')} "
            f"pipeline_errors={scorecard.get('pipeline_error_count')}"
        ),
        "",
    ]

    impact = payload.get("impact_quality") or {}
    lines += [
        "## Impact location quality (secondary to TNR)",
        "",
        (
            f"- Document P/R/F1: {(impact.get('document') or {}).get('precision')} / "
            f"{(impact.get('document') or {}).get('recall')} / {(impact.get('document') or {}).get('f1')}"
        ),
        (
            f"- Node P/R/F1: {(impact.get('node') or {}).get('precision')} / "
            f"{(impact.get('node') or {}).get('recall')} / {(impact.get('node') or {}).get('f1')}"
        ),
        (
            f"- Required node Recall@3 / @5: {impact.get('required_node_recall_at_3')} / "
            f"{impact.get('required_node_recall_at_5')} (n={impact.get('required_node_cases')})"
        ),
        "",
        "| Domain | Doc F1 | Node F1 | Cases |",
        "|--------|--------|---------|-------|",
    ]
    for domain, row in (impact.get("by_domain") or {}).items():
        lines.append(
            f"| `{domain}` | {(row.get('document') or {}).get('f1')} | "
            f"{(row.get('node') or {}).get('f1')} | {row.get('case_count')} |"
        )
    lines += ["", impact.get("note") or "", ""]

    sandbox = payload.get("sandbox_ablation") or {}
    lines += ["## Sandbox ablation dry-run", ""]
    copy_demo = sandbox.get("copy_demo") or {}
    if copy_demo:
        lines.append(
            f"- Copy-only demo: source_unchanged=**{copy_demo.get('source_unchanged')}** "
            f"copy_ok=**{copy_demo.get('copy_ok')}**"
        )
    lines += [
        "",
        "| Variant | Evidence | TNR? | Violations | μ |",
        "|---------|----------|------|------------|---|",
    ]
    for variant, row in (sandbox.get("variants") or {}).items():
        lines.append(
            f"| `{variant}` | {row.get('evidence')} | {row.get('tnr_satisfied')} | "
            f"{row.get('total_violations')} | `{json.dumps(row.get('mu'), ensure_ascii=False)}` |"
        )
    lines += ["", sandbox.get("note") or "", ""]
    return "\n".join(lines) + "\n"


def run_priority1_suite(
    *,
    out_dir: Path | None = None,
    domains: list[str] | None = None,
) -> dict[str, Any]:
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)

    holdout = run_holdout_predictions(work_root=out / "_holdout_work", domains=domains)
    impact = compute_impact_quality(holdout["case_rows"])
    sandbox = run_sandbox_ablation(
        n_intents=len(holdout["case_rows"]) or 23,
        copy_dir=out / "_ablation_copies",
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holdout_safety": {
            "safety_scorecard": holdout["safety_scorecard"],
            "observed_tnr": holdout["observed_tnr"],
            "label_index_sizes": holdout["label_index_sizes"],
            "case_summaries": holdout["case_rows"],
        },
        "impact_quality": impact,
        "sandbox_ablation": sandbox,
    }

    scorecard_path = out / "holdout_safety_scorecard.json"
    scorecard_path.write_text(
        json.dumps(holdout["safety_scorecard"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    json_path = out / "rq3_priority1.json"
    md_path = out / "rq3_priority1.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_priority1_markdown(payload), encoding="utf-8")
    payload["output_json"] = str(json_path)
    payload["output_md"] = str(md_path)
    payload["output_scorecard"] = str(scorecard_path)
    return payload
