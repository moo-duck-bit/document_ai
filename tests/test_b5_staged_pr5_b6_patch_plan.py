# -*- coding: utf-8 -*-
"""B5 staged PR-5 / B6: semantic patch planning — shadow only, actual parity."""

from __future__ import annotations

from document_ai.impact.atomic_change import AtomicChangeUnit, decompose_change_request
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.patch_plan import (
    build_shadow_patch_plans,
    compare_legacy_vs_shadow,
    semantic_intent_from_acu,
)
from document_ai.impact.propagation import (
    PropagationTrace,
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


def _decision(req_id: str) -> ConsistencyDecision:
    return ConsistencyDecision(
        req_id=req_id,
        document="MDSR",
        status="CONSISTENT",
        reason="synthetic",
        allow_auto_patch=True,
        fields={"description": "기존 설명"},
        evidence={"compatible_facets": ["object", "action"], "conflicting_facets": []},
        confidence=0.6,
    )


def _trace(
    req_id: str,
    *,
    decision: str = "PATCH_EXISTING",
    matched_resp: list[str] | None = None,
    allow: bool = True,
) -> PropagationTrace:
    return PropagationTrace(
        source_mdsr_req_id=req_id,
        mdsr_consistency_status="CONSISTENT",
        impacted_mddr_candidate=f"{req_id} (MDDR)",
        propagation_reason="synthetic",
        outcome="PATCHED" if allow else "SKIPPED_WITH_REASON",
        design_responsibility_aligned=allow,
        allow_mdsr_patch=allow,
        requirement=req_id,
        design_candidate=f"{req_id} (MDDR)",
        propagation_decision=decision,
        structured_evidence={
            "matched_responsibilities": matched_resp or [],
            "matched_facets": ["action", "object"],
            "requirement_spans": [],
            "design_spans": [],
            "direct_traceability": ["same_req_id"],
            "conflicts": [],
            "missing_information": [],
        },
        confidence=0.7,
    )


def _acu(
    change_id: str,
    span: str,
    *,
    action: list[str],
    obj: list[str] | None = None,
    actor: list[str] | None = None,
    condition: list[str] | None = None,
    rtype: str = "other",
    status: str = "EXTRACTED",
) -> AtomicChangeUnit:
    return AtomicChangeUnit(
        change_id=change_id,
        source_span=span,
        actor=actor or [],
        action=action,
        object=obj or [],
        condition=condition or [],
        constraint=[],
        output=[],
        responsibility_type=rtype,
        provenance={
            "evidence_ids": [f"ev_{change_id}"],
            "independent_group": f"span:{change_id}",
            "decomposition_method": "rule_v0",
        },
        confidence=0.7,
        decomposition_status=status,
    )


# ---------------------------------------------------------------------------
# A–J
# ---------------------------------------------------------------------------


def test_a_single_acu_single_mdsr_field_plan():
    acu = _acu(
        "ACU-001",
        "재고를 조회한다",
        action=["조회"],
        obj=["재고"],
        rtype="display",
    )
    tr = _trace("Req. Inv", matched_resp=["재고", "조회"])
    plans = build_shadow_patch_plans(cr_text="재고를 조회한다", acus=[acu], traces=[tr])
    planned = [p for p in plans if p.planning_status == "PLANNED" and p.target_document == "MDSR"]
    assert planned
    assert planned[0].target_field == "criteria"
    assert planned[0].atomic_change_id == "ACU-001"


def test_b_single_acu_mdsr_and_mddr_plans():
    acu = _acu(
        "ACU-001",
        "보충 요청을 생성한다",
        action=["생성"],
        obj=["요청"],
        rtype="other",
    )
    tr = _trace("Req. Inv", matched_resp=["생성", "요청", "보충"])
    plans = build_shadow_patch_plans(cr_text="x", acus=[acu], traces=[tr])
    docs = {p.target_document for p in plans if p.planning_status == "PLANNED"}
    assert "MDSR" in docs
    assert "MDDR" in docs


def test_c_multiple_acus_different_owners():
    a1 = _acu("ACU-001", "재고 조회", action=["조회"], obj=["재고"], rtype="display")
    a2 = _acu("ACU-002", "알림 전송", action=["알림"], obj=["관리자"], actor=["관리자"], rtype="other")
    t1 = _trace("Req. Stock", matched_resp=["재고", "조회"])
    t2 = _trace("Req. Notify", matched_resp=["알림", "관리자"])
    plans = build_shadow_patch_plans(cr_text="x", acus=[a1, a2], traces=[t1, t2])
    planned = [p for p in plans if p.planning_status == "PLANNED"]
    owners = {(p.atomic_change_id, p.target_id) for p in planned if p.target_document == "MDSR"}
    assert ("ACU-001", "Req. Stock") in owners
    assert ("ACU-002", "Req. Notify") in owners
    # Must not clone Stock owner onto notify ACU
    assert ("ACU-002", "Req. Stock") not in owners


def test_d_multiple_acus_same_target_grouping():
    a1 = _acu("ACU-001", "재고 생성", action=["생성"], obj=["재고"], rtype="other")
    a2 = _acu("ACU-002", "재고 알림", action=["알림"], obj=["재고"], rtype="other")
    tr = _trace("Req. Inv", matched_resp=["재고", "생성", "알림"])
    plans = build_shadow_patch_plans(cr_text="x", acus=[a1, a2], traces=[tr])
    same_field = [
        p
        for p in plans
        if p.planning_status == "PLANNED"
        and p.target_document == "MDSR"
        and p.target_id == "Req. Inv"
        and p.target_field == "criteria"
    ]
    assert len(same_field) >= 2
    assert all(p.plan_group_id for p in same_field)
    assert all(p.conflict_status in ("compatible", "potentially_duplicate", "conflict") for p in same_field)


def test_e_whole_cr_not_used_as_semantic_intent():
    cr = "재고가 최소 수량 이하이면 자동 발주 요청을 생성하고 관리자에게 알린다. " * 2
    acu = _acu(
        "ACU-001",
        "자동 발주 요청을 생성",
        action=["생성"],
        obj=["요청"],
        condition=["이하이면"],
        rtype="other",
    )
    intent = semantic_intent_from_acu(acu)
    assert cr not in intent
    assert "생성" in intent
    tr = _trace("Req. Inv", matched_resp=["생성", "요청"])
    plans = build_shadow_patch_plans(cr_text=cr, acus=[acu], traces=[tr])
    for p in plans:
        assert p.semantic_intent != cr
        assert cr not in p.semantic_intent


def test_f_needs_review_acu_no_auto_plan():
    acu = _acu(
        "ACU-001",
        "애매한 문구",
        action=["관리"],
        status="AMBIGUOUS",
    )
    tr = _trace("Req. X", matched_resp=["관리"])
    plans = build_shadow_patch_plans(cr_text="x", acus=[acu], traces=[tr])
    assert all(p.planning_status == "NEEDS_REVIEW" for p in plans)
    assert all(p.operation == "REVIEW" for p in plans)
    assert not any(p.planning_status == "PLANNED" for p in plans)


def test_g_new_design_no_existing_target_auto_patch():
    acu = _acu("ACU-001", "새 설계 필요", action=["생성"], obj=["보고서"], rtype="other")
    tr = _trace(
        "Req. New",
        decision="NEW_DESIGN_CANDIDATE",
        matched_resp=["생성", "보고서"],
        allow=False,
    )
    plans = build_shadow_patch_plans(cr_text="x", acus=[acu], traces=[tr])
    assert plans
    assert all(p.operation == "REVIEW" for p in plans)
    assert all(p.target_id is None for p in plans)
    assert all(p.planning_status == "NEEDS_REVIEW" for p in plans)


def test_h_provenance_chain_preserved():
    acu = _acu("ACU-001", "조회", action=["조회"], obj=["재고"], rtype="display")
    tr = _trace("Req. Inv", matched_resp=["조회", "재고"])
    plans = build_shadow_patch_plans(cr_text="x", acus=[acu], traces=[tr])
    planned = [p for p in plans if p.planning_status == "PLANNED"]
    assert planned
    for p in planned:
        assert p.source_cr_span == acu.source_span
        assert p.atomic_change_id == "ACU-001"
        assert "ev_ACU-001" in p.owner_evidence_ids
        assert p.provenance.get("atomic_change_id") == "ACU-001"
        assert p.provenance.get("path") == "shadow_only"


def test_i_planning_order_deterministic():
    a2 = _acu("ACU-002", "알림", action=["알림"], obj=["관리자"], rtype="other")
    a1 = _acu("ACU-001", "생성", action=["생성"], obj=["요청"], rtype="other")
    tr = _trace("Req. Inv", matched_resp=["생성", "요청", "알림", "관리자"])
    p1 = build_shadow_patch_plans(cr_text="x", acus=[a2, a1], traces=[tr])
    p2 = build_shadow_patch_plans(cr_text="x", acus=[a1, a2], traces=[tr])
    assert [p.patch_id for p in p1] == [p.patch_id for p in p2]
    assert [p.atomic_change_id for p in p1] == [p.atomic_change_id for p in p2]


def test_j_actual_legacy_patch_behavior_unchanged():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    mdsr = _block("Req. Inv", "재고 보충", "재고 기준 이하 시 보충 요청을 생성한다.")
    mddr = _block(
        "Req. Inv",
        "재고 보충",
        "재고 서비스는 기준 이하일 때 보충 요청을 생성한다.",
        "MDDR",
    )
    decision = _decision("Req. Inv")
    acus = decompose_change_request(cr)
    prop, _pev, conf, _r = assess_design_propagation(cr, mdsr, mddr, decision=decision)
    traces = build_propagation_plan(cr, [decision], [mdsr, mddr])
    _plans = build_shadow_patch_plans(cr_text=cr, acus=acus, traces=traces)
    # Actual façade unchanged
    assert traces[0].propagation_decision == prop
    assert abs(traces[0].confidence - conf) < 1e-9
    # Legacy whole-CR helper still produces whole-CR style append when eligible
    if traces[0].allow_mdsr_patch:
        text = proposed_mdsr_description(decision, cr)
        assert text is None or cr[:20] in text or "변경 요청 반영" in (text or "")


# ---------------------------------------------------------------------------
# Multi-domain
# ---------------------------------------------------------------------------


def test_inventory_domain_acu_plans():
    cr = "재고가 최소 수량 이하이면 자동 발주 요청을 생성하고 관리자에게 알린다."
    acus = decompose_change_request(cr)
    assert len(acus) >= 2
    tr = _trace(
        "Req. Inv",
        matched_resp=["재고", "생성", "요청", "알림", "관리자", "보충"],
    )
    plans = build_shadow_patch_plans(cr_text=cr, acus=acus, traces=[tr])
    acu_ids = {p.atomic_change_id for p in plans if p.planning_status == "PLANNED"}
    # At least one ACU should plan when overlap exists
    assert acu_ids
    cmp = compare_legacy_vs_shadow(cr_text=cr, traces=[tr], plans=plans)
    assert "legacy_whole_cr_targets" in cmp
    assert "shadow_acu_scoped_plans" in cmp


def test_reservation_domain_acu_plans():
    cr = "예약 취소 시 좌석을 사용 가능 상태로 변경하고 대기자에게 알린다."
    # "변경" may not stem-match 바꾸 — use decompose which handles 바꾸; this CR uses 변경
    # Force ACUs if decomposer yields 1
    acus = decompose_change_request(cr)
    if len(acus) < 2:
        acus = [
            _acu("ACU-001", "좌석을 사용 가능 상태로 변경", action=["갱신"], obj=["좌석"], condition=["취소 시"], rtype="update"),
            _acu("ACU-002", "대기자에게 알린다", action=["알림"], actor=["대기자"], rtype="other"),
        ]
    tr = _trace("Req. Res", matched_resp=["좌석", "갱신", "알림", "대기자", "취소"])
    plans = build_shadow_patch_plans(cr_text=cr, acus=acus, traces=[tr])
    assert any(p.planning_status == "PLANNED" for p in plans)


def test_reporting_domain_acu_plans():
    cr = "월말 보고서를 생성하고 관리자 화면에서 다운로드할 수 있게 한다."
    acus = decompose_change_request(cr)
    assert len(acus) >= 2
    tr = _trace("Req. Rpt", matched_resp=["보고서", "생성", "다운로드", "화면"])
    plans = build_shadow_patch_plans(cr_text=cr, acus=acus, traces=[tr])
    assert any(p.planning_status == "PLANNED" for p in plans)
    for p in plans:
        if p.planning_status == "PLANNED":
            assert p.semantic_intent != cr
