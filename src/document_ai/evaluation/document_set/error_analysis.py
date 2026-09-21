# -*- coding: utf-8 -*-
"""Error taxonomy for document-set benchmark."""

from __future__ import annotations

from typing import Any

ERROR_CLASSES = [
    "DOCUMENT_MISSED",
    "DOCUMENT_FALSE_POSITIVE",
    "NODE_MISSED",
    "WRONG_NODE",
    "OVER_PATCH",
    "UNDER_REVIEW",
    "OVER_REVIEW",
    "PHYSICAL_LOCATION_ERROR",
    "WRITER_BLOCK_ERROR",
    "WRITER_WRONG_EDIT",
    "FORMAT_REGRESSION",
    "STATE_TRANSITION_ERROR",
    "INPUT_VALIDATION_ERROR",
    "PIPELINE_ERROR",
]


def classify_case_errors(
    case_id: str,
    gold_docs: list[dict[str, Any]],
    pred_docs: list[dict[str, Any]],
    gold_nodes: list[dict[str, Any]],
    pred_nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    pred_by_doc = {d["document_id"]: d.get("predicted_status") for d in pred_docs}
    for g in gold_docs:
        did = g["document_id"]
        gold = g["gold_status"]
        pred = pred_by_doc.get(did, "UNRELATED")
        if gold in {"IMPACTED", "REVIEW_REQUIRED"} and pred == "UNRELATED":
            errors.append(_err(case_id, "DOCUMENT_MISSED", gold, pred, "document"))
        elif gold == "UNRELATED" and pred in {"IMPACTED", "REVIEW_REQUIRED"}:
            errors.append(_err(case_id, "DOCUMENT_FALSE_POSITIVE", gold, pred, "document"))

    gold_patch = {n["node_id"] for n in gold_nodes if n.get("gold_status") == "PATCH_CANDIDATE"}
    pred_patch = {n.get("node_id") for n in pred_nodes if n.get("predicted_status") == "PATCH_CANDIDATE"}
    if gold_patch and not (gold_patch & pred_patch):
        errors.append(_err(case_id, "NODE_MISSED", sorted(gold_patch), sorted(pred_patch), "node"))
    if pred_patch - gold_patch and gold_patch:
        # wrong or over-patch
        if not (pred_patch & gold_patch):
            errors.append(_err(case_id, "WRONG_NODE", sorted(gold_patch), sorted(pred_patch), "node"))
        else:
            errors.append(_err(case_id, "OVER_PATCH", sorted(gold_patch), sorted(pred_patch), "decision"))
    return errors


def _err(case_id: str, cls: str, expected: Any, predicted: Any, stage: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "error_class": cls,
        "stage": stage,
        "expected": expected,
        "predicted": predicted,
        "recommended_investigation": f"inspect {stage} artifacts for {case_id}",
    }


def summarize_errors(errors: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for e in errors:
        counts[e["error_class"]] = counts.get(e["error_class"], 0) + 1
    top = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return {
        "total_errors": len(errors),
        "by_class": counts,
        "most_frequent": top[0][0] if top else None,
        "errors": errors,
    }
