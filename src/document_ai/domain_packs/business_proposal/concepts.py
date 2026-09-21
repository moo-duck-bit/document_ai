# -*- coding: utf-8 -*-
"""Business Proposal canonical concepts and synonyms."""

from __future__ import annotations

import re

PROBLEM_DEFINITION = "PROBLEM_DEFINITION"
PROPOSAL_OVERVIEW = "PROPOSAL_OVERVIEW"
OBJECTIVE = "OBJECTIVE"
SCOPE = "SCOPE"
EXECUTION_PLAN = "EXECUTION_PLAN"
SCHEDULE = "SCHEDULE"
MILESTONE = "MILESTONE"
BUDGET = "BUDGET"
COST = "COST"
RISK_MANAGEMENT = "RISK_MANAGEMENT"
ORGANIZATION = "ORGANIZATION"
RESPONSIBILITY = "RESPONSIBILITY"
EXPECTED_EFFECT = "EXPECTED_EFFECT"
DELIVERABLE = "DELIVERABLE"
KPI = "KPI"
STRATEGY = "STRATEGY"
MARKET = "MARKET"
COMPETITOR = "COMPETITOR"
RESOURCE = "RESOURCE"
GOVERNANCE = "GOVERNANCE"
TABLE = "TABLE"

PROPOSAL_SYNONYMS: dict[str, frozenset[str]] = {
    PROBLEM_DEFINITION: frozenset({"문제", "문제정의", "현황", "problem", "challenge"}),
    PROPOSAL_OVERVIEW: frozenset({"제안", "개요", "overview", "제안 개요", "사업 제안"}),
    OBJECTIVE: frozenset({"목표", "objective", "목적"}),
    SCOPE: frozenset({"범위", "scope"}),
    EXECUTION_PLAN: frozenset({"수행계획", "수행 계획", "추진계획", "실행 계획", "execution plan"}),
    SCHEDULE: frozenset(
        {
            "일정",
            "수행 일정",
            "추진 일정",
            "사업 일정",
            "단계별 일정",
            "실행 일정",
            "로드맵",
            "timeline",
            "schedule",
            "execution schedule",
        }
    ),
    MILESTONE: frozenset({"마일스톤", "milestone", "주요단계"}),
    BUDGET: frozenset({"예산", "소요 예산", "사업비", "budget"}),
    COST: frozenset({"비용", "원가", "단가", "금액", "cost", "인건비", "장비"}),
    RISK_MANAGEMENT: frozenset(
        {"위험", "리스크", "위험 관리", "위험관리", "대응 방안", "risk", "mitigation", "risk management"}
    ),
    ORGANIZATION: frozenset(
        {"수행 조직", "수행조직", "추진 체계", "역할 분담", "조직", "organization", "governance"}
    ),
    RESPONSIBILITY: frozenset({"역할", "담당", "책임", "responsibility", "role"}),
    EXPECTED_EFFECT: frozenset(
        {
            "기대 효과",
            "기대효과",
            "정량적 효과",
            "정성적 효과",
            "예상 성과",
            "benefits",
            "expected impact",
            "expected outcomes",
            "outcomes",
        }
    ),
    DELIVERABLE: frozenset({"산출물", "deliverable", "deliverables"}),
    KPI: frozenset({"kpi", "지표", "성과지표", "측정"}),
    STRATEGY: frozenset({"전략", "strategy"}),
    MARKET: frozenset({"시장", "market"}),
    COMPETITOR: frozenset({"경쟁", "competitor"}),
    RESOURCE: frozenset({"자원", "인력", "resource"}),
    GOVERNANCE: frozenset({"거버넌스", "governance", "추진 체계"}),
    TABLE: frozenset({"표", "table"}),
}

# Map concept → preferred template section id under business_proposal_v1
CONCEPT_TO_TEMPLATE_SECTION: dict[str, str] = {
    SCHEDULE: "schedule",
    MILESTONE: "schedule",
    EXECUTION_PLAN: "execution_plan",
    BUDGET: "budget",
    COST: "budget",
    RISK_MANAGEMENT: "risks",
    ORGANIZATION: "organization",
    RESPONSIBILITY: "organization",
    GOVERNANCE: "organization",
    EXPECTED_EFFECT: "expected_outcomes",
    DELIVERABLE: "expected_outcomes",
    KPI: "expected_outcomes",
    PROBLEM_DEFINITION: "problem_statement",
    PROPOSAL_OVERVIEW: "overview",
    SCOPE: "scope",
    OBJECTIVE: "overview",
}

TEMPLATE_ID = "business_proposal_v1"


def normalize_proposal_concepts(text: str) -> set[str]:
    low = (text or "").lower()
    compact = re.sub(r"\s+", "", low)
    tokens = re.findall(r"[a-z0-9가-힣]+", low)
    found: set[str] = set()
    for concept, syns in PROPOSAL_SYNONYMS.items():
        for syn in syns:
            s = syn.lower().strip()
            if not s:
                continue
            if " " in s:
                if s in low:
                    found.add(concept)
                    break
                continue
            if s in tokens or any(tok.startswith(s) and len(s) >= 2 for tok in tokens):
                found.add(concept)
                break
            if len(s) >= 3 and (s in low or s.replace(" ", "") in compact):
                found.add(concept)
                break
    return found


def template_node_for_concepts(concepts: set[str] | list[str]) -> str | None:
    for c in (
        SCHEDULE,
        BUDGET,
        RISK_MANAGEMENT,
        ORGANIZATION,
        EXPECTED_EFFECT,
        EXECUTION_PLAN,
        KPI,
        COST,
    ):
        if c in concepts:
            sec = CONCEPT_TO_TEMPLATE_SECTION.get(c)
            if sec:
                return f"{TEMPLATE_ID}.{sec}"
    for c, sec in CONCEPT_TO_TEMPLATE_SECTION.items():
        if c in set(concepts):
            return f"{TEMPLATE_ID}.{sec}"
    return None
