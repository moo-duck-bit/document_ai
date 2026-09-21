# -*- coding: utf-8 -*-
"""B5v2 domain-independent design propagation — synthetic cases A–G."""

from __future__ import annotations

from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.propagation import (
    assess_design_propagation,
    build_propagation_plan,
    proposed_mdsr_description,
)
from document_ai.impact.semantic_index import RequirementBlock


def _block(req_id: str, title: str, body: str, doc: str = "MDSR") -> RequirementBlock:
    return RequirementBlock(
        req_id=req_id,
        title=title,
        body_text=f"{title}\n{body}",
        document_type=doc,
        source_path="synthetic",
        source_locator="t",
        keywords=[],
    )


def _consistent(req_id: str, **kwargs) -> ConsistencyDecision:
    return ConsistencyDecision(
        req_id=req_id,
        document="MDSR",
        status="CONSISTENT",
        reason=kwargs.get("reason", "synthetic consistent"),
        allow_auto_patch=True,
        fields={"description": kwargs.get("description", "기존 설명")},
        evidence={
            "compatible_facets": kwargs.get("compatible_facets", ["responsibility", "object"]),
            "conflicting_facets": [],
            "missing_information": [],
            "cr_spans": [],
            "candidate_spans": [],
        },
        b3_prior=kwargs.get("b3_prior", {}),
        confidence=kwargs.get("confidence", 0.5),
    )


def test_case_a_clear_responsibility_match_patch_existing():
    cr = "창고 재고가 안전 재고 미만이면 보충 요청을 생성한다."
    mdsr = _block(
        "Req. SynA",
        "창고 재고 모니터링 및 보충 관리",
        "시스템은 창고 재고 수준을 모니터링하고 보충 요청을 생성해야 한다.",
    )
    mddr = _block(
        "Req. SynA",
        "창고 재고 모니터링 및 보충 관리",
        "재고 서비스는 창고 재고를 조회하고 안전 재고 미만일 때 보충 요청을 생성하도록 구현한다.",
        "MDDR",
    )
    prop, ev, conf, reason = assess_design_propagation(
        cr, mdsr, mddr, decision=_consistent("Req. SynA"), b3_prior={"matched_concepts": ["재고", "보충"]}
    )
    assert prop == "PATCH_EXISTING"
    assert "object" in ev.matched_facets or ev.matched_responsibilities
    assert conf < 1.0
    assert "감사" not in reason


def test_case_b_extend_existing():
    cr = "예약 가능 좌석에 대기열 등록을 추가하고 대기 순번을 표시한다."
    mdsr = _block("Req. SynB", "예약 가능 여부 조회", "좌석별 예약 가능 여부를 조회한다.")
    mddr = _block(
        "Req. SynB",
        "예약 가능 여부 조회",
        "예약 서비스는 좌석 상태를 조회하여 예약 가능 여부를 반환한다.",
        "MDDR",
    )
    prop, ev, _c, _r = assess_design_propagation(
        cr, mdsr, mddr, decision=_consistent("Req. SynB"), b3_prior={"matched_concepts": ["예약", "좌석"]}
    )
    assert prop in {"EXTEND_EXISTING", "PATCH_EXISTING"}
    assert prop != "SKIP"


def test_case_c_theme_similar_responsibility_diff_skip():
    """Auth-code design must not receive inactive-activity CR (generalized FP)."""
    cr = "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 목록에서 식별 가능하게 표시한다."
    mdsr = _block(
        "Req. SynC",
        "인증 코드의 안전한 저장 및 관리",
        "일회성 인증 코드를 생성·저장하고 사용 후 재사용을 금지한다. 코드 조회 이력은 감사 기록으로 남긴다.",
    )
    mddr = _block(
        "Req. SynC",
        "인증 코드의 안전한 저장 및 관리",
        "patient_code를 생성해 회원가입 검증에 쓰고 사용 상태를 관리한다. 조회 이력은 감사 기록으로 남긴다.",
        "MDDR",
    )
    # Even if B4 wrongly CONSISTENT, B5 must SKIP false design propagation
    prop, ev, _c, reason = assess_design_propagation(
        cr,
        mdsr,
        mddr,
        decision=_consistent("Req. SynC", compatible_facets=["action", "object"]),
        b3_prior={"matched_concepts": ["상태", "관리"], "change_type": "EXTEND_EXISTING"},
    )
    assert prop == "SKIP"
    assert "responsibility_mismatch" in ev.conflicts or "boilerplate" in str(ev.conflicts)
    assert "theme pair" not in reason.lower()


def test_case_d_missing_design_new_candidate():
    cr = "월간 운영 보고서를 생성하여 관리자에게 제공한다."
    mdsr = _block("Req. SynD", "월간 운영 보고서 생성", "월간 운영 보고서를 생성한다.")
    prop, ev, _c, reason = assess_design_propagation(
        cr, mdsr, None, decision=_consistent("Req. SynD")
    )
    assert prop == "NEW_DESIGN_CANDIDATE"
    assert "design_block" in ev.missing_information
    assert "invent" in reason.lower() or "NEW_DESIGN" in reason


def test_case_e_needs_review_ambiguous():
    cr = "관련 상태를 일부 개선한다."
    mdsr = _block("Req. SynE", "기타 기능", "기타 기능을 제공한다.")
    mddr = _block("Req. SynE", "기타 기능", "기타 모듈을 구현한다.", "MDDR")
    prop, _ev, _c, _r = assess_design_propagation(
        cr, mdsr, mddr, decision=_consistent("Req. SynE", confidence=0.99)
    )
    assert prop in {"NEEDS_REVIEW", "NEW_DESIGN_CANDIDATE", "SKIP"}
    assert prop != "PATCH_EXISTING"


def test_case_f_traceability_with_behavioral_mismatch():
    cr = "결제가 실패하면 주문을 자동 취소하고 재시도를 제한한다."
    mdsr = _block(
        "Req. SynF",
        "결제 실패 시 사용자 오류 안내",
        "결제 실패 시 사용자에게 오류 메시지를 안내한다.",
    )
    mddr = _block(
        "Req. SynF",
        "결제 실패 시 사용자 오류 안내",
        "클라이언트는 결제 실패 오류 메시지를 화면에 표시한다.",
        "MDDR",
    )
    # B4 CONFLICT should SKIP
    conflict = ConsistencyDecision(
        req_id="Req. SynF",
        document="MDSR",
        status="CONFLICT",
        reason="inform vs enforce",
        allow_auto_patch=False,
        fields={},
        evidence={"compatible_facets": [], "conflicting_facets": ["responsibility"]},
    )
    prop, ev, _c, _r = assess_design_propagation(cr, mdsr, mddr, decision=conflict)
    assert prop == "SKIP"
    assert "b4_conflict" in ev.conflicts


def test_case_g_non_security_notification_domain():
    cr = "이벤트 발생 시 구독자에게 알림을 전송한다."
    mdsr = _block("Req. SynG", "이벤트 알림 전송", "시스템은 구독자에게 이벤트 알림을 전송해야 한다.")
    mddr = _block(
        "Req. SynG",
        "이벤트 알림 전송",
        "알림 서비스는 이벤트 구독자에게 알림 메시지를 전송하도록 구현한다.",
        "MDDR",
    )
    prop, ev, _c, reason = assess_design_propagation(
        cr, mdsr, mddr, decision=_consistent("Req. SynG"), b3_prior={"matched_concepts": ["이벤트", "알림"]}
    )
    assert prop in {"PATCH_EXISTING", "EXTEND_EXISTING"}
    assert "로그인" not in reason and "잠금" not in reason
    assert ev.matched_facets or ev.matched_responsibilities


def test_build_plan_emits_schema_and_mdsr_gate_flag():
    cr = "재고 수량이 0이면 품절 상태로 표시한다."
    blocks = [
        _block("Req. SynH", "재고 상태 표시", "재고 수량과 품절 상태를 표시한다."),
        _block(
            "Req. SynH",
            "재고 상태 표시",
            "UI는 재고 수량과 품절 상태를 화면에 표시한다.",
            "MDDR",
        ),
    ]
    cons = [_consistent("Req. SynH", description="재고 상태를 표시한다.")]
    traces = build_propagation_plan(cr, cons, blocks)
    assert len(traces) == 1
    t = traces[0]
    d = t.to_dict()
    assert d["propagation_decision"] in {"PATCH_EXISTING", "EXTEND_EXISTING"}
    assert "structured_evidence" in d or t.structured_evidence
    assert t.allow_mdsr_patch is True
    assert proposed_mdsr_description(cons[0], cr)


def test_legacy_theme_helper_isolated_not_required_for_patch():
    from document_ai.impact.propagation import legacy_theme_design_aligns

    mdsr = _block("Req. X", "코드 관리", "감사 기록으로 남긴다.")
    mddr = _block("Req. X", "코드 관리", "감사 기록으로 남긴다.", "MDDR")
    legacy_ok, _ = legacy_theme_design_aligns(mdsr, mddr)
    assert legacy_ok is True  # would have falsely aligned on 감사
    cr = "활동 기록이 없으면 별도 표시한다."
    prop, _ev, _c, _r = assess_design_propagation(
        cr, mdsr, mddr, decision=_consistent("Req. X")
    )
    assert prop == "SKIP"  # B5v2 must not follow legacy 감사 pair
