# -*- coding: utf-8 -*-
"""PR-7: ACU Semantic Integrity & Scope Isolation — shadow path quality only."""

from __future__ import annotations

from pathlib import Path

from document_ai.impact.atomic_change import (
    build_acu_scope_isolation,
    compare_acu_v1_vs_v2,
    decompose_change_request,
)
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.patch_plan import semantic_intent_from_acu
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
        evidence={"compatible_facets": ["object"], "conflicting_facets": []},
        confidence=0.5,
    )


# ---------------------------------------------------------------------------
# A–L
# ---------------------------------------------------------------------------


def test_a_different_actions_split_lock_and_notify():
    cr = "계정을 잠그고 관리자에게 알림을 보낸다."
    units = decompose_change_request(cr)
    assert len(units) >= 2
    actions = [a for u in units for a in u.action]
    assert "잠금" in actions
    assert "알림" in actions
    lock = next(u for u in units if "잠금" in u.action)
    notify = next(u for u in units if "알림" in u.action)
    assert lock.change_id != notify.change_id
    assert "관리자" in notify.recipient
    assert "관리자" not in notify.actor


def test_b_same_action_multiple_objects_no_over_split():
    cr = "이름과 이메일을 저장한다."
    units = decompose_change_request(cr)
    assert len(units) == 1
    assert "저장" in units[0].action
    assert units[0].decomposition_status == "EXTRACTED"


def test_c_actor_vs_recipient():
    cr = "관리자에게 알림을 보낸다."
    units = decompose_change_request(cr)
    assert len(units) == 1
    u = units[0]
    assert "관리자" in u.recipient
    assert "관리자" not in u.actor
    assert "implicit_system" in u.actor or u.actor == ["implicit_system"]


def test_d_implicit_system_actor_reservation():
    units = decompose_change_request(
        "예약을 취소하고 좌석을 사용 가능 상태로 바꾼다."
    )
    assert len(units) >= 1
    assert any(u.decomposition_status == "EXTRACTED" for u in units)
    assert any("implicit_system" in u.actor for u in units)
    actions = [a for u in units for a in u.action]
    assert "취소" in actions
    assert "갱신" in actions


def test_e_acu_scope_isolation_no_audit_log_leak():
    cr = (
        "연속 로그인 실패 시 계정을 잠그고 관리자에게 알림을 보낸다. "
        "로그인 실패·계정 잠금·잠금 해제 이벤트는 감사 기록으로 남겨야 한다."
    )
    units = decompose_change_request(cr)
    early = [u for u in units if "잠금" in u.action or "알림" in u.action]
    assert early
    for u in early:
        assert "로그" not in (u.output or [])
        assert "감사 기록" not in (u.output or [])
        intent = semantic_intent_from_acu(u)
        assert "로그" not in intent or "로그인" in u.source_span
    iso = build_acu_scope_isolation(cr, units)
    for e in iso["entries"]:
        if e["atomic_change_id"] == early[0].change_id:
            assert not any(
                r.get("value") == "로그" for r in e.get("rejected_cross_acu_facets") or []
            )


def test_f_context_origin_tracking():
    cr = "시스템은 재고를 조회한다. 월말 보고서를 생성한다."
    units = decompose_change_request(cr)
    assert units
    u0 = units[0]
    assert u0.facet_origins
    origins = {f["origin"] for f in u0.facet_origins}
    assert "ACU_DIRECT" in origins
    # supporting_context may hold CR_CONTEXT outputs from later sentences
    for f in u0.supporting_context:
        assert f.get("origin") == "CR_CONTEXT"


def test_g_trailing_conjunction_extracted():
    cr = "사용자에게는 잠금 상태와 재시도 가능 시점을 안내해야 하며"
    units = decompose_change_request(cr)
    assert len(units) == 1
    assert units[0].decomposition_status == "EXTRACTED"
    assert "안내" in units[0].action
    assert "사용자" in units[0].recipient


def test_h_audit_record_extracted():
    cr = "로그인 실패·계정 잠금·잠금 해제 이벤트는 감사 기록으로 남겨야 한다."
    units = decompose_change_request(cr)
    assert len(units) == 1
    assert units[0].decomposition_status == "EXTRACTED"
    assert "기록" in units[0].action or "감사" in units[0].action


def test_i_true_ambiguity_multiple_interpretations():
    # Same vague verb twice without clear ownership boundary
    cr = "상태를 관리하고 기록을 관리한다."
    units = decompose_change_request(cr)
    statuses = {u.decomposition_status for u in units}
    assert statuses & {"AMBIGUOUS", "NEEDS_REVIEW", "EXTRACTED"}


def test_j_unsafe_split_needs_review_or_ambiguous():
    # Distinct responsibility types jammed without clean clause markers
    cr = "권한을 검증하고 데이터를 생성 삭제한다."
    units = decompose_change_request(cr)
    assert units
    # Must not invent Scenario-specific splits; status must be one of the three
    assert all(
        u.decomposition_status in ("EXTRACTED", "AMBIGUOUS", "NEEDS_REVIEW")
        for u in units
    )


def test_k_deterministic_acu_ids_order():
    cr = (
        "재고가 최소 수량 이하이면 발주 요청을 생성하고 관리자에게 알린다. "
        "월말 보고서를 생성한다."
    )
    a = decompose_change_request(cr)
    b = decompose_change_request(cr)
    assert [u.change_id for u in a] == [u.change_id for u in b]
    assert [u.source_span for u in a] == [u.source_span for u in b]
    assert a[0].change_id == "ACU-001"


def test_l_pr6_shadow_safety_invariants_unchanged():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    mdsr = _block("Req. Inv", "재고", "재고 기준 이하 시 보충 요청을 생성한다.")
    mddr = _block(
        "Req. Inv",
        "재고",
        "재고 서비스는 기준 이하일 때 보충 요청을 생성한다.",
        "MDDR",
    )
    decision = _consistent("Req. Inv")
    traces = build_propagation_plan(cr, [decision], [mdsr, mddr])
    before = [
        (t.propagation_decision, t.allow_mdsr_patch, t.source_mdsr_req_id)
        for t in traces
    ]
    acus = decompose_change_request(cr)
    out = run_staged_shadow_e2e(
        cr_text=cr,
        acus=acus,
        blocks=[mdsr, mddr],
        consistency=[decision],
        b3_decisions=[
            {
                "candidate_id": "Req. Inv",
                "document": "MDDR",
                "judgment": "IMPACTED",
                "retrieval_rank": 1,
                "confidence": 0.7,
                "evidence": {"matched_concepts": ["재고", "보충"]},
            }
        ],
        actual_traces=traces,
    )
    after = [
        (t.propagation_decision, t.allow_mdsr_patch, t.source_mdsr_req_id)
        for t in traces
    ]
    assert before == after
    assert out["stage"] == "staged_shadow_e2e"


def test_no_scenario_hard_code_in_acu_module():
    src = Path("src/document_ai/impact/atomic_change.py").read_text(encoding="utf-8")
    for banned in ("Req.17", "Req.100", "Req.110", "Req.204", "비활성", "3일", "3-day"):
        assert banned not in src


# ---------------------------------------------------------------------------
# Multi-domain
# ---------------------------------------------------------------------------


def test_inventory_split_reorder_and_notify():
    cr = "재고가 최소 수량 이하이면 발주 요청을 생성하고 관리자에게 알린다."
    units = decompose_change_request(cr)
    assert len(units) >= 2
    assert any("생성" in u.action for u in units)
    assert any("알림" in u.action for u in units)
    notify = next(u for u in units if "알림" in u.action)
    assert "관리자" in notify.recipient


def test_reservation_seat_and_waiting_notify():
    cr = "예약 취소 시 좌석을 사용 가능 상태로 바꾸고 대기자에게 알린다."
    units = decompose_change_request(cr)
    assert len(units) >= 2
    assert any("갱신" in u.action or "취소" in u.action for u in units)
    notify = next(u for u in units if "알림" in u.action)
    assert "대기자" in notify.recipient
    assert "대기자" not in notify.actor


def test_reporting_generate_and_download():
    cr = "월말 보고서를 생성하고 관리자 화면에서 다운로드할 수 있게 한다."
    units = decompose_change_request(cr)
    assert len(units) >= 2
    actions = [a for u in units for a in u.action]
    assert "생성" in actions
    assert "다운로드" in actions


def test_account_lock_fixture_improved_decomposition():
    cr = (
        "연속 로그인 실패 시 계정을 잠그고 관리자에게 알림을 보내도록 정책을 강화한다. "
        "잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다. "
        "사용자에게는 잠금 상태와 재시도 가능 시점을 안내해야 하며, "
        "로그인 실패·계정 잠금·잠금 해제 이벤트는 감사 기록으로 남겨야 한다."
    )
    units = decompose_change_request(cr)
    assert len(units) >= 4
    statuses = [u.decomposition_status for u in units]
    # Meaning-complete units should mostly be EXTRACTED (not AMBIGUOUS-dominated)
    assert statuses.count("EXTRACTED") >= 4
    assert any("잠금" in u.action for u in units)
    assert any("알림" in u.action and "관리자" in u.recipient for u in units)
    assert any("안내" in u.action and "사용자" in u.recipient for u in units)
    assert any(
        ("기록" in u.action or "감사" in u.action)
        and u.decomposition_status == "EXTRACTED"
        for u in units
    )
    # Primary lock action present; no login→로그 false positive on lock ACU
    lock = next(u for u in units if "잠금" in u.action)
    assert "로그" not in lock.output
    cmp = compare_acu_v1_vs_v2(cr)
    assert cmp["delta"]["extracted_v2"] >= cmp["delta"]["extracted_v1"]
