# -*- coding: utf-8 -*-
"""Tests for hybrid retrieval + B3 impact judgment."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_ai.impact.impact_judgment import judge_block, judge_candidates
from document_ai.impact.semantic_hybrid_retrieve import rank_by_method, score_all_methods
from document_ai.impact.semantic_index import RequirementBlock, load_index_jsonl

TRIAL = Path("data/trials/trial-002-lockout-multireq")
IDX = TRIAL / "retrieval" / "index_all.jsonl"
CR = TRIAL / "input" / "change_request.txt"


@pytest.fixture(scope="module")
def blocks():
    path = TRIAL / "retrieval" / "lexical_baseline" / "index_all.jsonl"
    if not path.exists():
        path = IDX
    if not path.exists():
        pytest.skip("index missing")
    return load_index_jsonl(path)


@pytest.fixture(scope="module")
def cr_text():
    return CR.read_text(encoding="utf-8")


def test_hybrid_scores_have_three_channels(blocks, cr_text):
    scored = score_all_methods(cr_text, blocks)
    assert scored
    hit = scored[0]
    assert hasattr(hit, "lexical_score")
    assert hasattr(hit, "semantic_score")
    assert hasattr(hit, "hybrid_score")


def test_methods_return_topk(blocks, cr_text):
    scored = score_all_methods(cr_text, blocks)
    for method in ("lexical", "semantic", "hybrid"):
        ranked = rank_by_method(scored, method, top_k=15)  # type: ignore[arg-type]
        assert 1 <= len(ranked) <= 15
        assert ranked[0].rank == 1
        assert ranked[0].method == method


def test_document_aware_not_collapsed(blocks, cr_text):
    scored = score_all_methods(cr_text, blocks)
    ranked = rank_by_method(scored, "hybrid", top_k=15)
    # Same ID may appear twice with different documents
    keys = [(h.candidate_id, h.document) for h in ranked]
    assert len(keys) == len(set(keys))


def test_b3_does_not_impact_by_id_alone():
    cr = "연속 로그인 실패 시 계정 잠금 및 관리자 알림"
    # Block with matching ID but unrelated body
    block = RequirementBlock(
        req_id="Req. 105",
        title=" unrelated UI color theme",
        body_text="화면 테마 색상만 변경한다.",
        document_type="MDSR",
        source_path="x",
        source_locator="t",
        keywords=[],
    )
    d = judge_block(cr, block, lexical_score=0.05, semantic_score=0.01)
    assert d.judgment != "IMPACTED"


def test_b3_lock_block_impacted():
    cr = CR.read_text(encoding="utf-8")
    block = RequirementBlock(
        req_id="Req. 105",
        title="API 요청 과다 방지",
        body_text="연속된 인증 실패 횟수를 추적하고 임계치를 초과한 계정에 대해 일정 시간 로그인 시도를 제한. 계정 잠금 이벤트는 감사 기록.",
        document_type="MDDR",
        source_path="x",
        source_locator="t",
        keywords=["잠금", "로그인"],
    )
    d = judge_block(cr, block, lexical_score=0.4, semantic_score=0.2)
    assert d.judgment == "IMPACTED"
    assert d.reason
    assert d.evidence is not None


def test_b3_generic_audit_not_impacted():
    cr = CR.read_text(encoding="utf-8")
    block = RequirementBlock(
        req_id="Req. 101",
        title="권한에 따른 API 접근 통제",
        body_text="권한 검증 실패 시 오류. 로그인 성공 실패 등 인증 이벤트는 감사 기록으로 남긴다.",
        document_type="MDSR",
        source_path="x",
        source_locator="t",
        keywords=["감사", "로그인"],
    )
    d = judge_block(cr, block, lexical_score=0.25, semantic_score=0.1)
    assert d.judgment in {"NOT_IMPACTED", "UNCERTAIN"}


def test_b3_audit_primary_impacted():
    cr = CR.read_text(encoding="utf-8")
    block = RequirementBlock(
        req_id="Req. 103",
        title="감사 기록 생성 및 보관",
        body_text="로그인 성공 및 실패 이력을 감사 기록으로 저장해야 한다.",
        document_type="MDSR",
        source_path="x",
        source_locator="t",
        keywords=["감사", "로그인"],
    )
    d = judge_block(cr, block, lexical_score=0.32, semantic_score=0.14)
    assert d.judgment in {"IMPACTED", "UNCERTAIN"}
    assert d.evidence_structured.get("matched_concepts") or d.reason
