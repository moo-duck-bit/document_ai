# -*- coding: utf-8 -*-
"""Business Proposal ranking invariants."""

from __future__ import annotations

from typing import Any

from document_ai.domain_packs.business_proposal.query_intent import BusinessProposalQueryIntent
from document_ai.domain_packs.business_proposal.structural_roles import (
    BUDGET_TABLE,
    KPI_TABLE,
    PROPOSAL_SECTION,
    SCHEDULE_TABLE,
    VIRTUAL_PROPOSAL_TARGET,
)


def validate_proposal_ranking(
    ranked_rows: list[dict[str, Any]],
    *,
    intent: BusinessProposalQueryIntent,
) -> dict[str, Any]:
    issues: list[str] = []
    validation = {
        "proposal_concept_rank_consistent": True,
        "proposal_table_role_consistent": True,
        "proposal_alignment_valid": True,
        "virtual_target_only_for_add": True,
        "business_proposal_not_general_report_fallback": True,
        "writer_scope_unchanged": True,
        "issues": issues,
    }

    if not ranked_rows:
        return validation

    top = ranked_rows[0]
    top_role = str(top.get("proposal_structural_role") or top.get("structural_role") or "")

    if not intent.add_intent and top_role == VIRTUAL_PROPOSAL_TARGET:
        validation["virtual_target_only_for_add"] = False
        issues.append("virtual_top_non_add")

    if intent.table_intent and intent.primary_concept in {"SCHEDULE", "BUDGET", "KPI"}:
        table_roles = {SCHEDULE_TABLE, BUDGET_TABLE, KPI_TABLE}
        has_table = any(
            str(r.get("proposal_structural_role") or r.get("structural_role") or "") in table_roles
            for r in ranked_rows
        )
        top3_roles = [
            str(r.get("proposal_structural_role") or r.get("structural_role") or "")
            for r in ranked_rows[:3]
        ]
        if has_table and not (set(top3_roles) & table_roles):
            validation["proposal_table_role_consistent"] = False
            issues.append("table_not_in_top3")

    if intent.primary_concept and top_role not in {
        PROPOSAL_SECTION,
        SCHEDULE_TABLE,
        BUDGET_TABLE,
        KPI_TABLE,
        "RISK_SECTION",
        "ORGANIZATION_SECTION",
        "EXPECTED_EFFECT_SECTION",
        "DOCUMENT_HEADING",
        "PARAGRAPH_BODY",
    }:
        comps = top.get("structural_score_components") or {}
        if float(comps.get("primary_concept_match") or 0) < 0.4:
            validation["proposal_concept_rank_consistent"] = False
            issues.append("top_missing_primary_concept")

    for row in ranked_rows[:5]:
        comps = row.get("structural_score_components") or {}
        if float(comps.get("alignment_confidence") or 0) > 0 and float(comps.get("primary_concept_match") or 0) == 0:
            if intent.primary_concept:
                validation["proposal_alignment_valid"] = False
                issues.append("alignment_without_concept")
                break

    for row in ranked_rows:
        comps = row.get("score_components") or {}
        if comps.get("tier_base", 0) >= 100 and str(row.get("status")) == "PATCH_CANDIDATE":
            validation["writer_scope_unchanged"] = False
            issues.append("patch_candidate_in_bp_ranking")
            break

    validation["issues"] = issues
    return validation


def validate_proposal_alignment_records(alignments: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    for a in alignments:
        if a.get("equivalent_for_patch") and not a.get("source_locator"):
            issues.append(f"patch_eq_without_locator:{a.get('alignment_id')}")
        if a.get("patch_equivalence") and not a.get("evaluation_equivalence"):
            issues.append(f"patch_without_eval:{a.get('alignment_id')}")
    return {
        "proposal_alignment_valid": not issues,
        "issues": issues,
    }
