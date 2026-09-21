# -*- coding: utf-8 -*-
"""Business Proposal structural match / table role tests."""

from document_ai.domain_packs.business_proposal.query_intent import parse_business_proposal_query_intent
from document_ai.domain_packs.business_proposal.structural_match import (
    score_proposal_structural_match,
)
from document_ai.domain_packs.business_proposal.structural_roles import (
    BUDGET_TABLE,
    EXPECTED_EFFECT_SECTION,
    KPI_TABLE,
    ORGANIZATION_SECTION,
    RISK_SECTION,
    SCHEDULE_TABLE,
    annotate_proposal_structural_role,
    classify_table_header_role,
)


def test_schedule_table_role_from_headers():
    role = classify_table_header_role("단계 | 기간 | 시작 | 종료")
    assert role == SCHEDULE_TABLE


def test_budget_table_role_from_headers():
    role = classify_table_header_role("항목 | 단가 | 수량 | 금액")
    assert role == BUDGET_TABLE


def test_organization_table_role_from_headers():
    role = classify_table_header_role("조직 | 역할 | 담당 | 책임")
    assert role in {ORGANIZATION_SECTION, "ORGANIZATION_TABLE", "TABLE"}


def test_kpi_table_role_from_headers():
    role = classify_table_header_role("KPI | 목표 | 지표 | 측정")
    assert role == KPI_TABLE


def test_risk_paragraph_role():
    ann = annotate_proposal_structural_role(
        node_id="paragraph_0012",
        display_name="위험 대응 방안을 수립한다",
        concepts={"RISK_MANAGEMENT"},
    )
    assert ann["structural_role"] in {RISK_SECTION, "PARAGRAPH_BODY"}


def test_expected_effect_paragraph_role():
    ann = annotate_proposal_structural_role(
        node_id="paragraph_0020",
        display_name="기대효과로 비용 절감이 예상된다",
        concepts={"EXPECTED_EFFECT"},
    )
    assert ann["structural_role"] in {EXPECTED_EFFECT_SECTION, "PARAGRAPH_BODY", "PROPOSAL_SECTION"}


def test_deliverable_list_role():
    ann = annotate_proposal_structural_role(
        node_id="list_0001",
        display_name="산출물 목록",
        concepts={"DELIVERABLE"},
    )
    assert ann["structural_role"] in {"DELIVERABLE_LIST", "LIST", "PARAGRAPH_BODY"}


def test_budget_table_beats_schedule_in_scores():
    intent = parse_business_proposal_query_intent("예산 표를 수정")
    budget = {
        "node_id": "table_01",
        "display_name": "항목 단가 금액",
        "metadata": {
            "structural_role": BUDGET_TABLE,
            "canonical_concepts": ["BUDGET", "TABLE"],
            "physical": True,
        },
    }
    schedule = {
        "node_id": "table_00",
        "display_name": "단계 기간 일정",
        "metadata": {
            "structural_role": SCHEDULE_TABLE,
            "canonical_concepts": ["SCHEDULE", "TABLE"],
            "physical": True,
        },
    }
    sb = score_proposal_structural_match(budget, intent=intent)
    ss = score_proposal_structural_match(schedule, intent=intent)
    assert sb.primary_concept_match >= ss.primary_concept_match
    assert sb.table_header_match >= ss.table_header_match or sb.structural_role_match > ss.structural_role_match


def test_risk_paragraph_beats_document_context():
    intent = parse_business_proposal_query_intent("위험 대응 방안 수정")
    para = {
        "node_id": "paragraph_0008",
        "display_name": "위험 완화 방안",
        "metadata": {
            "structural_role": "PARAGRAPH_BODY",
            "canonical_concepts": ["RISK_MANAGEMENT"],
            "physical": True,
            "content_specificity": 0.8,
        },
    }
    ctx = {
        "node_id": "document_context",
        "display_name": "문서 전반",
        "metadata": {
            "structural_role": "DOCUMENT_CONTEXT",
            "canonical_concepts": [],
            "physical": False,
        },
    }
    sp = score_proposal_structural_match(para, intent=intent)
    sc = score_proposal_structural_match(ctx, intent=intent)
    assert sp.primary_concept_match > sc.primary_concept_match
    assert sc.document_context_penalty >= sp.document_context_penalty


def test_annotate_schedule_table_node():
    ann = annotate_proposal_structural_role(
        node_id="table_00",
        display_name="단계 기간",
        headers=["단계", "기간", "일정"],
        evidence_type="TABLE_STRUCTURE",
    )
    assert ann["structural_role"] == SCHEDULE_TABLE
    assert ann["physical"] is True
