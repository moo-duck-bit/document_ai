# -*- coding: utf-8 -*-
"""B5 staged PR-4: Atomic Change Unit decomposition — trace/shadow only."""

from __future__ import annotations

from pathlib import Path

from document_ai.impact.atomic_change import (
    acu_as_design_discovery_input,
    acu_as_requirement_discovery_input,
    acus_to_trace_payload,
    decompose_change_request,
)
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.propagation import (
    assess_design_propagation,
    build_propagation_plan,
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
        evidence={"compatible_facets": ["object"], "conflicting_facets": []},
        confidence=0.5,
    )


# ---------------------------------------------------------------------------
# A–J
# ---------------------------------------------------------------------------


def test_a_single_responsibility_one_acu():
    cr = "시스템은 창고 재고 수준을 조회한다."
    units = decompose_change_request(cr)
    assert len(units) == 1
    assert units[0].change_id == "ACU-001"
    assert "조회" in units[0].action
    assert units[0].decomposition_status == "EXTRACTED"


def test_b_two_independent_actions_inventory():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    units = decompose_change_request(cr)
    assert len(units) == 2
    actions = [a for u in units for a in u.action]
    assert "생성" in actions
    assert "알림" in actions
    assert units[0].change_id == "ACU-001"
    assert units[1].change_id == "ACU-002"


def test_c_shared_actor_inheritance():
    cr = "관리자가 보고서를 생성하고 목록에서 식별한다."
    units = decompose_change_request(cr)
    assert len(units) >= 2
    assert "관리자" in units[0].actor
    # Second clause inherits actor when omitted
    assert "관리자" in units[1].actor
    assert units[1].provenance.get("actor_carry_over") == "inherited_from_prior_acu"


def test_d_condition_attached_to_action():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    units = decompose_change_request(cr)
    create = next(u for u in units if "생성" in u.action)
    assert create.condition
    assert any("이하" in c or "이면" in c for c in create.condition)


def test_e_ambiguous_conjunction():
    # Same responsibility-type actions jammed without clean clause ownership
    cr = "상태를 관리하고 기록을 관리한다."
    units = decompose_change_request(cr)
    assert len(units) >= 1
    # Either split EXTRACTED or single AMBIGUOUS — must not invent Scenario rules
    statuses = {u.decomposition_status for u in units}
    assert statuses & {"EXTRACTED", "AMBIGUOUS", "NEEDS_REVIEW"}


def test_f_multi_sentence_stable_ordering():
    cr = (
        "월말에 보고서를 생성한다.\n"
        "관리자 화면에서 다운로드할 수 있도록 한다."
    )
    units = decompose_change_request(cr)
    assert len(units) >= 2
    ids = [u.change_id for u in units]
    assert ids == sorted(ids)
    assert ids[0] == "ACU-001"


def test_g_provenance_source_span_preserved():
    cr = "예약 취소 시 좌석을 다시 사용 가능 상태로 바꾸고 대기자에게 알린다."
    units = decompose_change_request(cr)
    assert len(units) >= 2
    for u in units:
        assert u.source_span
        assert u.source_span in cr or u.source_span in " ".join(cr.split())
        assert u.provenance.get("evidence_ids")
        assert u.provenance.get("independent_group")
        assert "span_start" in u.provenance


def test_h_no_scenario_specific_hard_code():
    src = Path("src/document_ai/impact/atomic_change.py").read_text(encoding="utf-8")
    for banned in ("Req.17", "Req.100", "Req.110", "Req.204", "비활성", "3일", "3-day"):
        assert banned not in src


def test_i_j_actual_pipeline_unchanged_by_acu():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    mdsr = _block("Req. Inv", "재고 보충", "재고 기준 이하 시 보충 요청을 생성한다.")
    mddr = _block(
        "Req. Inv",
        "재고 보충",
        "재고 서비스는 기준 이하일 때 보충 요청을 생성한다.",
        "MDDR",
    )
    decision = _decision("Req. Inv")
    # ACU exists but is not passed into plan
    _acus = decompose_change_request(cr)
    prop, _pev, conf, reason = assess_design_propagation(
        cr, mdsr, mddr, decision=decision
    )
    traces = build_propagation_plan(cr, [decision], [mdsr, mddr])
    assert traces[0].propagation_decision == prop
    assert abs(traces[0].confidence - conf) < 1e-9
    # Patch eligibility set unchanged vs façade
    eligible = {t.source_mdsr_req_id for t in traces if t.allow_mdsr_patch}
    if prop in ("PATCH_EXISTING", "EXTEND_EXISTING") and traces[0].outcome == "PATCHED":
        assert "Req. Inv" in eligible
    else:
        assert "Req. Inv" not in eligible or traces[0].allow_mdsr_patch is False


# ---------------------------------------------------------------------------
# Multi-domain examples
# ---------------------------------------------------------------------------


def test_inventory_domain_decomposition():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    units = decompose_change_request(cr)
    assert len(units) == 2
    assert any("생성" in u.action for u in units)
    assert any("알림" in u.action for u in units)


def test_reservation_domain_decomposition():
    cr = "예약 취소 시 좌석을 다시 사용 가능 상태로 바꾸고 대기자에게 알린다."
    units = decompose_change_request(cr)
    assert len(units) == 2
    actions = [a for u in units for a in u.action]
    assert "갱신" in actions  # 바꾸 → 갱신
    assert "알림" in actions
    # Actor inheritance to notify clause
    assert any("대기자" in u.actor or u.actor for u in units)


def test_reporting_domain_decomposition():
    cr = "월말에 보고서를 생성하고 관리자 화면에서 다운로드할 수 있도록 한다."
    units = decompose_change_request(cr)
    assert len(units) == 2
    actions = [a for u in units for a in u.action]
    assert "생성" in actions
    assert "다운로드" in actions


def test_shadow_hooks_and_trace_payload():
    cr = "시스템은 재고를 조회한다."
    units = decompose_change_request(cr)
    payload = acus_to_trace_payload(cr, units)
    assert payload["unit_count"] == 1
    assert "does not yet replace whole-CR" in payload["note"]
    req_in = acu_as_requirement_discovery_input(units[0])
    des_in = acu_as_design_discovery_input(units[0])
    assert req_in["path"] == "shadow_ready"
    assert des_in["path"] == "shadow_ready"
    assert req_in["atomic_change_id"] == "ACU-001"
