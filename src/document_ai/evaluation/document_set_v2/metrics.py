# -*- coding: utf-8 -*-
"""Benchmark v2 aggregate metrics helpers."""

from __future__ import annotations

from typing import Any

from document_ai.evaluation.document_set.metrics import accuracy, confusion_matrix, macro_f1
from document_ai.evaluation.document_set.node_evaluation import compute_calibrated_node_metrics
from document_ai.evaluation.document_set.decision_metrics import compute_decision_metrics


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def summarize_split_metrics(
    *,
    doc_y_true: list[str],
    doc_y_pred: list[str],
    calibrated_cases: list[dict[str, Any]],
    e2e_statuses: list[str],
    false_patch_count: int,
    node_dec_true: list[str] | None = None,
    node_dec_pred: list[str] | None = None,
) -> dict[str, Any]:
    labels = ["IMPACTED", "REVIEW_REQUIRED", "UNRELATED"]
    n = len(e2e_statuses) or 1
    counts = {k: e2e_statuses.count(k) for k in ["SUCCESS", "PARTIAL", "SAFE_FAILURE", "UNSAFE_FAILURE", "INVALID"]}
    cal = compute_calibrated_node_metrics(calibrated_cases)
    node_dec = {}
    if node_dec_true is not None and node_dec_pred is not None:
        node_dec = compute_decision_metrics(node_dec_true, node_dec_pred)
    return {
        "document_macro_f1": macro_f1(doc_y_true, doc_y_pred, labels) if doc_y_true else 0.0,
        "document_accuracy": accuracy(doc_y_true, doc_y_pred) if doc_y_true else 0.0,
        "document_confusion": confusion_matrix(doc_y_true, doc_y_pred, labels) if doc_y_true else {},
        "required_node_top1": cal.get("required_node_top1", 0.0),
        "required_node_recall_at_3": cal.get("required_node_recall_at_3", 0.0),
        "required_node_recall_at_5": cal.get("required_node_recall_at_5", 0.0),
        "required_node_mrr": cal.get("required_node_mrr", 0.0),
        "ambiguous_group_hit_at_1": cal.get("ambiguous_group_hit_at_1", 0.0),
        "node_label_coverage": cal.get("node_label_coverage", 0.0),
        "node_decision_macro_f1": node_dec.get("macro_f1", 0.0),
        "false_patch_rate": _safe_div(false_patch_count, max(1, len(node_dec_true or []) or n)),
        "e2e_success_rate": counts.get("SUCCESS", 0) / n,
        "partial_rate": counts.get("PARTIAL", 0) / n,
        "safe_failure_rate": counts.get("SAFE_FAILURE", 0) / n,
        "unsafe_failure_rate": counts.get("UNSAFE_FAILURE", 0) / n,
        "e2e_counts": counts,
        "n_cases": len(e2e_statuses),
        "calibrated_detail": cal,
    }


def generalization_gap(dev: dict[str, Any], holdout: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "document_macro_f1",
        "required_node_top1",
        "required_node_recall_at_3",
        "e2e_success_rate",
        "node_decision_macro_f1",
    ]
    gaps = {}
    for k in keys:
        gaps[f"{k}_gap"] = float(dev.get(k) or 0) - float(holdout.get(k) or 0)
    return gaps


def domain_breakdown(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """rows: per-case metric snippets with domain + e2e + doc correct etc."""
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(r.get("domain") or "unknown", []).append(r)
    out = {}
    for domain, items in by.items():
        n = len(items) or 1
        required_n = sum(1 for x in items if x.get("mode") == "REQUIRED")
        out[domain] = {
            "case_count": len(items),
            "required_case_count": required_n,
            "e2e_success_rate": sum(1 for x in items if x.get("e2e_status") == "SUCCESS") / n,
            "partial_rate": sum(1 for x in items if x.get("e2e_status") == "PARTIAL") / n,
            "safe_failure_rate": sum(1 for x in items if x.get("e2e_status") == "SAFE_FAILURE") / n,
            "unsafe_failure_rate": sum(1 for x in items if x.get("e2e_status") == "UNSAFE_FAILURE") / n,
            "document_hit_rate": sum(1 for x in items if x.get("document_hit")) / n,
            "required_top1_hit_rate": _safe_div(
                sum(1 for x in items if x.get("required_top1_hit")),
                required_n,
            ),
            "mean_latency_ms": sum(float(x.get("latency_ms") or 0) for x in items) / n,
            "false_patch_count": sum(int(x.get("false_patch") or 0) for x in items),
        }
    return out
