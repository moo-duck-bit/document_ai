# -*- coding: utf-8 -*-
"""Validation rules for Business Proposal gold rows.

Pure structural checks — never consults prediction outputs. Rationale text is
scanned to make sure gold was not (even accidentally) justified by referring
to a prediction/ranking artifact.
"""

from __future__ import annotations

import re
from typing import Any

from document_ai.evaluation.business_proposal_gold.schema import (
    ALLOWED_LOCATION_TYPES,
    ALLOWED_MODES,
    ALLOWED_OPERATIONS,
    ALLOWED_PHYSICAL_NODE_TYPES,
    ALLOWED_REFERENCE_TYPES,
    BusinessProposalGoldRow,
)

FORBIDDEN_ARTIFACT_TOKENS: tuple[str, ...] = (
    "ranking_results",
    "node_ranking",
    "structural_match_matrix",
    "query_intent.json",
    "proposed_label_changes",
    "node_label_audit",
    "ranked_node_ids",
    "prediction",
    "top-1",
    "top1",
    "_results.jsonl",
)


def _as_row(row: BusinessProposalGoldRow | dict[str, Any]) -> BusinessProposalGoldRow:
    if isinstance(row, BusinessProposalGoldRow):
        return row
    return BusinessProposalGoldRow.from_dict(row)


def validate_gold_row(
    row: BusinessProposalGoldRow | dict[str, Any],
    *,
    inventory: dict[str, Any] | None = None,
) -> list[str]:
    r = _as_row(row)
    issues: list[str] = []

    if r.node_evaluation_mode not in ALLOWED_MODES:
        issues.append(f"INVALID_MODE:{r.node_evaluation_mode}")
    if r.expected_operation and r.expected_operation not in ALLOWED_OPERATIONS:
        issues.append(f"INVALID_OPERATION:{r.expected_operation}")
    if r.expected_physical_node_type and r.expected_physical_node_type not in ALLOWED_PHYSICAL_NODE_TYPES:
        issues.append(f"INVALID_PHYSICAL_NODE_TYPE:{r.expected_physical_node_type}")
    if r.expected_location_type and r.expected_location_type not in ALLOWED_LOCATION_TYPES:
        issues.append(f"INVALID_LOCATION_TYPE:{r.expected_location_type}")

    ref = r.primary_reference or {}
    ref_type = ref.get("reference_type")
    if ref and ref_type not in ALLOWED_REFERENCE_TYPES:
        issues.append(f"INVALID_REFERENCE_TYPE:{ref_type}")

    if not (r.label_rationale or "").strip():
        issues.append("RATIONALE_REQUIRED")
    else:
        low = r.label_rationale.lower()
        for token in FORBIDDEN_ARTIFACT_TOKENS:
            if token in low:
                issues.append(f"RATIONALE_REFERENCES_PREDICTION_ARTIFACT:{token}")

    if r.node_evaluation_mode == "REQUIRED":
        has_primary = bool(ref.get("template_node_id") or ref.get("document_node_id") or ref.get("stable_node_id"))
        if not has_primary:
            issues.append("REQUIRED_MISSING_PRIMARY")
        # REQUIRED must not resolve to a purely virtual (non-existent) node.
        if ref_type == "VIRTUAL":
            issues.append("REQUIRED_VIRTUAL_ONLY_REJECTED")

    if r.node_evaluation_mode == "AMBIGUOUS":
        if not (r.acceptable_groups or r.acceptable_references):
            issues.append("AMBIGUOUS_MISSING_GROUP")
        if r.acceptable_groups and any(len(g) < 2 for g in r.acceptable_groups):
            issues.append("AMBIGUOUS_GROUP_TOO_SMALL")

    if r.expected_operation == "UPDATE" and ref_type == "VIRTUAL":
        issues.append("UPDATE_VIRTUAL_ONLY_REJECTED")

    # TABLE-location gold rows must carry a TABLE physical node type (see
    # ``validate_change_request_table_alignment`` for the CR-driven cross-check).
    if (
        r.node_evaluation_mode in {"REQUIRED", "AMBIGUOUS"}
        and r.expected_location_type == "TABLE"
        and r.expected_physical_node_type not in {"TABLE", None}
    ):
        issues.append("TABLE_LOCATION_BUT_NON_TABLE_PHYSICAL_TYPE")

    if inventory is not None:
        node_ids = {n["node_id"] for n in inventory.get("nodes") or []}
        doc_node_id = ref.get("document_node_id")
        if doc_node_id and doc_node_id not in node_ids:
            issues.append(f"WRONG_DOCUMENT_OR_UNKNOWN_NODE:{doc_node_id}")
        for g in r.acceptable_groups or []:
            for member in g:
                if "." in member and not member.startswith(("heading_", "paragraph_", "table_")):
                    continue  # template node id — not part of this document's inventory
                if member not in node_ids:
                    issues.append(f"WRONG_DOCUMENT_OR_UNKNOWN_NODE:{member}")

    return issues


# Literal (not concept-inferred) table wording — deliberately narrower than
# ``BusinessProposalQueryIntent.table_intent``, which also turns on for any
# SCHEDULE/BUDGET/KPI concept even when the document only has a paragraph
# (that is a legitimate REQUIRED/paragraph gold, not a mismatch).
_EXPLICIT_TABLE_WORDING_RE = re.compile(r"표|테이블|table", re.IGNORECASE)


def validate_change_request_table_alignment(
    row: BusinessProposalGoldRow | dict[str, Any],
    *,
    change_request: str,
) -> list[str]:
    """Cross-check: a CR that *literally* asks for a table edit but resolves to a
    paragraph-only physical node is a WARN (or REJECT for REQUIRED) — this only
    fires on explicit table wording, not the broader concept-based table_intent
    heuristic (SCHEDULE/BUDGET/KPI concepts are table_intent by default even when
    the document represents them as a paragraph)."""
    r = _as_row(row)
    issues: list[str] = []
    if _EXPLICIT_TABLE_WORDING_RE.search(change_request or "") and r.expected_physical_node_type == "PARAGRAPH":
        if r.node_evaluation_mode == "REQUIRED":
            issues.append("TABLE_INTENT_PARAGRAPH_ONLY_REJECTED")
        else:
            issues.append("TABLE_INTENT_PARAGRAPH_ONLY_WARNING")
    return issues


def validate_gold_rows(
    rows: list[BusinessProposalGoldRow | dict[str, Any]],
    *,
    inventories: dict[str, dict[str, Any]] | None = None,
    change_requests: dict[str, str] | None = None,
) -> dict[str, Any]:
    inventories = inventories or {}
    change_requests = change_requests or {}
    per_case: dict[str, list[str]] = {}
    for row in rows:
        r = _as_row(row)
        inv = inventories.get(r.case_id)
        issues = validate_gold_row(r, inventory=inv)
        cr = change_requests.get(r.case_id)
        if cr is not None:
            issues += validate_change_request_table_alignment(r, change_request=cr)
        if issues:
            per_case[r.case_id] = issues
    return {
        "n_rows": len(rows),
        "n_invalid": len(per_case),
        "issues_by_case": per_case,
        "status": "VALID" if not per_case else "INVALID",
    }
