# -*- coding: utf-8 -*-
"""Identifier match matrix tests."""

from __future__ import annotations

from document_ai.domain_packs.ec_sw.node_ranking import build_identifier_match_matrix
from document_ai.domain_packs.ec_sw.query_intent import parse_query_intent


def test_design_exact_primary():
    intent = parse_query_intent("설계 ID 4.2.2 검토")
    m = build_identifier_match_matrix(
        node_id="n1",
        intent=intent,
        row_requirement_ids=["Req. 2"],
        row_design_ids=["4.2.2"],
        row_test_ids=[],
    )
    assert m.primary_identifier_match
    assert m.exact_design_matches == ["4.2.2"]
    assert "PRIMARY_IDENTIFIER_EXACT" in m.reason_codes


def test_requirement_context_not_primary_for_design_query():
    intent = parse_query_intent("설계 ID 4.2.2 검토")
    m = build_identifier_match_matrix(
        node_id="n2",
        intent=intent,
        row_requirement_ids=["Req. 1"],
        row_design_ids=["4.2.1"],
        row_test_ids=[],
    )
    assert not m.primary_identifier_match
    assert not m.exact_design_matches
    # Req-only neighbor must not outrank design exact (checked in ranking tests)
    assert m.identifier_match_score < 10.0


def test_adjacent_origin_not_exact():
    intent = parse_query_intent("Req. 2 변경")
    m = build_identifier_match_matrix(
        node_id="n3",
        intent=intent,
        row_requirement_ids=["Req. 2"],
        row_design_ids=[],
        row_test_ids=[],
        identifier_origins={"requirement:Req. 2": "ADJACENT_CONTEXT"},
    )
    assert not m.exact_requirement_matches
    assert not m.primary_identifier_match


def test_local_cell_exact():
    intent = parse_query_intent("Req. 2 변경")
    m = build_identifier_match_matrix(
        node_id="n4",
        intent=intent,
        row_requirement_ids=["Req. 2"],
        row_design_ids=[],
        row_test_ids=[],
        identifier_origins={"requirement:Req. 2": "LOCAL_CELL"},
    )
    assert m.exact_requirement_matches == ["Req. 2"]


def test_test_exact():
    intent = parse_query_intent("시험 TC-12 검토")
    # force test id if extractor varies
    intent.test_ids = ["TC-12"]
    intent.primary_identifier_type = "TEST"
    m = build_identifier_match_matrix(
        node_id="n5",
        intent=intent,
        row_requirement_ids=[],
        row_design_ids=[],
        row_test_ids=["TC-12"],
    )
    assert m.primary_identifier_match
