# -*- coding: utf-8 -*-
"""EC-SW node ranking tier tests."""

from __future__ import annotations

from document_ai.domain_packs.ec_sw.node_ranking import (
    assign_rank_tier,
    build_identifier_match_matrix,
    rank_mdtm_candidates,
    score_candidate,
)
from document_ai.domain_packs.ec_sw.query_intent import parse_query_intent


def _cand(nid, status, *, reqs=None, designs=None, tests=None, overlap=0.0, row_text=""):
    return {
        "node_id": nid,
        "status": status,
        "matched_requirement_ids": reqs or [],
        "reason_codes": [],
        "human_review_required": True,
        "metadata": {
            "overlap": overlap,
            "row_text": row_text,
            "row_requirement_ids": reqs or [],
            "row_design_ids": designs or [],
            "row_test_ids": tests or [],
            "identifier_origins": {
                **{f"requirement:{r}": "LOCAL_CELL" for r in (reqs or [])},
                **{f"design:{d}": "LOCAL_CELL" for d in (designs or [])},
                **{f"test:{t}": "LOCAL_CELL" for t in (tests or [])},
            },
            "table_index": 3,
            "row_index": int(nid.split("_")[-1]) if nid.split("_")[-1].isdigit() else 0,
        },
    }


def test_primary_exact_beats_semantic():
    intent = parse_query_intent("Req. 2 갱신")
    cands = [
        _cand("row_a", "REVIEW_REQUIRED", reqs=["Req. 1"], overlap=0.9, row_text="인증 보안"),
        _cand("row_b", "PATCH_CANDIDATE", reqs=["Req. 2"], overlap=0.1, row_text="Req. 2"),
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 2 갱신")
    assert out["ranking_results"]["ranked_node_ids"][0] == "row_b"
    assert cands[1]["metadata"]["rank_tier"] in {0, 1}


def test_design_exact_beats_requirement_context():
    intent = parse_query_intent("설계 ID 4.2.2 검토")
    cands = [
        _cand("row_wrong", "REVIEW_REQUIRED", reqs=["Req. 1"], designs=["4.2.1"], overlap=0.5),
        _cand("row_right", "REVIEW_REQUIRED", reqs=["Req. 2"], designs=["4.2.2"], overlap=0.1),
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="설계 ID 4.2.2 검토")
    assert out["ranking_results"]["ranked_node_ids"][0] == "row_right"


def test_test_exact_beats_unrelated_req():
    intent = parse_query_intent("시험")
    intent.test_ids = ["TC-9"]
    intent.primary_identifier_type = "TEST"
    intent.identifier_status = "SINGLE"
    cands = [
        _cand("row_req", "REVIEW_REQUIRED", reqs=["Req. 1"], overlap=0.8),
        _cand("row_test", "REVIEW_REQUIRED", tests=["TC-9"], overlap=0.1),
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="시험 TC-9")
    assert out["ranking_results"]["ranked_node_ids"][0] == "row_test"


def test_row_local_beats_adjacent_context():
    intent = parse_query_intent("Req. 2 변경")
    local = _cand("local", "PATCH_CANDIDATE", reqs=["Req. 2"], overlap=0.1)
    adj = _cand("adj", "REVIEW_REQUIRED", reqs=[], overlap=0.5)
    adj["metadata"]["evidence_scopes"] = ["ADJACENT_ROW"]
    adj["metadata"]["identifier_origins"] = {}
    out = rank_mdtm_candidates([adj, local], intent=intent, change_request="Req. 2 변경")
    assert out["ranking_results"]["ranked_node_ids"][0] == "local"


def test_inherited_lower_than_local():
    intent = parse_query_intent("Req. 2 변경")
    m_local = build_identifier_match_matrix(
        node_id="a",
        intent=intent,
        row_requirement_ids=["Req. 2"],
        row_design_ids=[],
        row_test_ids=[],
        identifier_origins={"requirement:Req. 2": "LOCAL_CELL"},
    )
    m_inh = build_identifier_match_matrix(
        node_id="b",
        intent=intent,
        row_requirement_ids=["Req. 2"],
        row_design_ids=[],
        row_test_ids=[],
        identifier_origins={"requirement:Req. 2": "MERGED_CELL_INHERITED"},
    )
    assert m_local.primary_identifier_match
    assert not m_inh.primary_identifier_match


def test_duplicate_exact_rows_preserved():
    intent = parse_query_intent("Req. 2 변경")
    cands = [
        _cand("dup1", "PATCH_CANDIDATE", reqs=["Req. 2"], overlap=0.2),
        _cand("dup2", "PATCH_CANDIDATE", reqs=["Req. 2"], overlap=0.1),
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 2 변경")
    ids = out["ranking_results"]["ranked_node_ids"]
    assert "dup1" in ids and "dup2" in ids
    assert out["duplicate_identifier_groups"]
    assert all(c.get("human_review_required") for c in cands)


def test_duplicate_exact_rows_review_if_unresolved():
    intent = parse_query_intent("Req. 2 변경")
    cands = [
        _cand("dup1", "PATCH_CANDIDATE", reqs=["Req. 2"]),
        _cand("dup2", "PATCH_CANDIDATE", reqs=["Req. 2"]),
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 2 변경")
    assert out["duplicate_identifier_groups"][0]["human_review_required"] is True


def test_deterministic_tie_break():
    intent = parse_query_intent("Req. 9 변경")
    cands = [
        _cand("z_row", "PATCH_CANDIDATE", reqs=["Req. 9"], overlap=0.0),
        _cand("a_row", "PATCH_CANDIDATE", reqs=["Req. 9"], overlap=0.0),
    ]
    out1 = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 9")
    out2 = rank_mdtm_candidates(list(reversed(cands)), intent=intent, change_request="Req. 9")
    assert out1["ranking_results"]["ranked_node_ids"] == out2["ranking_results"]["ranked_node_ids"]


def test_rank_tier_ordering():
    intent = parse_query_intent("Req. 2 변경")
    m = build_identifier_match_matrix(
        node_id="x",
        intent=intent,
        row_requirement_ids=["Req. 2"],
        row_design_ids=[],
        row_test_ids=[],
    )
    tier, reasons = assign_rank_tier(m, row_local_semantic=0.0)
    assert tier == 1
    assert "RANK_TIER_1" in reasons
    scored = score_candidate(matrix=m, tier=1, row_local_semantic=0.1)
    assert scored["final_score"] > 100


def test_neighbor_penalty_flag():
    intent = parse_query_intent("Req. 2 변경")
    adj = _cand("adj", "REVIEW_REQUIRED", overlap=0.4, row_text="something")
    adj["metadata"]["evidence_scopes"] = ["ADJACENT_ROW"]
    out = rank_mdtm_candidates([adj], intent=intent, change_request="Req. 2 변경")
    assert out["neighbor_context_analysis"] or "NEIGHBOR_PENALTY_APPLIED" in str(
        adj["metadata"].get("ranking_reason_codes")
    )


def test_primary_exact_ranked_before_non_exact_invariant():
    intent = parse_query_intent("Req. 2 변경")
    cands = [
        _cand("weak", "REVIEW_REQUIRED", overlap=0.99, row_text="변경 추적성"),
        _cand("exact", "PATCH_CANDIDATE", reqs=["Req. 2"], overlap=0.01),
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 2 변경")
    assert out["validation"]["primary_exact_ranked_before_non_exact"] is True
