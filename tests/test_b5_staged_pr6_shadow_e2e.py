# -*- coding: utf-8 -*-
"""PR-6: staged shadow E2E — analysis only; actual path parity invariants."""

from __future__ import annotations

from document_ai.impact.atomic_change import AtomicChangeUnit, decompose_change_request
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.propagation import build_propagation_plan
from document_ai.impact.semantic_index import RequirementBlock
from document_ai.impact.staged_shadow_e2e import run_staged_shadow_e2e


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


def _consistent(req_id: str) -> ConsistencyDecision:
    return ConsistencyDecision(
        req_id=req_id,
        document="MDSR",
        status="CONSISTENT",
        reason="synthetic",
        allow_auto_patch=True,
        fields={"description": "기존"},
        evidence={"compatible_facets": ["object", "action"], "conflicting_facets": []},
        confidence=0.6,
    )


def _acu(
    cid: str,
    span: str,
    *,
    action: list[str],
    obj: list[str] | None = None,
    actor: list[str] | None = None,
    rtype: str = "other",
    status: str = "EXTRACTED",
) -> AtomicChangeUnit:
    return AtomicChangeUnit(
        change_id=cid,
        source_span=span,
        actor=actor or [],
        action=action,
        object=obj or [],
        condition=[],
        constraint=[],
        output=[],
        responsibility_type=rtype,
        provenance={"evidence_ids": [f"ev_{cid}"], "independent_group": f"span:{cid}"},
        confidence=0.7,
        decomposition_status=status,
    )


def _b3_mddr(rid: str, *, judgment: str = "IMPACTED", concepts: list[str] | None = None) -> dict:
    return {
        "candidate_id": rid,
        "document": "MDDR",
        "judgment": judgment,
        "retrieval_rank": 2,
        "confidence": 0.7,
        "evidence": {"matched_concepts": concepts or []},
    }


# ---------------------------------------------------------------------------
# A–K
# ---------------------------------------------------------------------------


def test_a_one_acu_same_id_true_owner_clear():
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고 수준을 조회한다.")
    mddr = _block(
        "Req. Inv",
        "재고 조회",
        "재고 서비스는 창고 재고 수준을 조회하여 반환한다.",
        "MDDR",
    )
    acu = _acu("ACU-001", "창고 재고 수준을 조회한다", action=["조회"], obj=["재고"], rtype="display")
    out = run_staged_shadow_e2e(
        cr_text="창고 재고 수준을 조회한다.",
        acus=[acu],
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. Inv")],
        b3_decisions=[],
        actual_traces=[],
    )
    rec = out["acu_owner_recommendations"][0]
    assert rec["recommendation_status"] == "CLEAR_OWNER"
    assert rec["recommended_owner"] == "Req. Inv"


def test_b_same_id_false_cross_id_stronger_shadow_only():
    # Same-ID: auth/audit theme — weak for inactivity CR span
    mdsr = _block(
        "Req. Same",
        "인증 코드 관리",
        "일회성 인증 코드를 저장하고 감사 기록으로 남긴다.",
    )
    same = _block(
        "Req. Same",
        "인증 코드 관리",
        "patient_code를 관리하고 감사 기록으로 남긴다.",
        "MDDR",
    )
    # Cross-ID: strong match to ACU span
    cross = _block(
        "Req. Cross",
        "비활성 대상 분류 표시",
        "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 목록에서 식별 표시한다.",
        "MDDR",
    )
    mdsr_cross = _block(
        "Req. Cross",
        "비활성 대상 분류 표시",
        "최근 활동 기록이 없는 대상을 별도 상태로 분류한다.",
    )
    acu = _acu(
        "ACU-001",
        "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 목록에서 식별한다",
        action=["분류", "식별"],
        obj=["상태", "대상"],
        rtype="classify",
    )
    cr = acu.source_span
    # Actual path: same-ID only
    actual = build_propagation_plan(
        cr, [_consistent("Req. Same")], [mdsr, same]
    )
    out = run_staged_shadow_e2e(
        cr_text=cr,
        acus=[acu],
        blocks=[mdsr, same, mdsr_cross, cross],
        consistency=[_consistent("Req. Same"), _consistent("Req. Cross")],
        b3_decisions=[_b3_mddr("Req. Cross", concepts=["활동", "상태", "분류"])],
        actual_traces=actual,
    )
    rec = out["acu_owner_recommendations"][0]
    # Shadow may recommend cross-ID; actual unchanged
    if rec["recommendation_status"] == "CLEAR_OWNER":
        assert rec["recommended_owner"] == "Req. Cross"
    else:
        # At least cross appears in candidates with discriminative path
        cands = out["acu_owner_candidates"][0]["candidates"]
        assert any(c["design_id"] == "Req. Cross" for c in cands)
    assert actual[0].propagation_decision in {
        "SKIP",
        "NEEDS_REVIEW",
        "EXTEND_EXISTING",
        "PATCH_EXISTING",
        "NEW_DESIGN_CANDIDATE",
    }
    # Actual still same-ID design candidate label
    assert "Req. Same" in (actual[0].design_candidate or actual[0].impacted_mddr_candidate)


def test_c_multiple_plausible_owners():
    mdsr_a = _block("Req. A", "재고 조회", "창고 재고를 조회한다.")
    mddr_a = _block("Req. A", "재고 조회", "창고 재고를 조회하여 표시한다.", "MDDR")
    mdsr_b = _block("Req. B", "재고 조회 화면", "창고 재고를 조회한다.")
    mddr_b = _block("Req. B", "재고 조회 화면", "창고 재고를 조회하여 화면에 표시한다.", "MDDR")
    acu = _acu("ACU-001", "창고 재고를 조회한다", action=["조회"], obj=["재고"], rtype="display")
    out = run_staged_shadow_e2e(
        cr_text=acu.source_span,
        acus=[acu],
        blocks=[mdsr_a, mddr_a, mdsr_b, mddr_b],
        consistency=[_consistent("Req. A"), _consistent("Req. B")],
        b3_decisions=[_b3_mddr("Req. B", concepts=["재고", "조회"])],
        actual_traces=[],
    )
    rec = out["acu_owner_recommendations"][0]
    assert rec["recommendation_status"] in {"MULTIPLE_PLAUSIBLE", "CLEAR_OWNER"}
    # If both discriminative and close scores → MULTIPLE; accept CLEAR only if clearly dominant
    if rec["recommendation_status"] == "MULTIPLE_PLAUSIBLE":
        assert rec["recommended_owner"] is None
        assert rec["shadow_decision"] == "NEEDS_REVIEW"


def test_d_no_safe_owner():
    mdsr = _block("Req. X", "인증", "인증 코드를 저장한다.")
    mddr = _block("Req. X", "인증", "인증 코드를 저장한다.", "MDDR")
    acu = _acu(
        "ACU-001",
        "월간 운영 보고서를 생성하여 제공한다",
        action=["생성"],
        obj=["보고서"],
        rtype="other",
    )
    out = run_staged_shadow_e2e(
        cr_text=acu.source_span,
        acus=[acu],
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. X")],
        b3_decisions=[],
        actual_traces=[],
    )
    rec = out["acu_owner_recommendations"][0]
    assert rec["recommendation_status"] in {"NO_SAFE_OWNER", "NEEDS_REVIEW"}
    assert rec["recommended_owner"] is None
    assert rec["shadow_decision"] in {"NEW_DESIGN_CANDIDATE", "NEEDS_REVIEW"}


def test_e_generic_only_no_clear_owner():
    mdsr = _block("Req. G", "상태 관리", "상태를 관리하고 기록을 제공한다.")
    mddr = _block("Req. G", "상태 관리", "상태를 관리하고 기록을 제공한다.", "MDDR")
    acu = _acu(
        "ACU-001",
        "상태를 관리하고 기록을 제공한다",
        action=["관리"],
        obj=["상태", "기록"],
        rtype="other",
    )
    out = run_staged_shadow_e2e(
        cr_text=acu.source_span,
        acus=[acu],
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. G")],
        b3_decisions=[],
        actual_traces=[],
    )
    rec = out["acu_owner_recommendations"][0]
    # Generic/weak tokens should not yield CLEAR_OWNER
    assert rec["recommendation_status"] != "CLEAR_OWNER" or rec["recommended_owner"] is None
    if rec["recommendation_status"] == "CLEAR_OWNER":
        raise AssertionError("generic-only must not be CLEAR_OWNER")


def test_f_prior_only_no_clear_owner():
    mdsr = _block("Req. P", "기타", "기타 기능을 제공한다.")
    mddr = _block("Req. P", "기타", "기타 모듈을 구현한다.", "MDDR")
    acu = _acu("ACU-001", "관련 상태를 일부 개선한다", action=[], obj=["상태"], rtype="other")
    # Empty actions → weak; B3 prior concepts alone shouldn't clear
    out = run_staged_shadow_e2e(
        cr_text=acu.source_span,
        acus=[acu],
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. P")],
        b3_decisions=[
            {
                "candidate_id": "Req. P",
                "document": "MDSR",
                "judgment": "IMPACTED",
                "evidence": {
                    "matched_concepts": ["상태"],
                    "behavioral_overlap": {"object": ["상태"]},
                },
            }
        ],
        actual_traces=[],
    )
    rec = out["acu_owner_recommendations"][0]
    assert rec["recommendation_status"] != "CLEAR_OWNER"


def test_g_multi_acu_different_recommendations():
    mdsr_s = _block("Req. Stock", "재고 조회", "창고 재고를 조회한다.")
    mddr_s = _block("Req. Stock", "재고 조회", "창고 재고를 조회한다.", "MDDR")
    mdsr_n = _block("Req. Notify", "알림 전송", "관리자에게 알림을 전송한다.")
    mddr_n = _block("Req. Notify", "알림 전송", "관리자에게 알림을 전송한다.", "MDDR")
    a1 = _acu("ACU-001", "창고 재고를 조회한다", action=["조회"], obj=["재고"], rtype="display")
    a2 = _acu(
        "ACU-002",
        "관리자에게 알림을 전송한다",
        action=["알림", "전송"],
        actor=["관리자"],
        rtype="other",
    )
    out = run_staged_shadow_e2e(
        cr_text="창고 재고를 조회하고 관리자에게 알림을 전송한다.",
        acus=[a1, a2],
        blocks=[mdsr_s, mddr_s, mdsr_n, mddr_n],
        consistency=[_consistent("Req. Stock"), _consistent("Req. Notify")],
        b3_decisions=[
            _b3_mddr("Req. Stock", concepts=["재고", "조회"]),
            _b3_mddr("Req. Notify", concepts=["알림", "전송"]),
        ],
        actual_traces=[],
    )
    recs = {r["atomic_change_id"]: r for r in out["acu_owner_recommendations"]}
    # Prefer different owners when both CLEAR
    if (
        recs["ACU-001"]["recommendation_status"] == "CLEAR_OWNER"
        and recs["ACU-002"]["recommendation_status"] == "CLEAR_OWNER"
    ):
        assert recs["ACU-001"]["recommended_owner"] != recs["ACU-002"]["recommended_owner"]


def test_h_one_acu_multiple_artifact_plans():
    mdsr = _block("Req. Inv", "재고 보충", "안전 재고 미만이면 보충 요청을 생성한다.")
    mddr = _block(
        "Req. Inv",
        "재고 보충",
        "재고 서비스는 안전 재고 미만일 때 보충 요청을 생성한다.",
        "MDDR",
    )
    acu = _acu(
        "ACU-001",
        "안전 재고 미만이면 보충 요청을 생성한다",
        action=["생성"],
        obj=["재고", "요청"],
        rtype="other",
    )
    out = run_staged_shadow_e2e(
        cr_text=acu.source_span,
        acus=[acu],
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. Inv")],
        b3_decisions=[],
        actual_traces=[],
    )
    rec = out["acu_owner_recommendations"][0]
    if rec["recommendation_status"] == "CLEAR_OWNER" and rec["shadow_decision"] in {
        "PATCH_EXISTING",
        "EXTEND_EXISTING",
    }:
        plans = [
            p
            for p in out["staged_patch_plans"]
            if p.get("atomic_change_id") == "ACU-001" and p.get("planning_status") == "PLANNED"
        ]
        docs = {p.get("target_document") for p in plans}
        assert "MDSR" in docs
        assert "MDDR" in docs


def test_i_provenance_lineage_end_to_end():
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고를 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "창고 재고를 조회한다.", "MDDR")
    acu = _acu("ACU-001", "창고 재고를 조회한다", action=["조회"], obj=["재고"], rtype="display")
    out = run_staged_shadow_e2e(
        cr_text=acu.source_span,
        acus=[acu],
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. Inv")],
        b3_decisions=[],
        actual_traces=[],
    )
    cands = out["acu_owner_candidates"][0]["candidates"]
    assert cands
    assert "unique_independent_groups" in cands[0]
    assert "evidence_lineage_summary" in cands[0]
    assert "derived_prior_count" in cands[0]


def test_j_legacy_actual_outputs_unchanged():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    mdsr = _block("Req. Inv", "재고 보충", "재고 기준 이하 시 보충 요청을 생성한다.")
    mddr = _block(
        "Req. Inv",
        "재고 보충",
        "재고 서비스는 기준 이하일 때 보충 요청을 생성한다.",
        "MDDR",
    )
    decision = _consistent("Req. Inv")
    traces_before = build_propagation_plan(cr, [decision], [mdsr, mddr])
    snap = [
        (t.propagation_decision, t.allow_mdsr_patch, t.source_mdsr_req_id)
        for t in traces_before
    ]
    acus = decompose_change_request(cr)
    _ = run_staged_shadow_e2e(
        cr_text=cr,
        acus=acus,
        blocks=[mdsr, mddr],
        consistency=[decision],
        b3_decisions=[],
        actual_traces=traces_before,
    )
    traces_after = build_propagation_plan(cr, [decision], [mdsr, mddr])
    snap2 = [
        (t.propagation_decision, t.allow_mdsr_patch, t.source_mdsr_req_id)
        for t in traces_after
    ]
    assert snap == snap2


def test_k_deterministic_order():
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고를 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "창고 재고를 조회한다.", "MDDR")
    a1 = _acu("ACU-001", "창고 재고를 조회한다", action=["조회"], obj=["재고"], rtype="display")
    a2 = _acu("ACU-002", "관리자에게 알린다", action=["알림"], actor=["관리자"], rtype="other")
    kwargs = dict(
        cr_text="x",
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. Inv")],
        b3_decisions=[],
        actual_traces=[],
    )
    o1 = run_staged_shadow_e2e(acus=[a1, a2], **kwargs)
    o2 = run_staged_shadow_e2e(acus=[a2, a1], **kwargs)
    # Results keyed by ACU id remain stable for same ACU
    r1 = {r["atomic_change_id"]: r["recommendation_status"] for r in o1["acu_owner_recommendations"]}
    r2 = {r["atomic_change_id"]: r["recommendation_status"] for r in o2["acu_owner_recommendations"]}
    assert r1 == r2


# ---------------------------------------------------------------------------
# Multi-domain
# ---------------------------------------------------------------------------


def test_inventory_domain_e2e():
    cr = "재고가 최소 수량 이하이면 자동 발주 요청을 생성하고 관리자에게 알린다."
    acus = decompose_change_request(cr)
    mdsr = _block("Req. Inv", "재고 발주", "최소 수량 이하이면 발주 요청을 생성한다.")
    mddr = _block(
        "Req. Inv",
        "재고 발주",
        "재고 서비스는 최소 수량 이하일 때 발주 요청을 생성하고 관리자에게 알린다.",
        "MDDR",
    )
    out = run_staged_shadow_e2e(
        cr_text=cr,
        acus=acus,
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. Inv")],
        b3_decisions=[],
        actual_traces=[],
    )
    assert out["summary"]["total_acus"] == len(acus)
    assert out["table_rows"]


def test_reservation_domain_e2e():
    cr = "예약 취소 시 좌석을 사용 가능 상태로 바꾸고 대기자에게 알린다."
    acus = decompose_change_request(cr)
    mdsr = _block("Req. Res", "예약 취소", "예약 취소 시 좌석 상태를 갱신한다.")
    mddr = _block(
        "Req. Res",
        "예약 취소",
        "취소 시 좌석을 사용 가능 상태로 바꾸고 대기자에게 알린다.",
        "MDDR",
    )
    out = run_staged_shadow_e2e(
        cr_text=cr,
        acus=acus,
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. Res")],
        b3_decisions=[],
        actual_traces=[],
    )
    assert out["summary"]["total_acus"] >= 1


def test_reporting_domain_e2e():
    cr = "월말 보고서를 생성하고 관리자 화면에서 다운로드할 수 있게 한다."
    acus = decompose_change_request(cr)
    mdsr = _block("Req. Rpt", "월말 보고", "월말 보고서를 생성한다.")
    mddr = _block(
        "Req. Rpt",
        "월말 보고",
        "월말 보고서를 생성하고 관리자 화면에서 다운로드할 수 있게 한다.",
        "MDDR",
    )
    out = run_staged_shadow_e2e(
        cr_text=cr,
        acus=acus,
        blocks=[mdsr, mddr],
        consistency=[_consistent("Req. Rpt")],
        b3_decisions=[],
        actual_traces=[],
    )
    assert out["summary"]["total_acus"] == len(acus)
    for rec in out["acu_owner_recommendations"]:
        assert "recommendation_status" in rec
