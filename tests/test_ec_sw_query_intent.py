# -*- coding: utf-8 -*-
"""EC-SW query intent tests."""

from __future__ import annotations

from document_ai.domain_packs.ec_sw.query_intent import parse_query_intent


def test_requirement_only():
    i = parse_query_intent("Req. 101 추적성 갱신")
    assert i.primary_identifier_type == "REQUIREMENT"
    assert i.requirement_ids == ["Req. 101"]
    assert i.identifier_status == "SINGLE"


def test_design_only():
    i = parse_query_intent("설계 ID 4.2.2 관련 추적성 검토")
    assert i.primary_identifier_type == "DESIGN"
    assert "4.2.2" in i.design_ids
    assert i.requirement_ids == []


def test_test_only():
    i = parse_query_intent("시험 TC-12 결과 반영")
    assert i.primary_identifier_type == "TEST"
    assert any(t.startswith("TC") for t in i.test_ids)


def test_mixed_identifiers_with_design_hint():
    i = parse_query_intent("설계 4.2.2 및 Req. 2 연계 검토")
    assert i.primary_identifier_type == "DESIGN"
    assert i.requirement_ids
    assert i.design_ids


def test_no_identifier():
    i = parse_query_intent("사용자 인증 및 접근통제 보안 요구 변경")
    assert i.primary_identifier_type == "NONE"
    assert "no_identifier" in i.reason_codes


def test_malformed_identifier_excluded():
    i = parse_query_intent("REQ2 관련 변경")
    assert "Req. 2" not in i.requirement_ids
    assert "malformed_requirement_excluded" in i.reason_codes or i.primary_identifier_type == "NONE"


def test_primary_type_deterministic():
    a = parse_query_intent("설계 ID 4.2.2 검토").to_dict()
    b = parse_query_intent("설계 ID 4.2.2 검토").to_dict()
    assert a == b


def test_explicit_lists_merge():
    i = parse_query_intent("검토", requirement_ids=["Req. 3"], design_ids=["4.2.3"])
    assert "Req. 3" in i.requirement_ids
    assert "4.2.3" in i.design_ids
