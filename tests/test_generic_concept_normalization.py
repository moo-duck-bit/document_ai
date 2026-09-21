# -*- coding: utf-8 -*-
"""Concept normalization tests."""

from __future__ import annotations

from document_ai.template.concept_normalization import (
    MILESTONE,
    SCHEDULE,
    TABLE,
    TIMELINE,
    extract_time_unit_hits,
    normalize_concepts,
)


def test_schedule_synonyms():
    for text in ("일정", "일정표", "추진 일정", "수행 일정", "schedule"):
        assert SCHEDULE in normalize_concepts(text)


def test_timeline_concept():
    c = normalize_concepts("project timeline 타임라인")
    assert TIMELINE in c or SCHEDULE in c


def test_milestone_concept():
    assert MILESTONE in normalize_concepts("주요 마일스톤 추가")


def test_table_concept():
    assert TABLE in normalize_concepts("결과 표 수정")
    assert TABLE in normalize_concepts("update the table")


def test_schedule_table_compound():
    c = normalize_concepts("일정표 업데이트")
    assert SCHEDULE in c and TABLE in c


def test_deterministic_normalization():
    assert normalize_concepts("일정 표") == normalize_concepts("일정 표")


def test_unrelated_no_concept():
    assert normalize_concepts("사무실 화분 배치 XYZABC") == set()


def test_execution_plan_concept():
    from document_ai.template.concept_normalization import EXECUTION_PLAN

    assert EXECUTION_PLAN in normalize_concepts("수행 계획 단계")


def test_security_domain_concepts_present():
    from document_ai.template.concept_normalization import AUTHENTICATION, SECURITY

    c = normalize_concepts("보안 인증")
    assert SECURITY in c and AUTHENTICATION in c
