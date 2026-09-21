# -*- coding: utf-8 -*-
"""EC-SW semantic review evidence tests."""

from __future__ import annotations

from pathlib import Path

from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.domain_packs.ec_sw.semantic_evidence import (
    collect_semantic_review_evidence,
    semantic_to_review_candidates,
)

REPO = Path(__file__).resolve().parents[1]
MDTM = next((REPO / "data" / "examples" / "ec_sw").glob("matrix_mdtm*.docx"))


def _nodes():
    return list(index_mdtm_document(source_path=MDTM, document_id="MDTM")["nodes"])


def test_semantic_only_specific_rows_review():
    ev = collect_semantic_review_evidence(
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        nodes=_nodes(),
    )
    strong = [e for e in ev if e.evidence_status == "STRONG_REVIEW"]
    assert strong
    assert all(e.supports_review for e in strong)
    assert all(not e.supports_patch for e in strong)


def test_semantic_only_no_patch_candidates():
    cands = semantic_to_review_candidates(
        collect_semantic_review_evidence(
            change_request="사용자 인증 및 접근통제 보안 요구 변경",
            nodes=_nodes(),
        )
    )
    assert cands
    assert all(c["status"] == "REVIEW_REQUIRED" for c in cands)
    assert all(c.get("metadata", {}).get("supports_patch") is False for c in cands)


def test_weak_or_no_match_marketing():
    ev = collect_semantic_review_evidence(
        change_request="마케팅 슬로건 XYZABCQUUX 변경",
        nodes=_nodes(),
    )
    assert not any(e.evidence_status == "STRONG_REVIEW" for e in ev)


def test_multiple_matching_rows_ambiguous():
    ev = collect_semantic_review_evidence(
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        nodes=_nodes(),
    )
    strong = [e for e in ev if e.evidence_status == "STRONG_REVIEW"]
    if len(strong) > 1:
        assert any("SEMANTIC_AMBIGUOUS" in e.reason_codes for e in strong)


def test_exact_req_skips_semantic_pack():
    ev = collect_semantic_review_evidence(
        change_request="Req. 2 행 추적성 갱신",
        nodes=_nodes(),
    )
    assert ev == []


def test_malformed_plus_domain_can_review():
    # malformed alone not enough; with domain+intent still reviews via concepts
    ev = collect_semantic_review_evidence(
        change_request="REQ2 및 사용자 인증 접근통제 보안 요구 검토",
        nodes=_nodes(),
    )
    # REQ2 is malformed (not valid id) so semantic pack runs
    assert any(e.evidence_status == "STRONG_REVIEW" for e in ev)


def test_malformed_only_unrelated_semantic():
    ev = collect_semantic_review_evidence(
        change_request="REQ2 형식 오류 식별자",
        nodes=_nodes(),
    )
    assert not any(e.supports_review for e in ev)


def test_deterministic_ranking():
    a = collect_semantic_review_evidence(
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        nodes=_nodes(),
    )
    b = collect_semantic_review_evidence(
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        nodes=_nodes(),
    )
    assert [e.node_id for e in a] == [e.node_id for e in b]
