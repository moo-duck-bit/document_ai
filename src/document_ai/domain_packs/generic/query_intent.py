# -*- coding: utf-8 -*-
"""Generic change-request query intent (deterministic, no LLM)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.template.concept_normalization import (
    MILESTONE,
    SCHEDULE,
    TABLE,
    TIMELINE,
    normalize_concepts,
    tokenize,
)

RequestedOperation = Literal["ADD", "UPDATE", "DELETE", "REPLACE", "REVIEW", "UNKNOWN"]

# Section / content concepts for generic docs
METHODOLOGY = "METHODOLOGY"
RESULTS = "RESULTS"
CONCLUSION = "CONCLUSION"
BUDGET = "BUDGET"
RISK = "RISK"
ORGANIZATION = "ORGANIZATION"
RECOMMENDATION = "RECOMMENDATION"
DATA_SOURCE = "DATA_SOURCE"
BACKGROUND = "BACKGROUND"
OBJECTIVES = "OBJECTIVES"
DISCUSSION = "DISCUSSION"
EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"

_SECTION_SYNONYMS: dict[str, frozenset[str]] = {
    METHODOLOGY: frozenset({"방법론", "방법", "methodology", "approach", "접근", "데이터 출처", "한계"}),
    RESULTS: frozenset({"결과", "results", "findings", "핵심 발견", "성과"}),
    CONCLUSION: frozenset({"결론", "conclusion", "conclusions", "맺음말"}),
    BUDGET: frozenset({"예산", "budget", "비용", "cost", "금액"}),
    RISK: frozenset({"위험", "리스크", "risk", "risks"}),
    ORGANIZATION: frozenset({"조직", "organization", "인력", "역할", "책임"}),
    RECOMMENDATION: frozenset({"권고", "권고사항", "recommendation", "제언"}),
    DATA_SOURCE: frozenset({"데이터 출처", "data source", "자료"}),
    BACKGROUND: frozenset({"배경", "background"}),
    OBJECTIVES: frozenset({"목표", "objective", "objectives", "목적"}),
    DISCUSSION: frozenset({"논의", "discussion"}),
    EXECUTIVE_SUMMARY: frozenset({"요약", "executive summary", "개요"}),
    SCHEDULE: frozenset({"일정", "schedule", "timeline", "타임라인", "추진일정"}),
    TABLE: frozenset({"표", "table"}),
    MILESTONE: frozenset({"마일스톤", "milestone"}),
    TIMELINE: frozenset({"timeline", "타임라인"}),
}

_ADD_RE = re.compile(r"추가|신설|insert|add\b|새로\s*넣", re.IGNORECASE)
_UPDATE_RE = re.compile(r"수정|갱신|변경|업데이트|update|revise|고쳐", re.IGNORECASE)
_DELETE_RE = re.compile(r"삭제|제거|delete|remove", re.IGNORECASE)
_REPLACE_RE = re.compile(r"교체|대체|replace", re.IGNORECASE)
_DOC_LEVEL_RE = re.compile(r"전체|문서\s*전반|document[- ]?wide|전반적", re.IGNORECASE)


@dataclass
class GenericQueryIntent:
    raw_change_request: str
    canonical_concepts: list[str] = field(default_factory=list)
    requested_operation: RequestedOperation = "UNKNOWN"
    requested_node_roles: list[str] = field(default_factory=list)
    target_section_concepts: list[str] = field(default_factory=list)
    intent_label: str = "UNKNOWN"
    table_intent: bool = False
    list_intent: bool = False
    add_intent: bool = False
    update_intent: bool = False
    delete_intent: bool = False
    document_level: bool = False
    ambiguity: bool = False
    confidence: float = 0.0
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _section_concepts_from_text(text: str) -> set[str]:
    low = (text or "").lower()
    compact = re.sub(r"\s+", "", low)
    tokens = re.findall(r"[a-z0-9가-힣]+", low)
    found: set[str] = set()
    for concept, syns in _SECTION_SYNONYMS.items():
        for syn in syns:
            s = syn.lower().strip()
            if not s:
                continue
            if " " in s:
                if s in low:
                    found.add(concept)
                    break
                continue
            # Prefer whole-token or startswith for short Hangul (결론 ⊂ 결론을)
            if s in tokens or any(tok.startswith(s) and len(s) >= 2 for tok in tokens):
                found.add(concept)
                break
            if len(s) >= 3 and (s in low or s.replace(" ", "") in compact):
                found.add(concept)
                break
    found |= normalize_concepts(text)
    return found


def parse_generic_query_intent(change_request: str) -> GenericQueryIntent:
    cr = change_request or ""
    concepts = sorted(_section_concepts_from_text(cr))
    reasons: list[str] = []
    op: RequestedOperation = "UNKNOWN"
    if _ADD_RE.search(cr):
        op = "ADD"
        reasons.append("op_add")
    elif _DELETE_RE.search(cr):
        op = "DELETE"
        reasons.append("op_delete")
    elif _REPLACE_RE.search(cr):
        op = "REPLACE"
        reasons.append("op_replace")
    elif _UPDATE_RE.search(cr):
        op = "UPDATE"
        reasons.append("op_update")
    else:
        op = "REVIEW"
        reasons.append("op_review_default")

    doc_level = bool(_DOC_LEVEL_RE.search(cr))
    table_intent = TABLE in concepts or SCHEDULE in concepts or BUDGET in concepts or bool(
        re.search(r"표|table|일정표", cr, re.IGNORECASE)
    )
    list_intent = bool(re.search(r"목록|리스트|list\b|항목", cr, re.IGNORECASE))

    section_concepts = [
        c
        for c in concepts
        if c
        in {
            METHODOLOGY,
            RESULTS,
            CONCLUSION,
            BUDGET,
            RISK,
            ORGANIZATION,
            RECOMMENDATION,
            DATA_SOURCE,
            BACKGROUND,
            OBJECTIVES,
            DISCUSSION,
            EXECUTIVE_SUMMARY,
            SCHEDULE,
            MILESTONE,
            TIMELINE,
        }
    ]

    roles: list[str] = []
    intent_label = "UNKNOWN"
    if doc_level and not section_concepts:
        intent_label = "DOCUMENT_LEVEL_REVIEW"
        roles = ["DOCUMENT_CONTEXT"]
    elif op == "ADD" and section_concepts:
        intent_label = "SECTION_ADD"
        roles = ["VIRTUAL_TARGET", "TEMPLATE_SECTION"]
    elif SCHEDULE in concepts or (table_intent and SCHEDULE in concepts):
        intent_label = "SCHEDULE_UPDATE" if op != "ADD" else "SECTION_ADD"
        roles = ["TABLE", "TABLE_CELL", "DOCUMENT_HEADING", "PARAGRAPH_BODY"]
    elif BUDGET in concepts:
        intent_label = "BUDGET_UPDATE"
        roles = ["TABLE", "TABLE_CELL", "DOCUMENT_HEADING", "PARAGRAPH_BODY"]
    elif table_intent and not section_concepts:
        intent_label = "TABLE_UPDATE"
        roles = ["TABLE", "TABLE_CELL"]
    elif list_intent:
        intent_label = "LIST_UPDATE"
        roles = ["LIST", "PARAGRAPH_BODY"]
    elif CONCLUSION in section_concepts:
        intent_label = "CONCLUSION_UPDATE"
        roles = ["PARAGRAPH_BODY", "DOCUMENT_HEADING", "TEMPLATE_SECTION"]
    elif METHODOLOGY in section_concepts:
        intent_label = "METHODOLOGY_UPDATE"
        roles = ["PARAGRAPH_BODY", "DOCUMENT_HEADING", "TEMPLATE_SECTION"]
    elif section_concepts:
        intent_label = "SECTION_UPDATE"
        roles = ["PARAGRAPH_BODY", "DOCUMENT_HEADING", "TEMPLATE_SECTION", "SECTION_CONTAINER"]
    elif op == "UPDATE":
        intent_label = "PARAGRAPH_UPDATE"
        roles = ["PARAGRAPH_BODY", "DOCUMENT_HEADING"]
    else:
        intent_label = "UNKNOWN"
        roles = ["DOCUMENT_CONTEXT", "PARAGRAPH_BODY"]

    conf = 0.35
    if section_concepts:
        conf += 0.35
    if op in {"ADD", "UPDATE", "DELETE", "REPLACE"}:
        conf += 0.2
    if doc_level and section_concepts:
        # ambiguous between doc-level and section
        reasons.append("ambiguous_doc_and_section")
    ambiguity = len(section_concepts) > 2 or (doc_level and bool(section_concepts))

    return GenericQueryIntent(
        raw_change_request=cr,
        canonical_concepts=concepts,
        requested_operation=op,
        requested_node_roles=roles,
        target_section_concepts=section_concepts,
        intent_label=intent_label,
        table_intent=table_intent,
        list_intent=list_intent,
        add_intent=op == "ADD",
        update_intent=op == "UPDATE",
        delete_intent=op == "DELETE",
        document_level=doc_level,
        ambiguity=ambiguity,
        confidence=min(1.0, conf),
        reason_codes=reasons + [f"intent:{intent_label}"],
    )


def annotate_structural_role(
    *,
    node_id: str,
    display_name: str = "",
    style: str = "",
    is_heading: bool = False,
    virtual_target: bool = False,
    template_only: bool = False,
    evidence_type: str = "",
) -> dict[str, Any]:
    nid = node_id or ""
    if virtual_target or template_only or (
        "." in nid and not nid.startswith(("heading_", "paragraph_", "table_"))
    ):
        role = "VIRTUAL_TARGET" if virtual_target and not template_only else "TEMPLATE_SECTION"
        if template_only:
            role = "TEMPLATE_SECTION"
        return {
            "structural_role": role,
            "editable": False,
            "physical": False,
            "virtual": role == "VIRTUAL_TARGET",
            "content_specificity": 0.2,
            "reason_codes": ["role_from_template_or_virtual"],
        }
    if nid.startswith("table_") or evidence_type in {"TABLE_STRUCTURE", "TABLE_HEADER_MATCH"}:
        if "cell" in nid.lower():
            role = "TABLE_CELL"
        else:
            role = "TABLE"
        return {
            "structural_role": role,
            "editable": True,
            "physical": True,
            "virtual": False,
            "content_specificity": 0.7,
            "reason_codes": ["role_table"],
        }
    if nid.startswith("heading_") or is_heading or "heading" in (style or "").lower():
        return {
            "structural_role": "DOCUMENT_HEADING",
            "editable": True,
            "physical": True,
            "virtual": False,
            "content_specificity": 0.45,
            "reason_codes": ["role_heading"],
        }
    if nid.startswith("list_"):
        return {
            "structural_role": "LIST",
            "editable": True,
            "physical": True,
            "virtual": False,
            "content_specificity": 0.55,
            "reason_codes": ["role_list"],
        }
    return {
        "structural_role": "PARAGRAPH_BODY",
        "editable": True,
        "physical": True,
        "virtual": False,
        "content_specificity": 0.65 if len(display_name or "") > 40 else 0.5,
        "reason_codes": ["role_paragraph"],
    }
