# -*- coding: utf-8 -*-
"""PR-8: ACU owner selection activation — generation/DOCX unchanged."""

from __future__ import annotations

from document_ai.impact.atomic_change import AtomicChangeUnit, decompose_change_request
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.owner_activation import (
    build_owner_activation_diff,
    build_owner_activation_summary,
    resolve_owner_selection_mode,
    select_owners_via_acu,
    usable_acus_for_owner_selection,
)
from document_ai.impact.propagation import build_propagation_plan, proposed_mdsr_description
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


def _consistent(req_id: str, desc: str = "기존 설명") -> ConsistencyDecision:
    return ConsistencyDecision(
        req_id=req_id,
        document="MDSR",
        status="CONSISTENT",
        reason="synthetic",
        allow_auto_patch=True,
        fields={"description": desc},
        evidence={"compatible_facets": ["object", "action"], "conflicting_facets": []},
        confidence=0.6,
    )


def _acu(cid: str, span: str, *, action: list[str], status: str = "EXTRACTED") -> AtomicChangeUnit:
    return AtomicChangeUnit(
        change_id=cid,
        source_span=span,
        actor=["implicit_system"],
        action=action,
        object=[],
        condition=[],
        constraint=[],
        output=[],
        responsibility_type="other",
        provenance={"evidence_ids": [f"ev_{cid}"]},
        confidence=0.7,
        decomposition_status=status,
    )


def test_legacy_fallback_when_empty_acu():
    cr = "시스템은 창고 재고 수준을 조회한다."
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고 수준을 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "재고 서비스가 창고 재고 수준을 조회한다.", "MDDR")
    decision = _consistent("Req. Inv")
    empty: list[AtomicChangeUnit] = []
    mode, reason = resolve_owner_selection_mode("auto", empty)
    assert mode == "legacy"
    assert "fallback" in reason or "empty" in reason
    traces, staged = build_propagation_plan(
        cr,
        [decision],
        [mdsr, mddr],
        return_stages=True,
        acus=empty,
        owner_selection_mode="auto",
    )
    assert len(traces) == 1
    assert staged["owner_activation_summary"]["effective_mode"] == "legacy"
    assert staged["acu_owner_mapping"]["entries"] == []


def test_single_acu_owner_selection():
    cr = "시스템은 창고 재고 수준을 조회한다."
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고 수준을 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "재고 서비스가 창고 재고 수준을 조회한다.", "MDDR")
    decision = _consistent("Req. Inv")
    acus = decompose_change_request(cr)
    assert len(usable_acus_for_owner_selection(acus)) >= 1
    traces, staged = build_propagation_plan(
        cr,
        [decision],
        [mdsr, mddr],
        return_stages=True,
        acus=acus,
        owner_selection_mode="acu",
    )
    assert len(traces) == 1
    assert staged["owner_activation_summary"]["effective_mode"] == "acu"
    assert staged["owner_activation_summary"]["acu_count"] >= 1
    assert any(
        e.get("path") == "actual_acu" for e in (staged.get("design_candidates") or [])
    )
    # Generation helper still whole-CR (unchanged contract)
    text = proposed_mdsr_description(decision, cr)
    assert text is None or cr[:8] in text or "변경 요청" in (text or "")


def test_multiple_acus_independent_evaluation():
    cr = "재고가 기준 이하이면 자동 보충 요청을 생성하고 관리자에게 알린다."
    mdsr = _block("Req. Inv", "재고 보충", "재고 기준 이하 시 보충 요청을 생성하고 알린다.")
    mddr = _block(
        "Req. Inv",
        "재고 보충",
        "재고 서비스는 기준 이하일 때 보충 요청을 생성하고 관리자에게 알린다.",
        "MDDR",
    )
    decision = _consistent("Req. Inv")
    acus = decompose_change_request(cr)
    assert len(usable_acus_for_owner_selection(acus)) >= 2
    payload = select_owners_via_acu(
        cr_text=cr,
        acus=acus,
        consistency=[decision],
        blocks=[mdsr, mddr],
    )
    acu_ids = {r["atomic_change_id"] for r in payload["mapping"]}
    assert len(acu_ids) >= 2
    # Each ACU evaluated against the requirement
    assert all(r["requirement_id"] == "Req. Inv" for r in payload["mapping"])
    traces, staged = build_propagation_plan(
        cr,
        [decision],
        [mdsr, mddr],
        return_stages=True,
        acus=acus,
        owner_selection_mode="auto",
    )
    assert staged["owner_activation_summary"]["effective_mode"] == "acu"
    assert staged["owner_activation_summary"]["acu_count"] >= 2
    assert "legacy_targets" in staged["owner_activation_summary"]
    assert "acu_targets" in staged["owner_activation_summary"]
    assert staged["acu_owner_mapping"]["entries"]
    assert len(traces) == 1  # still requirement-level for apply


def test_empty_acu_list_explicit_acu_falls_back():
    cr = "시스템은 재고를 조회한다."
    mdsr = _block("Req. Inv", "재고", "재고를 조회한다.")
    mddr = _block("Req. Inv", "재고", "재고 조회 설계", "MDDR")
    decision = _consistent("Req. Inv")
    traces, staged = build_propagation_plan(
        cr,
        [decision],
        [mdsr, mddr],
        return_stages=True,
        acus=[],
        owner_selection_mode="acu",
    )
    assert staged["owner_activation_summary"]["effective_mode"] == "legacy"
    assert len(traces) == 1


def test_legacy_vs_acu_diff_artifact():
    cr = "시스템은 창고 재고 수준을 조회한다."
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고 수준을 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "재고 서비스가 창고 재고 수준을 조회한다.", "MDDR")
    decision = _consistent("Req. Inv")
    acus = decompose_change_request(cr)
    traces, staged = build_propagation_plan(
        cr,
        [decision],
        [mdsr, mddr],
        return_stages=True,
        acus=acus,
        owner_selection_mode="auto",
    )
    diff = staged["owner_activation_diff"]
    assert diff["stage"] == "owner_activation_diff"
    assert "legacy_targets" in diff
    assert "acu_targets" in diff
    summary = build_owner_activation_summary(
        effective_mode="acu",
        mode_reason="test",
        acus=acus,
        legacy_traces=traces,
        active_traces=traces,
    )
    assert summary["generation_unchanged"] is True
    assert summary["b3_b4_unchanged"] is True


def test_ambiguous_acu_does_not_alone_grant_owner():
    cr = "상태 관련 정책을 조정한다."
    mdsr = _block("Req. X", "상태", "상태를 관리한다.")
    mddr = _block("Req. X", "상태", "상태 관리 설계", "MDDR")
    decision = _consistent("Req. X")
    acus = [
        _acu("ACU-001", "상태 관련 정책을 조정한다.", action=[], status="AMBIGUOUS"),
    ]
    payload = select_owners_via_acu(
        cr_text=cr, acus=acus, consistency=[decision], blocks=[mdsr, mddr]
    )
    assert all(not r.get("owner_found") for r in payload["mapping"])
    assert all(r["propagation_decision"] == "NEEDS_REVIEW" for r in payload["mapping"])


def test_default_mode_remains_legacy_compatible():
    """Library default stays legacy so older tests keep CR-level owner selection."""
    cr = "시스템은 창고 재고 수준을 조회한다."
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고 수준을 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "재고 서비스가 창고 재고 수준을 조회한다.", "MDDR")
    decision = _consistent("Req. Inv")
    traces, staged = build_propagation_plan(
        cr, [decision], [mdsr, mddr], return_stages=True
    )
    assert staged["owner_activation_summary"]["effective_mode"] == "legacy"
    assert traces[0].structured_evidence.get("owner_selection") == "legacy_cr"


def test_diff_builder_counts_targets():
    cr = "시스템은 재고를 조회한다."
    mdsr = _block("Req. Inv", "재고", "재고를 조회한다.")
    mddr = _block("Req. Inv", "재고", "재고 조회", "MDDR")
    decision = _consistent("Req. Inv")
    leg = build_propagation_plan(
        cr, [decision], [mdsr, mddr], owner_selection_mode="legacy"
    )
    acus = decompose_change_request(cr)
    acu = build_propagation_plan(
        cr, [decision], [mdsr, mddr], acus=acus, owner_selection_mode="acu"
    )
    diff = build_owner_activation_diff(legacy_traces=leg, acu_traces=acu)
    assert isinstance(diff["legacy_targets"], int)
    assert isinstance(diff["acu_targets"], int)
