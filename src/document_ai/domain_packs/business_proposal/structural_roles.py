# -*- coding: utf-8 -*-
"""Business Proposal structural roles and table header classifiers."""

from __future__ import annotations

import re
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
from document_ai.template.concept_normalization import normalize_concepts

PROPOSAL_SECTION = "PROPOSAL_SECTION"
PROPOSAL_FIELD = "PROPOSAL_FIELD"
EXECUTION_PLAN_SECTION = "EXECUTION_PLAN_SECTION"
SCHEDULE_TABLE = "SCHEDULE_TABLE"
BUDGET_TABLE = "BUDGET_TABLE"
RISK_SECTION = "RISK_SECTION"
ORGANIZATION_SECTION = "ORGANIZATION_SECTION"
EXPECTED_EFFECT_SECTION = "EXPECTED_EFFECT_SECTION"
KPI_TABLE = "KPI_TABLE"
DELIVERABLE_LIST = "DELIVERABLE_LIST"
VIRTUAL_PROPOSAL_TARGET = "VIRTUAL_PROPOSAL_TARGET"
DOCUMENT_CONTEXT = "DOCUMENT_CONTEXT"
DOCUMENT_HEADING = "DOCUMENT_HEADING"
PARAGRAPH_BODY = "PARAGRAPH_BODY"
TABLE = "TABLE"
TABLE_CELL = "TABLE_CELL"
TEMPLATE_SECTION = "PROPOSAL_SECTION"

_SCHEDULE_HEADER_RE = re.compile(
    r"단계|기간|일정|주차|월|분기|시작|종료|마일스톤|schedule|timeline|phase",
    re.IGNORECASE,
)
_BUDGET_HEADER_RE = re.compile(
    r"항목|단가|금액|비용|예산|원|budget|cost|unit|amount|quantity",
    re.IGNORECASE,
)
_ORG_HEADER_RE = re.compile(
    r"조직|역할|담당|책임|인력|organization|role|responsibility|team",
    re.IGNORECASE,
)
_KPI_HEADER_RE = re.compile(
    r"kpi|지표|성과|목표|측정|metric|indicator|target",
    re.IGNORECASE,
)


def classify_table_header_role(header_text: str, *, blob: str = "") -> str | None:
    joined = f"{header_text}\n{blob}".strip()
    if not joined:
        return None
    hits = [
        (SCHEDULE_TABLE, _SCHEDULE_HEADER_RE.search(joined)),
        (BUDGET_TABLE, _BUDGET_HEADER_RE.search(joined)),
        (ORGANIZATION_SECTION, _ORG_HEADER_RE.search(joined)),
        (KPI_TABLE, _KPI_HEADER_RE.search(joined)),
    ]
    for role, matched in hits:
        if matched:
            return role
    return TABLE


def _section_role_from_template_node(template_node_id: str) -> str | None:
    tid = (template_node_id or "").lower()
    if ".execution_plan" in tid or tid.endswith(".execution_plan"):
        return EXECUTION_PLAN_SECTION
    if ".schedule" in tid:
        return PROPOSAL_SECTION
    if ".budget" in tid:
        return PROPOSAL_SECTION
    if ".risks" in tid:
        return RISK_SECTION
    if ".organization" in tid:
        return ORGANIZATION_SECTION
    if ".expected_outcomes" in tid:
        return EXPECTED_EFFECT_SECTION
    if ".deliverables" in tid or "deliverable" in tid:
        return DELIVERABLE_LIST
    if "business_proposal_v1." in tid:
        return PROPOSAL_SECTION
    return None


def _table_concept_role(concepts: set[str]) -> str | None:
    if SCHEDULE in concepts:
        return SCHEDULE_TABLE
    if BUDGET in concepts:
        return BUDGET_TABLE
    if KPI in concepts:
        return KPI_TABLE
    return None


def _section_concept_role(concepts: set[str]) -> str | None:
    if RISK_MANAGEMENT in concepts:
        return RISK_SECTION
    if ORGANIZATION in concepts:
        return ORGANIZATION_SECTION
    if EXPECTED_EFFECT in concepts:
        return EXPECTED_EFFECT_SECTION
    if SCHEDULE in concepts:
        return PROPOSAL_SECTION
    if BUDGET in concepts:
        return PROPOSAL_SECTION
    if KPI in concepts:
        return PROPOSAL_SECTION
    return None


def _concept_role(concepts: set[str]) -> str | None:
    """Prefer section roles; table roles only when already in table context."""
    return _section_concept_role(concepts) or _table_concept_role(concepts)

def annotate_proposal_structural_role(
    *,
    node_id: str,
    display_name: str = "",
    headers: list[str] | None = None,
    concepts: set[str] | None = None,
    template_node_id: str | None = None,
    style: str = "",
    is_heading: bool = False,
    virtual_target: bool = False,
    template_only: bool = False,
    evidence_type: str = "",
    table_role: str | None = None,
) -> dict[str, Any]:
    nid = node_id or ""
    blob = display_name or ""
    node_concepts = set(concepts or []) | normalize_proposal_concepts(blob) | normalize_concepts(blob)

    if virtual_target:
        return {
            "structural_role": VIRTUAL_PROPOSAL_TARGET,
            "proposal_structural_role": VIRTUAL_PROPOSAL_TARGET,
            "editable": False,
            "physical": False,
            "virtual": True,
            "content_specificity": 0.15,
            "reason_codes": ["role_virtual_proposal_target"],
        }

    if template_only or (
        "." in nid and not nid.startswith(("heading_", "paragraph_", "table_"))
    ):
        role = _section_role_from_template_node(nid) or PROPOSAL_SECTION
        if template_node_id:
            role = _section_role_from_template_node(template_node_id) or role
        return {
            "structural_role": role,
            "proposal_structural_role": role,
            "editable": False,
            "physical": False,
            "virtual": False,
            "content_specificity": 0.35,
            "reason_codes": ["role_proposal_template_section"],
        }

    if nid.startswith("table_") or evidence_type in {"TABLE_STRUCTURE", "TABLE_HEADER_MATCH"}:
        header_join = " ".join(headers or [])
        detected = table_role or classify_table_header_role(header_join, blob=blob)
        role = detected or _table_concept_role(node_concepts) or TABLE
        return {
            "structural_role": role,
            "proposal_structural_role": role,
            "editable": True,
            "physical": True,
            "virtual": False,
            "content_specificity": 0.75,
            "reason_codes": ["role_proposal_table", f"table_role:{role}"],
        }

    if nid.startswith("heading_") or is_heading or "heading" in (style or "").lower():
        # Headings stay headings / section containers — never table roles
        role = DOCUMENT_HEADING
        return {
            "structural_role": role,
            "proposal_structural_role": role,
            "editable": True,
            "physical": True,
            "virtual": False,
            "content_specificity": 0.45,
            "reason_codes": ["role_proposal_heading"],
            "canonical_concepts": sorted(node_concepts),
        }

    if nid.startswith("list_"):
        return {
            "structural_role": DELIVERABLE_LIST,
            "proposal_structural_role": DELIVERABLE_LIST,
            "editable": True,
            "physical": True,
            "virtual": False,
            "content_specificity": 0.55,
            "reason_codes": ["role_deliverable_list"],
        }

    concept_role = _section_concept_role(node_concepts)
    role = concept_role or PARAGRAPH_BODY
    return {
        "structural_role": role,
        "proposal_structural_role": role,
        "editable": True,
        "physical": True,
        "virtual": False,
        "content_specificity": 0.65 if len(blob) > 40 else 0.5,
        "reason_codes": ["role_proposal_paragraph"],
    }