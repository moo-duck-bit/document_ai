# -*- coding: utf-8 -*-
"""PR-22: Target eligibility from semantic match + operation context."""

from __future__ import annotations

from typing import Any

from document_ai.patch_targeting.schema import REQUESTED_OPERATIONS, PatchTargetingInput
from document_ai.semantic_locator.thresholds import DEFAULT_THRESHOLDS, GENERIC_TEMPLATE_IDS
from document_ai.template.schema import WRITER_SUPPORTED_OPERATIONS


def evaluate_eligibility(
    inp: PatchTargetingInput,
    *,
    node_allowed_operations: list[str] | None = None,
    node_exists: bool = False,
    node_template_id: str | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    """
    Return (intent_status, reason_codes, evidence).

    Does not create patches or call writers.
    """
    reasons: list[str] = []
    evidence: dict[str, Any] = {
        "match_status": inp.match_status,
        "combined_score": inp.combined_score,
        "score_margin": inp.score_margin,
        "ambiguity_status": inp.ambiguity_status,
        "requested_operation": inp.requested_operation,
    }
    op = str(inp.requested_operation or "").upper()
    allowed = list(node_allowed_operations or [])

    if op not in REQUESTED_OPERATIONS:
        reasons.append("SEMANTIC_INVALID")
        return "INVALID", reasons + ["OPERATION_TEMPLATE_NOT_ALLOWED"], evidence

    # Semantic status baseline
    ms = str(inp.match_status or "").upper()
    if ms == "INVALID":
        reasons.append("SEMANTIC_INVALID")
        reasons.extend(
            ["ACTUAL_PATCH_NOT_CREATED", "ACTUAL_DOCUMENT_UNCHANGED"]
        )
        return "INVALID", reasons, evidence
    if ms == "UNMAPPED":
        reasons.append("SEMANTIC_UNMAPPED")
        reasons.extend(
            ["ACTUAL_PATCH_NOT_CREATED", "ACTUAL_DOCUMENT_UNCHANGED"]
        )
        return "BLOCKED", reasons, evidence
    if ms == "REVIEW":
        reasons.append("SEMANTIC_REVIEW_REQUIRED")
        status = "REVIEW_REQUIRED"
    elif ms == "MATCHED":
        reasons.append("SEMANTIC_MATCH_ELIGIBLE")
        status = "ELIGIBLE"
    else:
        reasons.append("SEMANTIC_INVALID")
        return "INVALID", reasons, evidence

    # Template / node checks
    if not inp.template_node_id:
        reasons.append("TEMPLATE_NODE_MISSING")
        if status == "ELIGIBLE":
            status = "BLOCKED"
    else:
        if node_exists:
            reasons.append("TEMPLATE_NODE_RESOLVED")
        else:
            reasons.append("NODE_NOT_FOUND")
            return "INVALID", reasons, evidence

    if inp.template_id and inp.template_id not in GENERIC_TEMPLATE_IDS:
        reasons.append("TEMPLATE_MISMATCH")
        return "INVALID", reasons, evidence

    if (
        node_exists
        and node_template_id
        and inp.template_id
        and node_template_id != inp.template_id
    ):
        reasons.append("TEMPLATE_MISMATCH")
        return "INVALID", reasons, evidence

    # Ambiguity / margin
    if inp.ambiguity_status == "AMBIGUOUS":
        reasons.append("AMBIGUOUS_MATCH")
        status = "REVIEW_REQUIRED"
    margin = inp.score_margin
    if margin is not None and margin < DEFAULT_THRESHOLDS.score_margin_min:
        reasons.append("LOW_SCORE_MARGIN")
        if status == "ELIGIBLE":
            status = "REVIEW_REQUIRED"

    # Operation capability (template)
    if op in allowed:
        reasons.append("OPERATION_TEMPLATE_ALLOWED")
        evidence["template_allowed"] = True
    else:
        reasons.append("OPERATION_TEMPLATE_NOT_ALLOWED")
        evidence["template_allowed"] = False
        status = "BLOCKED"

    # Writer capability (informational for eligibility; does not alone invalidate intent)
    writer_ok = op in WRITER_SUPPORTED_OPERATIONS
    if writer_ok:
        reasons.append("OPERATION_WRITER_SUPPORTED")
    else:
        reasons.append("OPERATION_WRITER_NOT_SUPPORTED")
    evidence["writer_supported"] = writer_ok

    # Content requirements
    if op == "UPDATE":
        if not (inp.proposed_text or "").strip():
            reasons.append("PROPOSED_TEXT_MISSING")
            status = "BLOCKED"
    if op == "DELETE":
        reasons.append("DELETE_REQUIRES_REVIEW")
        status = "REVIEW_REQUIRED"
        # strong evidence check
        rule = (inp.match_evidence or {}).get("rule_components") or {}
        strong = (
            rule.get("heading_path_exact", 0) >= 1.0
            or rule.get("exact_text", 0) >= 1.0
        )
        if not strong and (margin is None or margin < DEFAULT_THRESHOLDS.score_margin_min):
            if "AMBIGUOUS_MATCH" not in reasons:
                reasons.append("AMBIGUOUS_MATCH")
    if op == "ADD":
        parent_ok = bool(
            (inp.metadata or {}).get("parent_section_id")
            or (inp.match_evidence or {}).get("matched_heading_path")
            or inp.template_node_id
        )
        if not parent_ok:
            reasons.append("ADD_PARENT_TARGET_MISSING")
            status = "BLOCKED"
    if op == "LINK":
        meta = inp.metadata or {}
        if not (meta.get("link_source") and meta.get("link_target")):
            reasons.append("LINK_METADATA_MISSING")
            status = "BLOCKED"

    # Always observational markers
    reasons.append("ACTUAL_PATCH_NOT_CREATED")
    reasons.append("ACTUAL_DOCUMENT_UNCHANGED")
    if status == "ELIGIBLE":
        reasons.append("PATCH_INTENT_CREATED")

    # Deduplicate preserving order
    uniq: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return status, uniq, evidence
