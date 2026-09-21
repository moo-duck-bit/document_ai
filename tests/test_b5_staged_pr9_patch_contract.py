# -*- coding: utf-8 -*-
"""PR-9: Patch Contract — shadow interface for future semantic generation."""

from __future__ import annotations

from document_ai.impact.atomic_change import AtomicChangeUnit, decompose_change_request
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.patch_contract import (
    build_patch_contract,
    build_patch_contracts,
    build_semantic_intent_contract,
    compare_contracts_to_legacy,
    normalize_document_target,
    normalize_patch_operation,
    validate_patch_contract,
    validate_patch_contracts,
)
from document_ai.impact.patch_plan import PatchPlanItem, build_shadow_patch_plans
from document_ai.impact.propagation import PropagationTrace, build_propagation_plan
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
    status: str = "EXTRACTED",
    recipient: list[str] | None = None,
) -> AtomicChangeUnit:
    return AtomicChangeUnit(
        change_id=cid,
        source_span=span,
        actor=["implicit_system"],
        action=action,
        object=[],
        recipient=recipient or [],
        condition=[],
        constraint=[],
        output=[],
        responsibility_type="other",
        provenance={"evidence_ids": [f"ev_{cid}"]},
        confidence=0.7,
        decomposition_status=status,
        facet_origins=[
            {
                "value": a,
                "origin": "ACU_DIRECT",
                "source_span": span,
                "role": "action",
                "evidence_id": f"ev_{cid}",
            }
            for a in action
        ]
        + [
            {
                "value": "implicit_system",
                "origin": "ACU_DIRECT",
                "source_span": span,
                "role": "actor",
                "evidence_id": f"ev_{cid}",
            }
        ]
        + [
            {
                "value": r,
                "origin": "ACU_DIRECT",
                "source_span": span,
                "role": "recipient",
                "evidence_id": f"ev_{cid}",
            }
            for r in (recipient or [])
        ],
    )


def _plan(
    *,
    pid: str,
    acu_id: str,
    doc: str,
    tid: str,
    field: str,
    op: str = "EXTEND",
    status: str = "PLANNED",
) -> PatchPlanItem:
    return PatchPlanItem(
        patch_id=pid,
        atomic_change_id=acu_id,
        target_document=doc,
        target_id=tid,
        target_field=field,
        operation=op,
        semantic_intent="test",
        source_cr_span="span",
        justification="synthetic",
        owner_evidence_ids=["own_ev"],
        planning_status=status,
    )


def test_operation_normalization():
    assert normalize_patch_operation("EXTEND") == "UPDATE"
    assert normalize_patch_operation("MODIFY") == "UPDATE"
    assert normalize_patch_operation("NO_CHANGE") == "NO_ACTION"
    assert normalize_patch_operation("REVIEW") == "REVIEW_REQUIRED"
    assert normalize_patch_operation("weird") == "REVIEW_REQUIRED"
    assert normalize_patch_operation("ADD") == "ADD"


def test_target_normalization():
    t = normalize_document_target(
        document="mddr",
        requirement_id="Req. Inv",
        field="design_description",
    )
    assert t.document == "MDDR"
    assert t.field == "design_body"
    assert t.section == "MDDR.design_body"
    assert t.is_complete()
    bad = normalize_document_target(document="", requirement_id=None, field="")
    assert not bad.is_complete()


def test_semantic_intent_integrity():
    acu = _acu(
        "ACU-001",
        "관리자에게 알림을 보낸다.",
        action=["알림"],
        recipient=["관리자"],
    )
    intent = build_semantic_intent_contract(acu)
    d = intent.to_dict()
    assert d["action"] == "알림"
    assert d["actor"] == "implicit_system"
    assert d["recipient"] == "관리자"
    assert "prose" not in d
    assert isinstance(d["object"], list)


def test_single_acu_contract():
    cr = "시스템은 창고 재고 수준을 조회한다."
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고 수준을 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "재고 서비스가 창고 재고 수준을 조회한다.", "MDDR")
    decision = _consistent("Req. Inv")
    acus = decompose_change_request(cr)
    traces = build_propagation_plan(
        cr, [decision], [mdsr, mddr], owner_selection_mode="legacy"
    )
    plans = build_shadow_patch_plans(cr_text=cr, acus=acus, traces=traces)
    contracts = build_patch_contracts(acus=acus, plans=plans, traces=traces)
    assert len(contracts) >= 1
    c0 = contracts[0]
    assert c0.atomic_change_id.startswith("ACU-")
    assert "action" in c0.semantic_intent or "responsibility_type" in c0.semantic_intent
    assert "generated_text" not in c0.to_dict()
    assert c0.provenance.get("atomic_change_id") == c0.atomic_change_id


def test_multiple_acu_contracts():
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
    assert len(acus) >= 2
    traces = build_propagation_plan(
        cr, [decision], [mdsr, mddr], owner_selection_mode="legacy"
    )
    plans = build_shadow_patch_plans(cr_text=cr, acus=acus, traces=traces)
    contracts = build_patch_contracts(acus=acus, plans=plans, traces=traces)
    acu_ids = {c.atomic_change_id for c in contracts}
    assert len(acu_ids) >= 2


def test_review_required_on_incomplete():
    acu = _acu("ACU-001", "모호한 변경", action=["관리"], status="AMBIGUOUS")
    c = build_patch_contract(acu=acu, plan=None, owner_trace=None)
    assert c.review_required is True
    assert c.patch_operation == "REVIEW_REQUIRED"
    assert c.validation_status == "REVIEW_REQUIRED"


def test_no_owner_fallback_review():
    acu = _acu("ACU-001", "재고를 조회한다.", action=["조회"])
    c = build_patch_contract(acu=acu, plan=None, owner_trace=None)
    assert c.patch_operation == "REVIEW_REQUIRED"
    assert c.owner_requirement_id is None


def test_fallback_with_plan_and_trace():
    acu = _acu("ACU-001", "재고를 조회한다.", action=["조회"])
    plan = _plan(
        pid="PATCH-001",
        acu_id="ACU-001",
        doc="MDSR",
        tid="Req. Inv",
        field="criteria",
        op="EXTEND",
    )
    tr = PropagationTrace(
        source_mdsr_req_id="Req. Inv",
        mdsr_consistency_status="CONSISTENT",
        impacted_mddr_candidate="Req. Inv (MDDR)",
        propagation_reason="ok",
        outcome="PATCHED",
        evidence=[],
        design_candidate="Req. Inv (MDDR)",
        propagation_decision="EXTEND_EXISTING",
        allow_mdsr_patch=True,
        confidence=0.8,
        structured_evidence={"evidence_ids": ["ow1"]},
    )
    c = build_patch_contract(acu=acu, plan=plan, owner_trace=tr)
    assert c.patch_operation == "UPDATE"
    assert c.target["document"] == "MDSR"
    assert c.target["field"] == "criteria"
    assert c.owner_requirement_id == "Req. Inv"
    assert c.validation_status == "OK"
    assert not c.review_required


def test_validation_aggregate_and_diff():
    acu = _acu("ACU-001", "재고를 조회한다.", action=["조회"])
    contracts = build_patch_contracts(acus=[acu], plans=[], traces=[])
    report = validate_patch_contracts(contracts)
    assert report["total"] == 1
    assert report["review_required"] >= 1
    diff = compare_contracts_to_legacy(contracts=contracts, traces=[], plans=[])
    assert diff["contract_count"] == 1
    assert "legacy_target_count" in diff


def test_validate_forces_review_on_bad_target():
    acu = _acu("ACU-001", "재고를 조회한다.", action=["조회"])
    plan = _plan(
        pid="PATCH-001",
        acu_id="ACU-001",
        doc="MDSR",
        tid="Req. Inv",
        field="not_a_real_field",
        op="ADD",
    )
    tr = PropagationTrace(
        source_mdsr_req_id="Req. Inv",
        mdsr_consistency_status="CONSISTENT",
        impacted_mddr_candidate="Req. Inv (MDDR)",
        propagation_reason="ok",
        outcome="PATCHED",
        evidence=[],
        design_candidate="Req. Inv (MDDR)",
        propagation_decision="PATCH_EXISTING",
        allow_mdsr_patch=True,
        confidence=0.8,
        structured_evidence={"evidence_ids": ["ow1"]},
    )
    c = build_patch_contract(acu=acu, plan=plan, owner_trace=tr)
    assert c.review_required is True
    assert "incomplete_target" in c.validation_issues


def test_no_prose_in_contract_payload():
    acu = _acu("ACU-002", "관리자에게 알림", action=["알림"], recipient=["관리자"])
    c = validate_patch_contract(build_patch_contract(acu=acu))
    blob = str(c.to_dict())
    assert "변경 요청 반영" not in blob
    assert "설계 반영" not in blob
