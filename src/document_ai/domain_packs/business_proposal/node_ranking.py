# -*- coding: utf-8 -*-
"""Business Proposal candidate ranking (deterministic, no LLM)."""

from __future__ import annotations

from typing import Any

from document_ai.domain_packs.business_proposal.query_intent import BusinessProposalQueryIntent
from document_ai.domain_packs.business_proposal.structural_match import (
    assign_proposal_rank_tier,
    score_proposal_candidate,
    score_proposal_structural_match,
    _role_of,
)
from document_ai.domain_packs.business_proposal.structural_roles import (
    PROPOSAL_SECTION,
    VIRTUAL_PROPOSAL_TARGET,
    SCHEDULE_TABLE,
    BUDGET_TABLE,
    KPI_TABLE,
    DOCUMENT_HEADING,
)
from document_ai.domain_packs.business_proposal.validation import validate_proposal_ranking
from document_ai.domain_packs.generic.structural_match import promote_aligned_template_candidates


def _operation_role_rank(scores: dict[str, Any]) -> float:
    return float(scores.get("operation_role_match") or 0.0)


def _primary_concept_rank(scores: dict[str, Any]) -> float:
    return float(scores.get("primary_concept_match") or 0.0)


def _specificity(meta: dict[str, Any]) -> float:
    return float(meta.get("content_specificity") or 0.0)


def _locator_rank(meta: dict[str, Any]) -> tuple:
    loc = meta.get("source_locator") or {}
    return (1 if loc else 0, str(loc.get("paragraph_index") or loc.get("table_index") or ""))


def rank_business_proposal_candidates(
    candidates: list[dict[str, Any]],
    *,
    intent: BusinessProposalQueryIntent,
) -> dict[str, Any]:
    """Rank REVIEW candidates for business proposal. Mutates metadata. Deterministic."""
    ranked_rows: list[dict[str, Any]] = []
    matrices: list[dict[str, Any]] = []

    active = [c for c in candidates if c.get("status") in {"PATCH_CANDIDATE", "REVIEW_REQUIRED"}]
    for cand in active:
        meta = cand.setdefault("metadata", {})
        role = _role_of(cand)
        meta["structural_role"] = role
        meta["proposal_structural_role"] = role
        meta["domain"] = "business_proposal"
        scores = score_proposal_structural_match(cand, intent=intent)
        tier, reasons = assign_proposal_rank_tier(scores, intent=intent, role=role)
        scored = score_proposal_candidate(scores, tier=tier)
        meta["rank_tier"] = scored["rank_tier"]
        meta["final_score"] = scored["final_score"]
        meta["score_components"] = scored["score_components"]
        meta["structural_score_components"] = scores.to_dict()
        meta["ranking_reason_codes"] = sorted(set(reasons))
        meta["overlap"] = scored["final_score"]
        meta["query_intent"] = intent.intent_label
        meta["writer_executable"] = False
        meta["supports_patch"] = False
        matrices.append(scores.to_dict())
        ranked_rows.append(
            {
                "node_id": cand.get("node_id"),
                "status": cand.get("status"),
                "rank_tier": scored["rank_tier"],
                "final_score": scored["final_score"],
                "structural_role": role,
                "proposal_structural_role": role,
                "score_components": scored["score_components"],
                "structural_score_components": scores.to_dict(),
                "reason_codes": reasons,
            }
        )

    meta_by_id = {str(c.get("node_id")): c.get("metadata") or {} for c in candidates}

    def _sort_key(row: dict[str, Any]) -> tuple:
        tier = int(row.get("rank_tier") if row.get("rank_tier") is not None else 99)
        comps = row.get("structural_score_components") or {}
        meta_role = str(row.get("proposal_structural_role") or row.get("structural_role") or "")
        template_boost = 0
        if intent.update_intent and meta_role == PROPOSAL_SECTION:
            template_boost = 1
        elif intent.update_intent and meta_role == VIRTUAL_PROPOSAL_TARGET:
            template_boost = -2
        # Prefer matching tables over headings when table intent
        table_boost = 0
        if intent.table_intent and meta_role in {SCHEDULE_TABLE, BUDGET_TABLE, KPI_TABLE}:
            table_boost = 2
        elif intent.table_intent and meta_role == DOCUMENT_HEADING:
            table_boost = -1
        nid = str(row.get("node_id") or "")
        meta = meta_by_id.get(nid) or {}
        return (
            tier,
            -template_boost,
            -table_boost,
            -_operation_role_rank(comps),
            -_primary_concept_rank(comps),
            -float(comps.get("structural_role_match") or 0.0),
            -float(comps.get("table_header_match") or 0.0),
            -float(comps.get("alignment_confidence") or 0.0),
            -float(row.get("final_score") or 0.0),
            -float(comps.get("physical_editability") or 0.0),
            -_specificity(meta),
            float(comps.get("ambiguity_penalty") or 0.0),
            _locator_rank(meta),
            nid,
        )

    ranked_rows.sort(key=_sort_key)
    by_id = {c.get("node_id"): c for c in candidates}
    for i, row in enumerate(ranked_rows, start=1):
        row["rank"] = i
        cand = by_id.get(row["node_id"])
        if cand is not None:
            cand.setdefault("metadata", {})["rank"] = i

    order = {r["node_id"]: r["rank"] for r in ranked_rows}
    candidates.sort(key=lambda c: (order.get(c.get("node_id"), 10_000), str(c.get("node_id") or "")))

    validation = validate_proposal_ranking(ranked_rows, intent=intent)

    return {
        "query_intent": intent.to_dict(),
        "structural_match_matrix": matrices,
        "ranking_results": {
            "ranked_node_ids": [r["node_id"] for r in ranked_rows],
            "n_ranked": len(ranked_rows),
            "preferred_template_node_id": intent.preferred_template_node_id,
        },
        "ranking_candidates": ranked_rows,
        "validation": validation,
    }


def promote_aligned_proposal_template_candidates(
    *,
    review: list[dict[str, Any]],
    template_hits: list[dict[str, Any]],
    alignments: list[dict[str, Any]],
    intent: BusinessProposalQueryIntent,
) -> list[dict[str, Any]]:
    """Reuse generic promotion with mapped intent; enrich metadata for BP."""
    generic_intent = intent.to_generic_intent()
    out = promote_aligned_template_candidates(
        review=review,
        template_hits=template_hits,
        alignments=alignments,
        intent=generic_intent,
    )
    for item in out:
        meta = item.setdefault("metadata", {})
        role = str(meta.get("structural_role") or "")
        if role == "TEMPLATE_SECTION":
            meta["structural_role"] = PROPOSAL_SECTION
            meta["proposal_structural_role"] = PROPOSAL_SECTION
        if role == "VIRTUAL_TARGET":
            meta["structural_role"] = VIRTUAL_PROPOSAL_TARGET
            meta["proposal_structural_role"] = VIRTUAL_PROPOSAL_TARGET
        meta["domain"] = "business_proposal"
        meta["supports_patch"] = False
    return out
