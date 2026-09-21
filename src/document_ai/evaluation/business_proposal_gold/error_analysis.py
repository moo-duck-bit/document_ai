# -*- coding: utf-8 -*-
"""Classify Business Proposal REQUIRED node-ranking misses into a fixed taxonomy."""

from __future__ import annotations

from typing import Any

from document_ai.evaluation.document_set.retrieval_metrics import rank_nodes

CORRECT = "CORRECT"
NO_PREDICTION = "NO_PREDICTION"
WRONG_TEMPLATE_NODE = "WRONG_TEMPLATE_NODE"
WRONG_PHYSICAL_NODE = "WRONG_PHYSICAL_NODE"
HEADING_INSTEAD_OF_PARAGRAPH = "HEADING_INSTEAD_OF_PARAGRAPH"
HEADING_INSTEAD_OF_TABLE = "HEADING_INSTEAD_OF_TABLE"
PARAGRAPH_INSTEAD_OF_TABLE = "PARAGRAPH_INSTEAD_OF_TABLE"
TABLE_INSTEAD_OF_PARAGRAPH = "TABLE_INSTEAD_OF_PARAGRAPH"
WRONG_SECTION = "WRONG_SECTION"
OTHER_MISMATCH = "OTHER_MISMATCH"

ERROR_TAXONOMY = frozenset(
    {
        NO_PREDICTION,
        WRONG_TEMPLATE_NODE,
        WRONG_PHYSICAL_NODE,
        HEADING_INSTEAD_OF_PARAGRAPH,
        HEADING_INSTEAD_OF_TABLE,
        PARAGRAPH_INSTEAD_OF_TABLE,
        TABLE_INSTEAD_OF_PARAGRAPH,
        WRONG_SECTION,
        OTHER_MISMATCH,
    }
)


def _physical_type_of(node_id: str) -> str | None:
    if node_id.startswith("heading_"):
        return "HEADING"
    if node_id.startswith("paragraph_"):
        return "PARAGRAPH"
    if node_id.startswith("table_"):
        return "TABLE"
    return None


def classify_miss(
    *,
    gold_ids: set[str],
    acceptable: set[str],
    ranked_preds: list[dict[str, Any]],
    expected_physical_node_type: str | None,
) -> str:
    ranked = rank_nodes(ranked_preds or [])
    if not ranked:
        return NO_PREDICTION
    allowed = set(gold_ids) | set(acceptable)
    top_id = str(ranked[0].get("node_id") or "")
    if top_id in allowed:
        return CORRECT

    top_type = _physical_type_of(top_id)
    gold_is_template = any("." in g and _physical_type_of(g) is None for g in allowed)
    gold_is_physical = any(_physical_type_of(g) is not None for g in allowed)

    if top_type is None and gold_is_template:
        return WRONG_TEMPLATE_NODE
    if top_type is not None and gold_is_physical and not gold_is_template:
        if expected_physical_node_type == "TABLE" and top_type == "HEADING":
            return HEADING_INSTEAD_OF_TABLE
        if expected_physical_node_type == "TABLE" and top_type == "PARAGRAPH":
            return PARAGRAPH_INSTEAD_OF_TABLE
        if expected_physical_node_type == "PARAGRAPH" and top_type == "HEADING":
            return HEADING_INSTEAD_OF_PARAGRAPH
        if expected_physical_node_type == "PARAGRAPH" and top_type == "TABLE":
            return TABLE_INSTEAD_OF_PARAGRAPH
        return WRONG_PHYSICAL_NODE
    if top_type is None and not gold_is_template:
        return WRONG_SECTION
    return OTHER_MISMATCH


def build_error_report(
    calibrated_cases: list[dict[str, Any]],
    *,
    expected_physical_node_type_by_case: dict[str, str] | None = None,
) -> dict[str, Any]:
    expected = expected_physical_node_type_by_case or {}
    rows = []
    counts: dict[str, int] = {}
    for c in calibrated_cases:
        if c.get("mode") != "REQUIRED":
            continue
        error = classify_miss(
            gold_ids=set(c.get("gold_ids") or []),
            acceptable=set(c.get("acceptable") or []),
            ranked_preds=c.get("ranked_preds") or [],
            expected_physical_node_type=expected.get(c.get("case_id")),
        )
        counts[error] = counts.get(error, 0) + 1
        rows.append({"case_id": c.get("case_id"), "error_type": error})
    return {
        "n_cases": len(rows),
        "error_counts": counts,
        "rows": rows,
        "taxonomy": sorted(ERROR_TAXONOMY),
    }
