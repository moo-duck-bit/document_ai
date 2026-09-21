# -*- coding: utf-8 -*-
"""Business Proposal query intent tests."""

from document_ai.domain_packs.business_proposal.concepts import (
    BUDGET,
    EXPECTED_EFFECT,
    KPI,
    ORGANIZATION,
    RISK_MANAGEMENT,
    SCHEDULE,
)
from document_ai.domain_packs.business_proposal.query_intent import (
    parse_business_proposal_query_intent,
)


def test_schedule_update_intent():
    i = parse_business_proposal_query_intent("수행 일정 표를 수정")
    assert i.primary_concept == SCHEDULE
    assert i.requested_operation == "UPDATE"
    assert i.update_intent
    assert i.table_intent
    assert any(r in i.requested_node_roles for r in ("TABLE", "SCHEDULE_TABLE", "TABLE_ROW", "TABLE_CELL"))


def test_budget_update_intent():
    i = parse_business_proposal_query_intent("예산 항목 표를 수정")
    assert i.primary_concept == BUDGET
    assert i.update_intent
    assert i.table_intent
    assert i.preferred_template_node_id == "business_proposal_v1.budget"


def test_risk_add_intent():
    i = parse_business_proposal_query_intent("위험 관리 절을 추가")
    assert i.primary_concept == RISK_MANAGEMENT
    assert i.add_intent
    assert i.requested_operation == "ADD"
    assert any(r in i.requested_node_roles for r in ("VIRTUAL_TARGET", "VIRTUAL_PROPOSAL_TARGET", "TEMPLATE_SECTION", "PROPOSAL_SECTION"))


def test_organization_update_intent():
    i = parse_business_proposal_query_intent("수행 조직 역할 분담을 수정")
    assert i.primary_concept == ORGANIZATION
    assert i.update_intent


def test_expected_effect_update_intent():
    i = parse_business_proposal_query_intent("기대효과 내용을 보강")
    assert i.primary_concept == EXPECTED_EFFECT
    assert i.update_intent or i.requested_operation in {"UPDATE", "REVIEW"}
    assert any(r in i.requested_node_roles for r in ("PARAGRAPH_BODY", "TEMPLATE_FIELD", "PROPOSAL_SECTION", "EXPECTED_EFFECT_SECTION"))


def test_kpi_table_update_intent():
    i = parse_business_proposal_query_intent("KPI 지표 표를 수정")
    assert i.primary_concept == KPI or KPI in i.canonical_concepts or i.table_intent
    assert i.table_intent or "TABLE" in i.requested_node_roles


def test_unknown_request_low_confidence():
    i = parse_business_proposal_query_intent("xyz unrelated blah")
    assert i.primary_concept is None or i.confidence < 0.7
    assert i.intent_label in {"UNKNOWN", "REVIEW", "DOCUMENT_LEVEL_REVIEW"} or i.ambiguity or not i.primary_concept


def test_to_generic_intent_maps_risk():
    i = parse_business_proposal_query_intent("위험 관리 수정")
    g = i.to_generic_intent()
    assert "RISK" in g.canonical_concepts or "RISK" in g.target_section_concepts


def test_schedule_synonyms():
    for cr in ("추진 일정 수정", "사업 일정 변경", "로드맵 업데이트", "execution schedule update"):
        i = parse_business_proposal_query_intent(cr)
        assert i.primary_concept == SCHEDULE, cr


def test_budget_synonyms():
    for cr in ("소요 예산 수정", "사업비 변경", "cost table update"):
        i = parse_business_proposal_query_intent(cr)
        assert i.primary_concept == BUDGET, cr


def test_risk_synonyms():
    for cr in ("리스크 대응 방안 수정", "risk mitigation update"):
        i = parse_business_proposal_query_intent(cr)
        assert i.primary_concept == RISK_MANAGEMENT, cr


def test_org_synonyms():
    for cr in ("추진 체계 수정", "organization roles update"):
        i = parse_business_proposal_query_intent(cr)
        assert i.primary_concept == ORGANIZATION, cr


def test_effect_synonyms():
    for cr in ("정량적 효과 보강", "expected impact update"):
        i = parse_business_proposal_query_intent(cr)
        assert i.primary_concept == EXPECTED_EFFECT, cr
