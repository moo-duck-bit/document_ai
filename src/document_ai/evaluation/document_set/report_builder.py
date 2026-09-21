# -*- coding: utf-8 -*-
"""Build markdown and JSON benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_benchmark_artifacts(out_dir: Path, payload: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "run_manifest.json": payload.get("run_manifest"),
        "document_metrics.json": payload.get("document_metrics"),
        "node_retrieval_metrics.json": payload.get("node_retrieval_metrics"),
        "node_metrics_legacy.json": payload.get("node_metrics_legacy"),
        "node_metrics_calibrated.json": payload.get("node_metrics_calibrated"),
        "node_evaluation_eligibility.json": payload.get("node_evaluation_eligibility"),
        "node_grounding_coverage.json": payload.get("node_grounding_coverage"),
        "node_identity_validation.json": payload.get("node_identity_validation"),
        "stable_node_reference_validation.json": payload.get("stable_node_reference_validation"),
        "decision_metrics.json": payload.get("decision_metrics"),
        "decision_metrics_document.json": payload.get("decision_metrics_document"),
        "decision_metrics_node.json": payload.get("decision_metrics_node"),
        "writer_metrics.json": payload.get("writer_metrics"),
        "e2e_metrics.json": payload.get("e2e_metrics"),
        "latency_metrics.json": payload.get("latency_metrics"),
        "safety_scorecard.json": payload.get("safety_scorecard"),
        "error_analysis.json": payload.get("error_analysis"),
        "benchmark_summary.json": payload.get("summary"),
    }
    for name, obj in files.items():
        if obj is None:
            continue
        (out_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    case_path = out_dir / "case_results.jsonl"
    with case_path.open("w", encoding="utf-8") as f:
        for row in payload.get("case_results") or []:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    md = build_markdown_report(payload)
    (out_dir / "BENCHMARK_REPORT.md").write_text(md, encoding="utf-8")
    return out_dir


def build_markdown_report(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    dm = payload.get("document_metrics") or {}
    nm = payload.get("node_retrieval_metrics") or {}
    cal = payload.get("node_metrics_calibrated") or {}
    dec = payload.get("decision_metrics") or {}
    e2e = payload.get("e2e_metrics") or {}
    lat = payload.get("latency_metrics") or {}
    safe = payload.get("safety_scorecard") or {}
    lines = [
        "# Document Set Benchmark Report",
        "",
        f"Run ID: `{s.get('run_id')}`",
        "",
        "## Document / E2E",
        "",
        f"- Document Macro F1: {dm.get('macro_f1', 0):.4f}",
        f"- E2E Success Rate: {e2e.get('success_rate', 0):.4f}",
        f"- False Patch Rate: {dec.get('false_patch_rate', 0):.4f}",
        f"- Unsafe Failure Rate: {e2e.get('unsafe_failure_rate', 0):.4f}",
        "",
        "## Legacy Node Metrics",
        "",
        f"- Node Top-1: {nm.get('top1_accuracy', 0):.4f}",
        f"- Recall@3: {nm.get('recall_at_3', 0):.4f}",
        f"- MRR: {nm.get('mrr', s.get('legacy_mrr', 0)):.4f}",
        "",
        "## Calibrated Node Metrics",
        "",
        f"- Required Top-1: {cal.get('required_node_top1', 0):.4f}",
        f"- Required Recall@3: {cal.get('required_node_recall_at_3', 0):.4f}",
        f"- Required MRR: {cal.get('required_node_mrr', 0):.4f}",
        f"- Ambiguous Group Hit@1: {cal.get('ambiguous_group_hit_at_1', 0):.4f}",
        f"- Optional Grounding Coverage: {cal.get('optional_grounding_coverage', 0):.4f}",
        f"- Node Label Coverage: {cal.get('node_label_coverage', 0):.4f}",
        "",
        "## Safety",
        "",
        f"- Status: {safe.get('safety_status')}",
        "",
        f"- Latency mean ms: {lat.get('total_ms', {}).get('mean', 0):.1f}",
        "",
    ]
    return "\n".join(lines)
