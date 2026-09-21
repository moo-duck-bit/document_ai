# -*- coding: utf-8 -*-
"""Business Proposal node ranking tests."""

from document_ai.domain_packs.business_proposal.query_intent import parse_business_proposal_query_intent
from document_ai.domain_packs.business_proposal.node_ranking import rank_business_proposal_candidates
from document_ai.domain_packs.business_proposal.structural_roles import (
    BUDGET_TABLE,
    DOCUMENT_CONTEXT,
    PROPOSAL_SECTION,
    SCHEDULE_TABLE,
    VIRTUAL_PROPOSAL_TARGET,
)


def _cand(nid, role, concepts, **meta):
    return {
        "node_id": nid,
        "status": "REVIEW_REQUIRED",
        "display_name": nid,
        "metadata": {
            "structural_role": role,
            "canonical_concepts": concepts,
            "physical": role not in {PROPOSAL_SECTION, VIRTUAL_PROPOSAL_TARGET, DOCUMENT_CONTEXT},
            "writer_executable": False,
            **meta,
        },
    }


def test_schedule_table_beats_generic_heading():
    intent = parse_business_proposal_query_intent("수행 일정 표를 수정")
    cands = [
        _cand("heading_0001", "DOCUMENT_HEADING", ["SCHEDULE"]),
        _cand("table_00", SCHEDULE_TABLE, ["SCHEDULE", "TABLE"], content_specificity=0.8),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] == "table_00"


def test_budget_table_beats_schedule_table():
    intent = parse_business_proposal_query_intent("예산 표를 수정")
    cands = [
        _cand("table_00", SCHEDULE_TABLE, ["SCHEDULE", "TABLE"]),
        _cand("table_01", BUDGET_TABLE, ["BUDGET", "TABLE"]),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] == "table_01"


def test_risk_paragraph_beats_document_context():
    intent = parse_business_proposal_query_intent("위험 대응 수정")
    cands = [
        _cand("document_context", DOCUMENT_CONTEXT, []),
        _cand("paragraph_0008", "PARAGRAPH_BODY", ["RISK_MANAGEMENT"], content_specificity=0.85),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] == "paragraph_0008"


def test_expected_effect_section_ranks_high():
    intent = parse_business_proposal_query_intent("기대효과 내용을 보강")
    cands = [
        _cand(
            "business_proposal_v1.expected_outcomes",
            PROPOSAL_SECTION,
            ["EXPECTED_EFFECT"],
            evaluation_equivalent=True,
            alignment_confidence=0.9,
        ),
        _cand("heading_0099", "DOCUMENT_HEADING", ["SCHEDULE"]),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] == "business_proposal_v1.expected_outcomes"


def test_virtual_target_only_for_add_not_top_on_update():
    intent = parse_business_proposal_query_intent("예산 수정")
    cands = [
        _cand(
            "business_proposal_v1.budget",
            VIRTUAL_PROPOSAL_TARGET,
            ["BUDGET"],
            virtual=True,
            physical=False,
        ),
        _cand("heading_0004", "DOCUMENT_HEADING", ["BUDGET"], physical=True),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] != "business_proposal_v1.budget" or out[
        "ranking_candidates"
    ][0]["structural_role"] != VIRTUAL_PROPOSAL_TARGET
    assert out["validation"]["virtual_target_only_for_add"]


def test_virtual_allowed_for_add():
    intent = parse_business_proposal_query_intent("신규 거버넌스 절을 추가")
    cands = [
        _cand(
            "business_proposal_v1.organization",
            VIRTUAL_PROPOSAL_TARGET,
            ["ORGANIZATION"],
            virtual=True,
            physical=False,
        ),
        _cand("paragraph_0001", "PARAGRAPH_BODY", [], physical=True),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["validation"]["virtual_target_only_for_add"]
    # ADD may prefer virtual/template
    top = out["ranking_candidates"][0]
    assert top["node_id"] in {
        "business_proposal_v1.organization",
        "paragraph_0001",
    }


def test_exact_physical_beats_template_only_when_unaligned_weak():
    intent = parse_business_proposal_query_intent("예산 표를 수정")
    cands = [
        _cand(
            "business_proposal_v1.appendix",
            PROPOSAL_SECTION,
            [],
            evaluation_equivalent=False,
            alignment_confidence=0.1,
            template_only=True,
        ),
        _cand("table_01", BUDGET_TABLE, ["BUDGET", "TABLE"], physical=True, content_specificity=0.9),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] == "table_01"


def test_template_section_beats_heading_on_update():
    intent = parse_business_proposal_query_intent("일정 수정")
    cands = [
        _cand("heading_0001", "DOCUMENT_HEADING", ["SCHEDULE"], physical=True),
        _cand(
            "business_proposal_v1.schedule",
            PROPOSAL_SECTION,
            ["SCHEDULE"],
            evaluation_equivalent=True,
            alignment_confidence=0.9,
        ),
    ]
    out = rank_business_proposal_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] == "business_proposal_v1.schedule"


def test_deterministic_ranking():
    intent = parse_business_proposal_query_intent("예산 수정")
    cands = [
        _cand("table_01", BUDGET_TABLE, ["BUDGET"]),
        _cand("heading_0004", "DOCUMENT_HEADING", ["BUDGET"]),
        _cand(
            "business_proposal_v1.budget",
            PROPOSAL_SECTION,
            ["BUDGET"],
            evaluation_equivalent=True,
            alignment_confidence=0.9,
        ),
    ]
    a = rank_business_proposal_candidates([dict(c, metadata=dict(c["metadata"])) for c in cands], intent=intent)
    b = rank_business_proposal_candidates([dict(c, metadata=dict(c["metadata"])) for c in cands], intent=intent)
    assert [r["node_id"] for r in a["ranking_candidates"]] == [r["node_id"] for r in b["ranking_candidates"]]


def test_writer_never_executable():
    intent = parse_business_proposal_query_intent("일정 수정")
    cands = [_cand("table_00", SCHEDULE_TABLE, ["SCHEDULE"])]
    rank_business_proposal_candidates(cands, intent=intent)
    assert cands[0]["metadata"]["writer_executable"] is False
    assert cands[0]["metadata"].get("supports_patch") is False
