# -*- coding: utf-8 -*-
"""Unit tests for domain-independent B3 + NEW_REQUIREMENT fallback.

Does not overwrite Scenario-001 freeze. Does not hard-code Scenario-001 answers.
"""

from __future__ import annotations

from document_ai.impact.impact_judgment import judge_block
from document_ai.impact.new_requirement_proposal import (
    build_new_requirement_proposal,
    should_emit_zero_impacted_fallback,
)
from document_ai.impact.semantic_hybrid_retrieve import ScoredHit
from document_ai.impact.semantic_index import RequirementBlock


def _block(req_id: str, title: str, body: str, doc: str = "MDSR") -> RequirementBlock:
    return RequirementBlock(
        req_id=req_id,
        title=title,
        body_text=body,
        document_type=doc,
        source_path="synthetic",
        source_locator="t",
        keywords=[],
    )


def _hit(block: RequirementBlock, *, rank: int, lex: float, sem: float) -> ScoredHit:
    return ScoredHit(
        candidate_id=block.req_id,
        document=block.document_type,
        title=block.title,
        source_path=block.source_path,
        source_locator=block.source_locator,
        lexical_score=lex,
        semantic_score=sem,
        hybrid_score=(lex + sem) / 2,
        rank=rank,
    )


def test_case_a_modify_existing_impacted():
    """Clear overlap of actor/action/object → IMPACTED / MODIFY_EXISTING."""
    cr = "서버는 사용자 비밀번호 변경 API를 제공하고 변경 이력을 저장해야 한다."
    block = _block(
        "Req. 50",
        "비밀번호 변경 API 제공",
        "서버는 인증된 사용자가 비밀번호를 변경할 수 있는 API를 제공해야 한다. 변경 결과는 저장된다.",
    )
    d = judge_block(cr, block, lexical_score=0.35, semantic_score=0.22, retrieval_rank=1)
    assert d.judgment == "IMPACTED"
    assert d.change_type in {"MODIFY_EXISTING", "EXTEND_EXISTING"}
    assert d.evidence_structured.get("matched_concepts")
    assert d.confidence > 0


def test_case_b_extend_existing():
    """Related responsibility + novel CR constraint → EXTEND or UNCERTAIN extension."""
    cr = (
        "의료진이 담당 환자의 최근 활동 상태를 조회할 수 있어야 하며, "
        "활동이 없는 환자를 별도 상태로 분류하는 규칙을 추가한다."
    )
    block = _block(
        "Req. 90",
        "개별 환자별 조회 기능",
        "의료진은 담당 환자를 선택하여 해당 환자의 치료 진행 현황과 활동 상태를 조회할 수 있어야 한다.",
    )
    d = judge_block(cr, block, lexical_score=0.22, semantic_score=0.14, retrieval_rank=2)
    assert d.judgment in {"IMPACTED", "UNCERTAIN"}
    assert d.change_type in {"EXTEND_EXISTING", "MODIFY_EXISTING", "NEW_REQUIREMENT_CANDIDATE", "UNCERTAIN"}
    assert "환자" in " ".join(d.evidence_structured.get("matched_concepts") or []) or d.theme_hits


def test_case_c_new_requirement_candidate_and_fallback():
    """Adjacent candidates but no safe IMPACTED → proposal generated."""
    cr = (
        "연속 3회 이상 예약 미방문 고객을 별도 등급으로 분류하고 "
        "상담원 화면에서 강조 표시하며 상태는 방문 기록을 기준으로 자동 갱신한다."
    )
    b1 = _block(
        "Req. 1",
        "고객 목록 조회",
        "상담원은 담당 고객 목록을 조회할 수 있어야 한다.",
    )
    b2 = _block(
        "Req. 2",
        "방문 기록 저장",
        "시스템은 고객 방문 기록을 저장하고 조회 API를 제공한다.",
    )
    d1 = judge_block(cr, b1, lexical_score=0.12, semantic_score=0.09, retrieval_rank=1)
    d2 = judge_block(cr, b2, lexical_score=0.11, semantic_score=0.08, retrieval_rank=2)
    # Simulate zero-IMPACTED with related evidence (not NOT_RELATED)
    for x in (d1, d2):
        x.judgment = "UNCERTAIN"
        x.change_type = "NEW_REQUIREMENT_CANDIDATE"
        x.evidence_structured = {
            "matched_concepts": ["고객", "방문"],
            "behavioral_overlap": {"object": ["기록"], "action": ["조회"]},
            "cr_spans": [],
            "candidate_spans": [],
        }
        x.scores = {**(x.scores or {}), "relevance": 0.08}
    decisions = [d1, d2]
    ranked = [_hit(b1, rank=1, lex=0.12, sem=0.09), _hit(b2, rank=2, lex=0.11, sem=0.08)]
    assert should_emit_zero_impacted_fallback(decisions, ranked)
    prop = build_new_requirement_proposal(cr, decisions, ranked)
    assert prop is not None
    assert prop.status == "NEW_REQUIREMENT_CANDIDATE"
    assert prop.proposed_title
    assert prop.related_existing_req_candidates
    assert prop.human_decision_required


def test_zero_impacted_fallback_does_not_emit_when_all_candidates_not_related():
    """IMPACTED=0 with nonempty Top-k that are all NOT_RELATED → no proposal."""
    cr = "완전히 무관한 변경 요청 텍스트이며 기존 요구와 겹치지 않는다."
    b1 = _block("Req. 9", "테마 색상", "화면 테마 색상만 변경한다.")
    b2 = _block("Req. 10", "폰트 크기", "기본 폰트 크기만 설정한다.")
    d1 = judge_block(cr, b1, lexical_score=0.02, semantic_score=0.01, retrieval_rank=1)
    d2 = judge_block(cr, b2, lexical_score=0.02, semantic_score=0.01, retrieval_rank=2)
    # Force the unsafe pre-fix shape: zero IMPACTED, all NOT_RELATED, ranked nonempty
    for x in (d1, d2):
        x.judgment = "NOT_IMPACTED"
        x.change_type = "NOT_RELATED"
        x.evidence_structured = {
            "matched_concepts": [],
            "behavioral_overlap": {},
            "cr_spans": [],
            "candidate_spans": [],
        }
        x.scores = {"relevance": 0.01, "lexical": 0.02, "semantic": 0.01}
    ranked = [_hit(b1, rank=1, lex=0.02, sem=0.01), _hit(b2, rank=2, lex=0.02, sem=0.01)]
    assert all(d.judgment != "IMPACTED" for d in (d1, d2))
    assert ranked
    assert should_emit_zero_impacted_fallback([d1, d2], ranked) is False
    assert build_new_requirement_proposal(cr, [d1, d2], ranked) is None


def test_case_d_false_friend_not_impacted():
    """Shared ambiguous token without shared actor/object → NOT_IMPACTED."""
    cr = "비활성 환자를 별도로 분류한다."
    block = _block(
        "Req. 12",
        "애플리케이션 내 제어 및 종료 메커니즘",
        "애플리케이션이 백그라운드 또는 비활성 상태로 전환되는 경우 세션을 저장해야 한다.",
    )
    d = judge_block(cr, block, lexical_score=0.08, semantic_score=0.07, retrieval_rank=11)
    assert d.judgment == "NOT_IMPACTED"
    assert d.change_type == "NOT_RELATED"


def test_case_e_uncertain_needs_review_signal():
    """Weak evidence → UNCERTAIN (not forced IMPACTED)."""
    cr = "데이터 보관 정책에 대한 일반적인 개선이 필요하다."
    block = _block(
        "Req. 70",
        "로그 파일 로테이션",
        "서버는 일 단위로 로그 파일을 로테이션해야 한다.",
    )
    d = judge_block(cr, block, lexical_score=0.05, semantic_score=0.04, retrieval_rank=9)
    assert d.judgment in {"UNCERTAIN", "NOT_IMPACTED"}
    assert d.judgment != "IMPACTED"


def test_lockout_still_impacted_without_id_hardcode():
    """Regression: lockout-family CR can still IMPACT a lock-policy block via evidence."""
    cr = "연속 로그인 실패 시 계정을 잠그고 자동 해제한다."
    block = _block(
        "Req. 105",
        "API 요청 과다 방지 및 IP 차단",
        "연속된 인증 실패 횟수를 추적하고 임계치를 초과한 계정에 대해 일정 시간 로그인 시도를 제한한다. 계정 잠금 이벤트는 기록한다.",
    )
    d = judge_block(cr, block, lexical_score=0.4, semantic_score=0.25, retrieval_rank=1)
    assert d.judgment == "IMPACTED"
    assert d.change_type in {"MODIFY_EXISTING", "EXTEND_EXISTING"}


def test_id_alone_insufficient():
    cr = "연속 로그인 실패 시 계정 잠금"
    block = _block(
        "Req. 105",
        "화면 테마 색상",
        "화면 테마 색상만 변경한다.",
    )
    d = judge_block(cr, block, lexical_score=0.05, semantic_score=0.01)
    assert d.judgment != "IMPACTED"


def test_structured_evidence_fields_present():
    cr = "서버는 사용자 세션을 관리하고 만료 시 재로그인을 안내해야 한다."
    block = _block(
        "Req. 8",
        "세션 만료 처리",
        "서버는 사용자 세션 만료 시 재로그인을 안내해야 한다.",
    )
    d = judge_block(cr, block, lexical_score=0.3, semantic_score=0.2)
    payload = d.to_dict()
    assert payload["judgment"] in {"IMPACTED", "UNCERTAIN", "NOT_IMPACTED"}
    assert "change_type" in payload
    assert "evidence" in payload
    assert "matched_concepts" in payload["evidence"]
    assert "confidence" in payload
