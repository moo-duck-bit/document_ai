# -*- coding: utf-8 -*-
"""Business Proposal structural match matrix and tier assignment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from document_ai.domain_packs.business_proposal.concepts import (
    BUDGET,
    EXPECTED_EFFECT,
    KPI,
    ORGANIZATION,
    RISK_MANAGEMENT,
    SCHEDULE,
    normalize_proposal_concepts,
)
from document_ai.domain_packs.business_proposal.query_intent import BusinessProposalQueryIntent
from document_ai.domain_packs.business_proposal.structural_roles import (
    BUDGET_TABLE,
    DOCUMENT_CONTEXT,
    DOCUMENT_HEADING,
    EXPECTED_EFFECT_SECTION,
    KPI_TABLE,
    ORGANIZATION_SECTION,
    PARAGRAPH_BODY,
    PROPOSAL_FIELD,
    PROPOSAL_SECTION,
    RISK_SECTION,
    SCHEDULE_TABLE,
    VIRTUAL_PROPOSAL_TARGET,
    annotate_proposal_structural_role,
)
from document_ai.template.concept_normalization import RISK, normalize_concepts, tokenize


@dataclass
class ProposalStructuralMatchScores:
    candidate_node_id: str
    primary_concept_match: float = 0.0
    secondary_concept_match: float = 0.0
    operation_role_match: float = 0.0
    structural_role_match: float = 0.0
    template_node_match: float = 0.0
    parent_section_match: float = 0.0
    table_header_match: float = 0.0
    paragraph_content_match: float = 0.0
    list_content_match: float = 0.0
    alignment_confidence: float = 0.0
    physical_editability: float = 0.0
    virtual_target_penalty: float = 0.0
    ambiguity_penalty: float = 0.0
    document_context_penalty: float = 0.0
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ROLE_PREF: dict[str, list[str]] = {
    "SCHEDULE_UPDATE": [SCHEDULE_TABLE, PROPOSAL_SECTION, DOCUMENT_HEADING, PARAGRAPH_BODY],
    "SCHEDULE_ADD": [VIRTUAL_PROPOSAL_TARGET, SCHEDULE_TABLE, PROPOSAL_SECTION],
    "BUDGET_UPDATE": [BUDGET_TABLE, PROPOSAL_SECTION, PROPOSAL_FIELD, PARAGRAPH_BODY, DOCUMENT_HEADING],
    "BUDGET_ADD": [VIRTUAL_PROPOSAL_TARGET, BUDGET_TABLE, PROPOSAL_SECTION],
    "KPI_UPDATE": [KPI_TABLE, PROPOSAL_SECTION, PARAGRAPH_BODY],
    "KPI_ADD": [VIRTUAL_PROPOSAL_TARGET, KPI_TABLE, PROPOSAL_SECTION],
    "RISK_UPDATE": [RISK_SECTION, PROPOSAL_SECTION, PARAGRAPH_BODY, DOCUMENT_HEADING],
    "RISK_ADD": [VIRTUAL_PROPOSAL_TARGET, PROPOSAL_SECTION, RISK_SECTION],
    "ORGANIZATION_UPDATE": [ORGANIZATION_SECTION, PROPOSAL_SECTION, PARAGRAPH_BODY],
    "ORGANIZATION_ADD": [VIRTUAL_PROPOSAL_TARGET, ORGANIZATION_SECTION, PROPOSAL_SECTION],
    "EXPECTED_EFFECT_UPDATE": [EXPECTED_EFFECT_SECTION, PROPOSAL_SECTION, PARAGRAPH_BODY],
    "EXPECTED_EFFECT_ADD": [VIRTUAL_PROPOSAL_TARGET, EXPECTED_EFFECT_SECTION, PROPOSAL_SECTION],
    "SECTION_ADD": [VIRTUAL_PROPOSAL_TARGET, PROPOSAL_SECTION],
    "PROPOSAL_REVIEW": [PROPOSAL_SECTION, PARAGRAPH_BODY, DOCUMENT_HEADING],
    "UNKNOWN": [PROPOSAL_SECTION, PARAGRAPH_BODY, DOCUMENT_HEADING],
}


def _cand_concepts(cand: dict[str, Any]) -> set[str]:
    meta = cand.get("metadata") or {}
    blob = " ".join(
        [
            str(cand.get("node_id") or ""),
            str(cand.get("display_name") or ""),
            str(meta.get("section_context") or ""),
            " ".join(meta.get("canonical_concepts") or []),
        ]
    )
    return (
        set(meta.get("canonical_concepts") or [])
        | normalize_proposal_concepts(blob)
        | normalize_concepts(blob)
    )


def _role_of(cand: dict[str, Any]) -> str:
    meta = cand.get("metadata") or {}
    if meta.get("proposal_structural_role"):
        return str(meta["proposal_structural_role"])
    if meta.get("structural_role"):
        return str(meta["structural_role"])
    ann = annotate_proposal_structural_role(
        node_id=str(cand.get("node_id") or ""),
        display_name=str(cand.get("display_name") or ""),
        virtual_target=bool(meta.get("virtual_target")),
        template_only=bool(meta.get("template_only")),
        evidence_type=str(meta.get("evidence_type") or ""),
        is_heading=str(cand.get("node_id") or "").startswith("heading_"),
        table_role=meta.get("table_role"),
    )
    return str(ann.get("proposal_structural_role") or ann["structural_role"])


def _concept_match(primary: str | None, secondary: list[str], concepts: set[str]) -> tuple[float, float]:
    primary_score = 1.0 if primary and primary in concepts else 0.0
    if not primary and RISK in concepts and primary is None:
        if RISK_MANAGEMENT in concepts:
            primary_score = 1.0
    secondary_hits = sum(1 for c in secondary if c in concepts)
    secondary_score = min(1.0, secondary_hits / max(1, len(secondary))) if secondary else 0.0
    if primary_score == 0.0 and concepts:
        generic_primary = {RISK if primary == RISK_MANAGEMENT else primary} if primary else set()
        if generic_primary & concepts:
            primary_score = 0.85
    return primary_score, secondary_score


def score_proposal_structural_match(
    cand: dict[str, Any],
    *,
    intent: BusinessProposalQueryIntent,
) -> ProposalStructuralMatchScores:
    meta = cand.get("metadata") or {}
    nid = str(cand.get("node_id") or "")
    role = _role_of(cand)
    concepts = _cand_concepts(cand)
    reasons: list[str] = []

    primary_match, secondary_match = _concept_match(
        intent.primary_concept, intent.secondary_concepts, concepts
    )
    if primary_match >= 0.85:
        reasons.append("primary_concept_hit")
    elif secondary_match > 0:
        reasons.append("secondary_concept_hit")

    preferred = _ROLE_PREF.get(intent.intent_label, _ROLE_PREF["UNKNOWN"])
    if role in preferred:
        structural_role_match = 1.0 - 0.1 * preferred.index(role)
        reasons.append(f"role_pref:{role}")
    else:
        structural_role_match = 0.12

    op = intent.requested_operation
    operation_role_match = 0.0
    if op == "ADD":
        if role == VIRTUAL_PROPOSAL_TARGET and intent.add_intent:
            operation_role_match = 1.0
            reasons.append("add_prefers_virtual")
        elif role in {PROPOSAL_SECTION, PARAGRAPH_BODY}:
            operation_role_match = 0.25
    else:
        if role in {
            SCHEDULE_TABLE,
            BUDGET_TABLE,
            KPI_TABLE,
            RISK_SECTION,
            ORGANIZATION_SECTION,
            EXPECTED_EFFECT_SECTION,
            PARAGRAPH_BODY,
            DOCUMENT_HEADING,
        }:
            operation_role_match = 0.9 if primary_match >= 0.85 else 0.45
        if role == PROPOSAL_SECTION and primary_match >= 0.85:
            operation_role_match = max(operation_role_match, 0.98)
            reasons.append("update_template_section_eval")
        if role == VIRTUAL_PROPOSAL_TARGET:
            operation_role_match = 0.0
            reasons.append("virtual_not_for_update")

    template_node_match = 0.0
    preferred_tid = intent.preferred_template_node_id
    if preferred_tid and nid == preferred_tid:
        template_node_match = 1.0
        reasons.append("preferred_template_node")
    elif meta.get("template_node_id") == preferred_tid or meta.get("evaluation_equivalent"):
        template_node_match = max(template_node_match, 0.85)
        reasons.append("aligned_preferred_template")

    parent_section_match = float(meta.get("parent_context_match") or 0.0)
    if meta.get("direct_match"):
        parent_section_match = max(parent_section_match, 0.8)
    elif meta.get("inherited_match"):
        parent_section_match = max(parent_section_match, 0.35)

    table_header_match = 0.0
    if intent.table_intent or intent.intent_label.startswith(("SCHEDULE", "BUDGET", "KPI")):
        if role in {SCHEDULE_TABLE, BUDGET_TABLE, KPI_TABLE}:
            table_header_match = 0.95 if primary_match >= 0.5 else 0.6
            reasons.append("table_header_role_match")
        elif role == DOCUMENT_HEADING and intent.primary_concept in {SCHEDULE, BUDGET}:
            table_header_match = 0.35

    paragraph_content_match = 0.0
    if role in {PARAGRAPH_BODY, RISK_SECTION, EXPECTED_EFFECT_SECTION, ORGANIZATION_SECTION}:
        cr_toks = tokenize(intent.raw_change_request)
        cand_toks = tokenize(str(cand.get("display_name") or ""))
        overlap = len(cr_toks & cand_toks) / max(1, len(cr_toks)) if cr_toks else 0.0
        paragraph_content_match = min(1.0, 0.25 + overlap)
        if intent.primary_concept == RISK_MANAGEMENT and role == RISK_SECTION:
            paragraph_content_match = max(paragraph_content_match, 0.85)
            reasons.append("risk_section_paragraph_pref")

    list_content_match = 0.0
    if role.endswith("_LIST") or "list" in nid:
        list_content_match = 0.5

    alignment_confidence = float(meta.get("alignment_confidence") or 0.0)
    if meta.get("evaluation_equivalent"):
        alignment_confidence = max(alignment_confidence, 0.88)
        reasons.append("eval_equivalent_alignment")

    physical_editability = 1.0 if meta.get("physical", role not in {PROPOSAL_SECTION, VIRTUAL_PROPOSAL_TARGET, DOCUMENT_CONTEXT}) else 0.2
    if role == PROPOSAL_SECTION:
        physical_editability = 0.2

    virtual_target_penalty = 0.0
    if role == VIRTUAL_PROPOSAL_TARGET and not intent.add_intent:
        virtual_target_penalty = 0.85
        reasons.append("virtual_target_penalty_non_add")

    document_context_penalty = 0.0
    if role == DOCUMENT_CONTEXT:
        document_context_penalty = 0.45

    ambiguity_penalty = 0.12 if intent.ambiguity and primary_match < 0.85 else 0.0

    # Budget preference: table > section > field > paragraph
    if intent.primary_concept == BUDGET:
        if role == BUDGET_TABLE:
            structural_role_match = max(structural_role_match, 0.95)
        elif role == PROPOSAL_SECTION:
            structural_role_match = max(structural_role_match, 0.8)
        elif role == PROPOSAL_FIELD:
            structural_role_match = max(structural_role_match, 0.65)
        elif role == PARAGRAPH_BODY and primary_match < 0.5:
            structural_role_match = min(structural_role_match, 0.35)

    if intent.primary_concept == SCHEDULE and role == SCHEDULE_TABLE:
        structural_role_match = max(structural_role_match, 0.95)

    return ProposalStructuralMatchScores(
        candidate_node_id=nid,
        primary_concept_match=primary_match,
        secondary_concept_match=secondary_match,
        operation_role_match=operation_role_match,
        structural_role_match=structural_role_match,
        template_node_match=template_node_match,
        parent_section_match=parent_section_match,
        table_header_match=table_header_match,
        paragraph_content_match=paragraph_content_match,
        list_content_match=list_content_match,
        alignment_confidence=alignment_confidence,
        physical_editability=physical_editability,
        virtual_target_penalty=virtual_target_penalty,
        ambiguity_penalty=ambiguity_penalty,
        document_context_penalty=document_context_penalty,
        reason_codes=reasons,
    )


def assign_proposal_rank_tier(
    scores: ProposalStructuralMatchScores,
    *,
    intent: BusinessProposalQueryIntent,
    role: str,
) -> tuple[int, list[str]]:
    reasons = list(scores.reason_codes)
    if (
        scores.template_node_match >= 0.95
        and scores.operation_role_match >= 0.9
        and scores.primary_concept_match >= 0.85
        and role in {SCHEDULE_TABLE, BUDGET_TABLE, KPI_TABLE, PARAGRAPH_BODY, DOCUMENT_HEADING}
    ):
        reasons.append("RANK_TIER_0")
        return 0, reasons
    if role == PROPOSAL_SECTION and scores.primary_concept_match >= 0.85 and scores.operation_role_match >= 0.9:
        reasons.append("RANK_TIER_1")
        reasons.append("exact_section_concept_template")
        return 1, reasons
    if scores.primary_concept_match >= 0.85 and scores.structural_role_match >= 0.75:
        reasons.append("RANK_TIER_1")
        return 1, reasons
    if scores.alignment_confidence >= 0.75 and scores.primary_concept_match >= 0.5:
        reasons.append("RANK_TIER_2")
        return 2, reasons
    if scores.parent_section_match >= 0.7 or scores.table_header_match >= 0.55:
        reasons.append("RANK_TIER_3")
        return 3, reasons
    if scores.primary_concept_match >= 0.4 or scores.paragraph_content_match >= 0.5:
        reasons.append("RANK_TIER_4")
        return 4, reasons
    if role in {PROPOSAL_SECTION, VIRTUAL_PROPOSAL_TARGET}:
        reasons.append("RANK_TIER_5")
        return 5, reasons
    reasons.append("RANK_TIER_6")
    return 6, reasons


def score_proposal_candidate(
    scores: ProposalStructuralMatchScores,
    *,
    tier: int,
) -> dict[str, Any]:
    tier_base = {0: 130.0, 1: 105.0, 2: 82.0, 3: 62.0, 4: 36.0, 5: 14.0, 6: 4.0}.get(tier, 4.0)
    components = {
        "tier_base": tier_base,
        "primary_concept_match": 28.0 * scores.primary_concept_match,
        "secondary_concept_match": 8.0 * scores.secondary_concept_match,
        "operation_role_match": 22.0 * scores.operation_role_match,
        "structural_role_match": 20.0 * scores.structural_role_match,
        "template_node_match": 18.0 * scores.template_node_match,
        "parent_section_match": 10.0 * scores.parent_section_match,
        "table_header_match": 24.0 * scores.table_header_match,
        "paragraph_content_match": 10.0 * scores.paragraph_content_match,
        "list_content_match": 6.0 * scores.list_content_match,
        "alignment_confidence": 16.0 * scores.alignment_confidence,
        "physical_editability": 4.0 * scores.physical_editability,
        "virtual_target_penalty": -35.0 * scores.virtual_target_penalty,
        "document_context_penalty": -18.0 * scores.document_context_penalty,
        "ambiguity_penalty": -8.0 * scores.ambiguity_penalty,
    }
    final = sum(components.values())
    return {"final_score": round(final, 6), "score_components": components, "rank_tier": tier}
