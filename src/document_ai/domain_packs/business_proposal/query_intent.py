# -*- coding: utf-8 -*-
"""Business Proposal change-request query intent (deterministic, no LLM)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.domain_packs.business_proposal.concepts import (
    BUDGET,
    EXPECTED_EFFECT,
    KPI,
    ORGANIZATION,
    RISK_MANAGEMENT,
    SCHEDULE,
    TABLE,
    normalize_proposal_concepts,
    template_node_for_concepts,
)
from document_ai.domain_packs.generic.query_intent import (
    GenericQueryIntent,
    RequestedOperation,
)
from document_ai.template.concept_normalization import (
    RISK,
    normalize_concepts,
)

_ADD_RE = re.compile(r"추가|신설|insert|add\b|새로\s*넣", re.IGNORECASE)
_UPDATE_RE = re.compile(r"수정|갱신|변경|업데이트|update|revise|고쳐|조정", re.IGNORECASE)
_DELETE_RE = re.compile(r"삭제|제거|delete|remove", re.IGNORECASE)
_REPLACE_RE = re.compile(r"교체|대체|replace", re.IGNORECASE)
_REVIEW_RE = re.compile(r"검토|review|확인", re.IGNORECASE)


def _proposal_to_generic_concept(concept: str) -> str:
    if concept == RISK_MANAGEMENT:
        return RISK
    return concept


@dataclass
class BusinessProposalQueryIntent:
    raw_change_request: str
    requested_operation: RequestedOperation = "UNKNOWN"
    primary_concept: str | None = None
    secondary_concepts: list[str] = field(default_factory=list)
    requested_node_roles: list[str] = field(default_factory=list)
    table_intent: bool = False
    section_intent: bool = False
    paragraph_intent: bool = False
    add_intent: bool = False
    update_intent: bool = False
    review_intent: bool = False
    ambiguity: bool = False
    confidence: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    canonical_concepts: list[str] = field(default_factory=list)
    intent_label: str = "UNKNOWN"
    preferred_template_node_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_generic_intent(self) -> GenericQueryIntent:
        generic_concepts = sorted(
            {_proposal_to_generic_concept(c) for c in self.canonical_concepts}
            | normalize_concepts(self.raw_change_request)
        )
        target = [
            _proposal_to_generic_concept(c)
            for c in ([self.primary_concept] if self.primary_concept else [])
            + self.secondary_concepts
            if c
        ]
        return GenericQueryIntent(
            raw_change_request=self.raw_change_request,
            canonical_concepts=generic_concepts,
            requested_operation=self.requested_operation,
            requested_node_roles=list(self.requested_node_roles),
            target_section_concepts=target,
            intent_label=self.intent_label,
            table_intent=self.table_intent,
            list_intent=any(r in {"LIST", "DELIVERABLE_LIST"} for r in self.requested_node_roles),
            add_intent=self.add_intent,
            update_intent=self.update_intent,
            delete_intent=self.requested_operation == "DELETE",
            document_level=False,
            ambiguity=self.ambiguity,
            confidence=self.confidence,
            reason_codes=list(self.reason_codes),
        )


def _detect_operation(cr: str) -> tuple[RequestedOperation, list[str]]:
    reasons: list[str] = []
    if _ADD_RE.search(cr):
        return "ADD", reasons + ["op_add"]
    if _DELETE_RE.search(cr):
        return "DELETE", reasons + ["op_delete"]
    if _REPLACE_RE.search(cr):
        return "REPLACE", reasons + ["op_replace"]
    if _UPDATE_RE.search(cr):
        return "UPDATE", reasons + ["op_update"]
    if _REVIEW_RE.search(cr):
        return "REVIEW", reasons + ["op_review"]
    return "REVIEW", reasons + ["op_review_default"]


def _rank_primary(concepts: set[str]) -> tuple[str | None, list[str]]:
    priority = [
        SCHEDULE,
        BUDGET,
        RISK_MANAGEMENT,
        ORGANIZATION,
        EXPECTED_EFFECT,
        KPI,
    ]
    primary: str | None = None
    for c in priority:
        if c in concepts:
            primary = c
            break
    secondary = sorted(c for c in concepts if c != primary and c != TABLE)
    return primary, secondary


def parse_business_proposal_query_intent(change_request: str) -> BusinessProposalQueryIntent:
    cr = change_request or ""
    proposal_concepts = normalize_proposal_concepts(cr)
    generic_concepts = normalize_concepts(cr)
    concepts = proposal_concepts | generic_concepts
    canonical = sorted(concepts | generic_concepts)
    op, reasons = _detect_operation(cr)
    primary, secondary = _rank_primary(concepts)

    table_intent = TABLE in concepts or primary in {SCHEDULE, BUDGET, KPI} or bool(
        re.search(r"표|table|일정표|예산표", cr, re.IGNORECASE)
    )
    section_intent = primary is not None or bool(
        {RISK_MANAGEMENT, ORGANIZATION, EXPECTED_EFFECT} & concepts
    )
    paragraph_intent = primary in {RISK_MANAGEMENT, EXPECTED_EFFECT, ORGANIZATION} or bool(
        re.search(r"본문|문단|paragraph", cr, re.IGNORECASE)
    )

    roles: list[str] = []
    intent_label = "UNKNOWN"

    if primary == SCHEDULE or (table_intent and SCHEDULE in concepts):
        intent_label = "SCHEDULE_UPDATE" if op != "ADD" else "SCHEDULE_ADD"
        roles = ["SCHEDULE_TABLE", "TABLE", "PROPOSAL_SECTION", "DOCUMENT_HEADING"]
        reasons.append("intent_schedule")
    elif primary == BUDGET or (table_intent and BUDGET in concepts):
        intent_label = "BUDGET_UPDATE" if op != "ADD" else "BUDGET_ADD"
        roles = ["BUDGET_TABLE", "TABLE", "PROPOSAL_SECTION", "DOCUMENT_HEADING"]
        reasons.append("intent_budget")
    elif primary == KPI:
        intent_label = "KPI_UPDATE" if op != "ADD" else "KPI_ADD"
        roles = ["KPI_TABLE", "TABLE", "PROPOSAL_SECTION", "PARAGRAPH_BODY"]
        reasons.append("intent_kpi")
    elif primary == RISK_MANAGEMENT:
        if op == "ADD":
            intent_label = "RISK_ADD"
            roles = ["VIRTUAL_PROPOSAL_TARGET", "PROPOSAL_SECTION", "RISK_SECTION", "PARAGRAPH_BODY"]
        else:
            intent_label = "RISK_UPDATE"
            roles = ["RISK_SECTION", "PROPOSAL_SECTION", "PARAGRAPH_BODY", "DOCUMENT_HEADING"]
        reasons.append("intent_risk")
    elif primary == ORGANIZATION:
        intent_label = "ORGANIZATION_UPDATE" if op != "ADD" else "ORGANIZATION_ADD"
        roles = ["ORGANIZATION_SECTION", "PROPOSAL_SECTION", "TABLE", "PARAGRAPH_BODY"]
        reasons.append("intent_organization")
    elif primary == EXPECTED_EFFECT:
        intent_label = "EXPECTED_EFFECT_UPDATE" if op != "ADD" else "EXPECTED_EFFECT_ADD"
        roles = ["EXPECTED_EFFECT_SECTION", "PROPOSAL_SECTION", "PARAGRAPH_BODY"]
        reasons.append("intent_expected_effect")
    elif op == "ADD":
        intent_label = "SECTION_ADD"
        roles = ["VIRTUAL_PROPOSAL_TARGET", "PROPOSAL_SECTION"]
    else:
        intent_label = "PROPOSAL_REVIEW"
        roles = ["PROPOSAL_SECTION", "PARAGRAPH_BODY", "DOCUMENT_HEADING", "DOCUMENT_CONTEXT"]

    if op == "ADD" and "VIRTUAL_PROPOSAL_TARGET" not in roles:
        roles = ["VIRTUAL_PROPOSAL_TARGET"] + roles

    conf = 0.35
    if primary:
        conf += 0.35
    if op in {"ADD", "UPDATE", "DELETE", "REPLACE"}:
        conf += 0.2
    ambiguity = len(concepts) > 3 or (primary and len(secondary) >= 2)
    if ambiguity:
        reasons.append("ambiguous_multi_concept")

    preferred = template_node_for_concepts({c for c in ([primary] if primary else []) + secondary})

    return BusinessProposalQueryIntent(
        raw_change_request=cr,
        requested_operation=op,
        primary_concept=primary,
        secondary_concepts=secondary,
        requested_node_roles=roles,
        table_intent=table_intent,
        section_intent=section_intent,
        paragraph_intent=paragraph_intent,
        add_intent=op == "ADD",
        update_intent=op == "UPDATE",
        review_intent=op == "REVIEW",
        ambiguity=ambiguity,
        confidence=min(1.0, conf),
        reason_codes=reasons + [f"intent:{intent_label}"],
        canonical_concepts=canonical,
        intent_label=intent_label,
        preferred_template_node_id=preferred,
    )
