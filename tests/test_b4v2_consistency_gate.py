# -*- coding: utf-8 -*-
"""B4v2 domain-independent consistency gate — synthetic cases A–G."""

from __future__ import annotations

from document_ai.impact.consistency_gate import check_consistency
from document_ai.impact.semantic_index import RequirementBlock


def _block(req_id: str, title: str, description: str, purpose: str, criteria: str) -> RequirementBlock:
    body = f"{title}\n설명\n{description}\n목적\n{purpose}\n기준\n{criteria}"
    return RequirementBlock(
        req_id=req_id,
        title=title,
        body_text=body,
        document_type="MDSR",
        source_path="synthetic",
        source_locator="t",
        keywords=[],
    )


def _b3(**kwargs):
    base = {
        "judgment": "IMPACTED",
        "change_type": "EXTEND_EXISTING",
        "reason": "synthetic prior",
        "confidence": 0.5,
        "evidence": {
            "cr_spans": kwargs.pop("cr_spans", []),
            "candidate_spans": kwargs.pop("candidate_spans", []),
            "matched_concepts": kwargs.pop("matched_concepts", []),
            "behavioral_overlap": kwargs.pop("behavioral_overlap", {}),
        },
    }
    base.update(kwargs)
    return base


def test_case_a_clear_in_scope_modification():
    """Case A: clear modify within existing responsibility → CONSISTENT."""
    cr = "재고 수량이 0이 되면 해당 품목을 품절 상태로 표시한다."
    block = _block(
        "Req. SynA",
        "재고 현황 조회 및 상태 표시",
        "시스템은 품목별 재고 수량과 상태를 조회하고 화면에 표시해야 한다.",
        "운영자가 재고 상태를 파악할 수 있도록 하기 위함이다.",
        "재고 수량과 상태가 최신 데이터로 표시되어야 한다.",
    )
    d = check_consistency(
        cr,
        block,
        b3_decision=_b3(
            matched_concepts=["재고", "상태", "표시"],
            behavioral_overlap={"object": ["재고", "상태"], "action": ["표시", "조회"]},
            cr_spans=[cr],
            candidate_spans=[block.title],
        ),
    )
    assert d.status == "CONSISTENT"
    assert d.allow_auto_patch is True
    assert "responsibility" in d.evidence["compatible_facets"] or "object" in d.evidence["compatible_facets"]
    assert d.evidence["cr_spans"] or d.evidence["candidate_spans"]
    assert d.confidence < 1.0


def test_case_b_natural_scope_extension():
    """Case B: natural extension → CONSISTENT or NEEDS_REVIEW (not CONFLICT)."""
    cr = "예약 가능 좌석에 대해 대기열 등록 기능을 추가한다."
    block = _block(
        "Req. SynB",
        "예약 가능 여부 조회",
        "시스템은 좌석별 예약 가능 여부를 조회할 수 있어야 한다.",
        "고객이 예약 가능 상태를 확인할 수 있도록 하기 위함이다.",
        "좌석 상태가 최신으로 조회되어야 한다.",
    )
    d = check_consistency(
        cr,
        block,
        b3_decision=_b3(matched_concepts=["예약", "좌석"], change_type="EXTEND_EXISTING"),
    )
    assert d.status in {"CONSISTENT", "NEEDS_REVIEW"}
    assert d.status != "CONFLICT"


def test_case_c_direct_meaning_conflict():
    """Case C: enforce/cancel vs inform-only → CONFLICT."""
    cr = "결제가 실패하면 주문을 자동으로 취소하고 재시도를 제한한다."
    block = _block(
        "Req. SynC",
        "결제 실패 시 사용자 오류 안내",
        "결제 실패 발생 시 사용자에게 오류 메시지를 안내해야 한다.",
        "사용자가 실패 원인을 이해할 수 있도록 명확히 안내하기 위함이다.",
        "오류 메시지에 민감정보가 포함되지 않아야 한다.",
    )
    d = check_consistency(cr, block, b3_decision=_b3(matched_concepts=["결제", "실패"]))
    assert d.status == "CONFLICT"
    assert d.allow_auto_patch is False
    assert "responsibility" in d.evidence["conflicting_facets"] or "action" in d.evidence["conflicting_facets"]


def test_case_d_thematic_false_positive():
    """Case D: B3 thematic neighbor → CONFLICT or NEEDS_REVIEW with responsibility mismatch."""
    cr = "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 목록에서 식별 가능하게 표시한다."
    block = _block(
        "Req. SynD",
        "인증 코드의 안전한 저장 및 관리",
        "서버는 등록 시 일회성 인증 코드를 생성하고 저장하며 사용 후 재사용을 금지해야 한다.",
        "인가된 등록만 진행되도록 코드를 검증하기 위함이다.",
        "코드 상태는 미사용/사용완료로 관리되어야 한다.",
    )
    d = check_consistency(
        cr,
        block,
        b3_decision=_b3(
            matched_concepts=["상태", "관리"],
            change_type="EXTEND_EXISTING",
            behavioral_overlap={"object": ["상태"]},
        ),
    )
    assert d.status in {"CONFLICT", "NEEDS_REVIEW"}
    assert d.allow_auto_patch is False
    # Must not be "theme keyword miss"; must cite facet / responsibility evidence
    blob = (d.reason + " " + str(d.evidence)).lower()
    assert "theme keyword" not in blob
    assert d.evidence["conflicting_facets"] or d.evidence["missing_information"] or "mismatch" in d.reason.lower() or "conflict" in d.reason.lower() or "insufficient" in d.reason.lower()


def test_case_e_insufficient_information():
    """Case E: vague CR → NEEDS_REVIEW."""
    cr = "관련 기능을 개선한다."
    block = _block(
        "Req. SynE",
        "보고서 생성",
        "시스템은 월간 보고서를 생성할 수 있어야 한다.",
        "운영 현황을 공유하기 위함이다.",
        "보고서가 생성되어야 한다.",
    )
    d = check_consistency(cr, block, b3_decision=_b3(matched_concepts=[], confidence=0.9))
    assert d.status == "NEEDS_REVIEW"
    assert d.allow_auto_patch is False
    # High B3 confidence alone must not force CONSISTENT
    assert d.status != "CONSISTENT"


def test_case_f_near_identical_responsibility():
    """Case F: nearly identical responsibility → CONSISTENT."""
    cr = "시스템은 월간 운영 보고서를 생성하고 관리자에게 제공한다."
    block = _block(
        "Req. SynF",
        "월간 운영 보고서 생성",
        "시스템은 월간 운영 보고서를 생성하여 관리자에게 제공해야 한다.",
        "운영 현황을 관리자가 파악하도록 하기 위함이다.",
        "월간 단위로 보고서가 생성되어야 한다.",
    )
    d = check_consistency(
        cr,
        block,
        b3_decision=_b3(
            matched_concepts=["월간", "보고서", "관리자", "생성"],
            change_type="MODIFY_EXISTING",
            behavioral_overlap={"actor": ["관리자"], "action": ["생성"]},
        ),
    )
    assert d.status == "CONSISTENT"
    assert d.allow_auto_patch is True


def test_case_g_non_security_domain_inventory():
    """Case G: inventory domain without auth/lockout keywords → CONSISTENT possible."""
    cr = "창고 재고가 안전 재고 미만이면 보충 요청을 생성한다."
    block = _block(
        "Req. SynG",
        "창고 재고 모니터링 및 보충 관리",
        "시스템은 창고 재고 수준을 모니터링하고 보충이 필요할 때 요청을 생성할 수 있어야 한다.",
        "재고 부족을 방지하기 위함이다.",
        "재고 수준과 보충 요청 이력이 기록되어야 한다.",
    )
    d = check_consistency(
        cr,
        block,
        b3_decision=_b3(matched_concepts=["재고", "보충", "생성"], behavioral_overlap={"object": ["재고"]}),
    )
    assert d.status == "CONSISTENT"
    assert "계정 잠금" not in d.reason
    assert d.evidence["compatible_facets"]


def test_confidence_alone_never_forces_consistent():
    cr = "상태를 바꾼다."
    block = _block("Req. SynX", "기타", "기타 기능", "기타", "기타")
    d = check_consistency(
        cr,
        block,
        b3_decision=_b3(confidence=0.99, matched_concepts=["상태"]),
    )
    assert d.status != "CONSISTENT" or d.evidence["compatible_facets"]


def test_b3_evidence_forwarded_into_decision():
    cr = "알림 구독자가 이벤트 발생 시 알림을 수신한다."
    block = _block(
        "Req. SynN",
        "이벤트 알림 전송",
        "시스템은 구독자에게 이벤트 알림을 전송해야 한다.",
        "중요 이벤트 인지",
        "알림이 전송되어야 한다.",
    )
    prior = _b3(
        cr_spans=["이벤트 발생 시 알림을 수신한다"],
        candidate_spans=["구독자에게 이벤트 알림을 전송"],
        matched_concepts=["이벤트", "알림"],
        reason="b3 prior reason",
        change_type="MODIFY_EXISTING",
        confidence=0.44,
    )
    d = check_consistency(cr, block, b3_decision=prior)
    assert d.b3_prior.get("change_type") == "MODIFY_EXISTING"
    assert d.b3_prior.get("matched_concepts") == ["이벤트", "알림"]
    assert "이벤트 발생 시 알림을 수신한다" in d.evidence["cr_spans"]
    assert d.to_dict()["consistency"] == d.status
    assert "candidate" in d.to_dict()
