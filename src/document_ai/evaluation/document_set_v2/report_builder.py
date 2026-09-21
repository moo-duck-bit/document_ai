# -*- coding: utf-8 -*-
"""Write Benchmark v2 artifacts + markdown report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_v2_artifacts(out_dir: Path, payload: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "run_manifest.json": payload.get("run_manifest"),
        "dataset_validation.json": payload.get("dataset_validation"),
        "split_summary.json": payload.get("split_summary"),
        "regression_metrics.json": payload.get("regression_metrics"),
        "development_metrics.json": payload.get("development_metrics"),
        "holdout_metrics.json": payload.get("holdout_metrics"),
        "domain_metrics.json": payload.get("domain_metrics"),
        "cycle5_generalization_summary.json": payload.get("cycle5_generalization_summary"),
        "business_proposal_node_metrics.json": payload.get("business_proposal_node_metrics"),
        "business_proposal_official_node_metrics.json": payload.get("business_proposal_official_node_metrics"),
        "business_proposal_proxy_metrics.json": payload.get("business_proposal_proxy_metrics"),
        "business_proposal_label_coverage.json": payload.get("business_proposal_label_coverage"),
        "business_proposal_label_agreement.json": payload.get("business_proposal_label_agreement"),
        "business_proposal_node_errors.json": payload.get("business_proposal_node_errors"),
        "business_proposal_node_evaluation_summary.json": payload.get("business_proposal_node_evaluation_summary"),
        "business_proposal_blind_evaluation_manifest.json": payload.get(
            "business_proposal_blind_evaluation_manifest"
        ),
        "cycle6_generalization_summary.json": payload.get("cycle6_generalization_summary"),
        "generalization_gap.json": payload.get("generalization_gap"),
        "robustness_metrics.json": payload.get("robustness_metrics"),
        "identity_metrics.json": payload.get("identity_metrics"),
        "pack_routing_metrics.json": payload.get("pack_routing_metrics"),
        "document_id_alignment_metrics.json": payload.get("document_id_alignment_metrics"),
        "table_structure_identity_robustness.json": payload.get("table_structure_identity_robustness"),
        "stable_node_v2_metrics.json": payload.get("stable_node_v2_metrics"),
        "logical_base_match_metrics.json": payload.get("logical_base_match_metrics"),
        "instance_match_metrics.json": payload.get("instance_match_metrics"),
        "duplicate_instance_metrics.json": payload.get("duplicate_instance_metrics"),
        "generic_node_ranking_metrics.json": payload.get("generic_node_ranking_metrics"),
        "cycle4_generalization_summary.json": payload.get("cycle4_generalization_summary"),
        "table_variant_identity_metrics.json": payload.get("table_variant_identity_metrics"),
        "safe_generalization_cycle3_summary.json": payload.get("safe_generalization_cycle3_summary"),
        "calibration_metrics.json": payload.get("calibration_metrics"),
        "format_preservation_metrics.json": payload.get("format_preservation_metrics"),
        "safety_scorecard.json": payload.get("safety_scorecard"),
        "benchmark_summary.json": payload.get("summary"),
        "error_analysis.json": payload.get("error_analysis") or {"note": "see case_results"},
        "human_review_summary.json": payload.get("human_review_summary")
        or {"status": "FORMS_READY", "path": "data/eval/document_set_benchmark_v2/human_review/"},
    }
    for name, obj in files.items():
        if obj is None:
            continue
        (out_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # jsonl dumps
    cases = payload.get("case_results") or {}
    for split, rows in cases.items():
        path = out_dir / f"{split}_results.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if cases.get("holdout"):
        # evaluation view after unseal
        with (out_dir / "holdout_evaluation.jsonl").open("w", encoding="utf-8") as f:
            for row in cases["holdout"]:
                f.write(
                    json.dumps(
                        {
                            "case_id": row.get("case_id"),
                            "e2e_status": row.get("e2e_status"),
                            "node_evaluation_mode": row.get("node_evaluation_mode"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    meta_pairs = payload.get("metamorphic_pairs") or []
    with (out_dir / "metamorphic_results.jsonl").open("w", encoding="utf-8") as f:
        for p in meta_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    (out_dir / "BENCHMARK_V2_REPORT.md").write_text(build_v2_markdown(payload), encoding="utf-8")
    return out_dir


def build_v2_markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    reg = s.get("regression") or {}
    dev = s.get("development") or {}
    hol = s.get("holdout") or {}
    gap = s.get("generalization_gap") or {}
    rob = s.get("robustness") or {}
    lines = [
        "# Document Set Benchmark V2 Report",
        "",
        f"Run ID: `{s.get('run_id')}`",
        "",
        "## Split metrics",
        "",
        f"- Regression Document Macro F1: {reg.get('document_macro_f1', 0):.4f}",
        f"- Development Document Macro F1: {dev.get('document_macro_f1', 0):.4f}",
        f"- Holdout Document Macro F1: {hol.get('document_macro_f1', 0):.4f}",
        f"- Holdout Required Top-1: {hol.get('required_node_top1', 0):.4f}",
        f"- Holdout Required Recall@3: {hol.get('required_node_recall_at_3', 0):.4f}",
        f"- Holdout E2E Success: {hol.get('e2e_success_rate', 0):.4f}",
        "",
        "## Generalization gap (dev − holdout)",
        "",
        f"- Document F1 gap: {gap.get('document_macro_f1_gap', 0):.4f}",
        f"- Node Top-1 gap: {gap.get('required_node_top1_gap', 0):.4f}",
        f"- Recall@3 gap: {gap.get('required_node_recall_at_3_gap', 0):.4f}",
        f"- E2E gap: {gap.get('e2e_success_rate_gap', 0):.4f}",
        "",
        "## Robustness",
        "",
        f"- Metamorphic pass: {rob.get('metamorphic_pass_rate', 0):.4f}",
        f"- Decision consistency: {rob.get('decision_consistency_rate', 0):.4f}",
        "",
        f"Protocol: {s.get('protocol_status')}",
        "",
    ]
    return "\n".join(lines)
