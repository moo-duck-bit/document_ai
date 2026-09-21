# -*- coding: utf-8 -*-
from document_ai.domain_packs.generic.query_intent import parse_generic_query_intent


def test_methodology_update():
    i = parse_generic_query_intent("방법론 섹션을 수정한다")
    assert i.intent_label == "METHODOLOGY_UPDATE"
    assert i.update_intent or i.requested_operation in {"UPDATE", "REVIEW"}
    assert "METHODOLOGY" in i.target_section_concepts


def test_conclusion_update():
    i = parse_generic_query_intent("결론을 갱신해 주세요")
    assert i.intent_label == "CONCLUSION_UPDATE"
    assert "CONCLUSION" in i.target_section_concepts


def test_schedule_update():
    i = parse_generic_query_intent("일정 표를 수정한다")
    assert i.intent_label == "SCHEDULE_UPDATE"
    assert i.table_intent


def test_budget_update():
    i = parse_generic_query_intent("예산 항목을 업데이트")
    assert i.intent_label == "BUDGET_UPDATE"


def test_section_add():
    i = parse_generic_query_intent("결론 섹션을 추가한다")
    assert i.intent_label == "SECTION_ADD"
    assert i.add_intent


def test_table_update():
    i = parse_generic_query_intent("표를 수정한다")
    assert i.intent_label == "TABLE_UPDATE" or i.table_intent


def test_document_level_review():
    i = parse_generic_query_intent("문서 전반을 검토한다")
    assert i.intent_label == "DOCUMENT_LEVEL_REVIEW"
    assert i.document_level


def test_unknown_request():
    i = parse_generic_query_intent("xyzabc qwerty")
    assert i.intent_label in {"UNKNOWN", "PARAGRAPH_UPDATE", "DOCUMENT_LEVEL_REVIEW"}
