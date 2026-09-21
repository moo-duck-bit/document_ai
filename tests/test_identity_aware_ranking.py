# -*- coding: utf-8 -*-
from document_ai.domain_packs.ec_sw.node_ranking import (
    assign_rank_tier,
    build_identifier_match_matrix,
    rank_mdtm_candidates,
    score_candidate,
)
from document_ai.domain_packs.ec_sw.query_intent import QueryIntent
from document_ai.document_set.stable_node_identity import (
    build_stable_node_id_base,
    canonical_identifier_key,
    IDENTITY_VERSION_V2,
)


def _intent_req11():
    return QueryIntent(
        raw_change_request="Req. 11 수정",
        primary_identifier_type="REQUIREMENT",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
    )


def _base_for(reqs, dens=None, tests=None):
    key = canonical_identifier_key(
        requirement_ids=reqs,
        design_ids=dens or [],
        test_ids=tests or [],
        version=IDENTITY_VERSION_V2,
    )
    return build_stable_node_id_base(
        domain_pack_id="ec_sw_v1",
        document_role="traceability",
        node_type="TABLE_ROW",
        logical_key=key,
        structural_role="traceability_row",
    )


def test_exact_stable_base_top1():
    intent = _intent_req11()
    base = _base_for(["Req. 11"], ["5.1.2"], ["TC-11"])
    cands = [
        {
            "node_id": "semantic",
            "status": "REVIEW_REQUIRED",
            "metadata": {
                "row_requirement_ids": [],
                "row_design_ids": [],
                "row_test_ids": [],
                "row_text": "일반 설명 overlap 수정",
                "overlap": 0.5,
            },
        },
        {
            "node_id": "exact",
            "status": "PATCH_CANDIDATE",
            "matched_requirement_ids": ["Req. 11"],
            "metadata": {
                "row_requirement_ids": ["Req. 11"],
                "row_design_ids": ["5.1.2"],
                "row_test_ids": ["TC-11"],
                "stable_node_id_base": base,
                "row_text": "Req. 11",
                "overlap": 0.1,
            },
        },
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 11 수정")
    ranked = out["ranking_candidates"]
    assert ranked[0]["node_id"] == "exact"
    assert int(ranked[0]["rank_tier"]) <= 1


def test_primary_beats_context():
    intent = _intent_req11()
    matrix_exact = build_identifier_match_matrix(
        node_id="e",
        intent=intent,
        row_requirement_ids=["Req. 11"],
        row_design_ids=[],
        row_test_ids=[],
    )
    matrix_ctx = build_identifier_match_matrix(
        node_id="c",
        intent=intent,
        row_requirement_ids=[],
        row_design_ids=[],
        row_test_ids=[],
    )
    t_exact, _ = assign_rank_tier(matrix_exact, row_local_semantic=0.1, stable_base_match=True)
    t_ctx, _ = assign_rank_tier(matrix_ctx, row_local_semantic=0.9, stable_base_match=False)
    assert t_exact < t_ctx


def test_exact_instance_beats_base_only():
    matrix = build_identifier_match_matrix(
        node_id="x",
        intent=_intent_req11(),
        row_requirement_ids=["Req. 11"],
        row_design_ids=[],
        row_test_ids=[],
    )
    t0, _ = assign_rank_tier(
        matrix, row_local_semantic=0.1, stable_base_match=True, instance_match=True
    )
    t1, _ = assign_rank_tier(
        matrix, row_local_semantic=0.1, stable_base_match=True, instance_match=False
    )
    assert t0 < t1
    s0 = score_candidate(
        matrix=matrix, tier=t0, row_local_semantic=0.1, stable_base_match=True, instance_match=True
    )
    s1 = score_candidate(
        matrix=matrix, tier=t1, row_local_semantic=0.1, stable_base_match=True, instance_match=False
    )
    assert s0["final_score"] > s1["final_score"]


def test_duplicate_ambiguity_review():
    intent = _intent_req11()
    base = _base_for(["Req. 11"])
    cands = [
        {
            "node_id": "d1",
            "status": "PATCH_CANDIDATE",
            "matched_requirement_ids": ["Req. 11"],
            "metadata": {
                "row_requirement_ids": ["Req. 11"],
                "row_design_ids": [],
                "row_test_ids": [],
                "stable_node_id_base": base,
                "identity_status": "DUPLICATE_GROUP",
            },
        },
        {
            "node_id": "d2",
            "status": "PATCH_CANDIDATE",
            "matched_requirement_ids": ["Req. 11"],
            "metadata": {
                "row_requirement_ids": ["Req. 11"],
                "row_design_ids": [],
                "row_test_ids": [],
                "stable_node_id_base": base,
                "identity_status": "DUPLICATE_GROUP",
            },
        },
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 11")
    assert out["duplicate_identifier_groups"]
    assert all(c.get("human_review_required") for c in cands)


def test_semantic_only_high_tier_number():
    matrix = build_identifier_match_matrix(
        node_id="s",
        intent=_intent_req11(),
        row_requirement_ids=[],
        row_design_ids=[],
        row_test_ids=[],
    )
    tier, reasons = assign_rank_tier(matrix, row_local_semantic=0.5)
    assert tier >= 5
    assert "ROW_LOCAL_SEMANTIC_MATCH" in reasons or "CONTEXT_ONLY_MATCH" in reasons or tier == 5


def test_deterministic_tie_break():
    intent = _intent_req11()
    base = _base_for(["Req. 11"])
    cands = [
        {
            "node_id": "b_node",
            "status": "PATCH_CANDIDATE",
            "matched_requirement_ids": ["Req. 11"],
            "metadata": {
                "row_requirement_ids": ["Req. 11"],
                "row_design_ids": [],
                "row_test_ids": [],
                "stable_node_id_base": base,
                "table_index": 0,
                "row_index": 5,
            },
        },
        {
            "node_id": "a_node",
            "status": "PATCH_CANDIDATE",
            "matched_requirement_ids": ["Req. 11"],
            "metadata": {
                "row_requirement_ids": ["Req. 11"],
                "row_design_ids": [],
                "row_test_ids": [],
                "stable_node_id_base": base,
                "table_index": 0,
                "row_index": 3,
            },
        },
    ]
    out1 = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 11")
    out2 = rank_mdtm_candidates(list(reversed(cands)), intent=intent, change_request="Req. 11")
    assert [r["node_id"] for r in out1["ranking_candidates"]] == [
        r["node_id"] for r in out2["ranking_candidates"]
    ]


def test_identity_rank_tier_consistent_validation():
    intent = _intent_req11()
    base = _base_for(["Req. 11"])
    cands = [
        {
            "node_id": "ctx",
            "status": "REVIEW_REQUIRED",
            "metadata": {
                "row_requirement_ids": [],
                "row_design_ids": [],
                "row_test_ids": [],
                "row_text": "수정 내용 많은 semantic",
                "overlap": 0.8,
            },
        },
        {
            "node_id": "pri",
            "status": "PATCH_CANDIDATE",
            "matched_requirement_ids": ["Req. 11"],
            "metadata": {
                "row_requirement_ids": ["Req. 11"],
                "row_design_ids": [],
                "row_test_ids": [],
                "stable_node_id_base": base,
            },
        },
    ]
    out = rank_mdtm_candidates(cands, intent=intent, change_request="Req. 11 수정")
    assert out["validation"]["primary_exact_ranked_before_non_exact"] is True
    assert out["validation"]["identity_rank_tier_consistent"] is True
