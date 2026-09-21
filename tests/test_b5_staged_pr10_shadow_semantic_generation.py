# -*- coding: utf-8 -*-
"""PR-10: Shadow semantic generation from Patch Contract."""

from __future__ import annotations

import inspect

from document_ai.impact.atomic_change import decompose_change_request
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.patch_contract import (
    PatchContract,
    build_patch_contract,
    build_patch_contracts,
    validate_patch_contract,
)
from document_ai.impact.patch_plan import PatchPlanItem, build_shadow_patch_plans
from document_ai.impact.propagation import (
    PropagationTrace,
    build_propagation_plan,
    proposed_mdsr_description,
)
from document_ai.impact.semantic_draft import (
    compare_legacy_vs_semantic_drafts,
    generate_semantic_draft,
    generate_semantic_drafts,
    semantic_generation_summary,
    validate_semantic_drafts,
)
from document_ai.impact.semantic_draft import generate_semantic_draft as _gen
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


def _ok_contract(
    *,
    cid: str = "PC-ACU-001",
    acu_id: str = "ACU-001",
    op: str = "UPDATE",
    action: str = "조회",
    recipient: str | None = None,
    obj: list[str] | None = None,
    condition: str | None = None,
    constraint: list[str] | None = None,
    affected: list[str] | None = None,
    output: list[str] | None = None,
    span: str = "재고를 조회한다",
    field: str = "criteria",
    doc: str = "MDSR",
    rid: str = "Req. Inv",
) -> PatchContract:
    intent = {
        "responsibility_type": "other",
        "actor": "implicit_system",
        "recipient": recipient,
        "action": action,
        "object": obj or [],
        "condition": condition,
        "constraint": constraint or [],
        "output": output or [],
        "affected_entity": affected or [],
    }
    c = PatchContract(
        contract_id=cid,
        atomic_change_id=acu_id,
        owner_requirement_id=rid,
        owner_design_id=rid,
        semantic_intent=intent,
        responsibility_type="other",
        patch_operation=op,
        target={
            "document": doc,
            "requirement_id": rid,
            "field": field,
            "section": f"{doc}.{field}",
            "anchor": f"{rid}:{field}",
        },
        target_section=f"{doc}.{field}",
        target_field=field,
        source_span=span,
        rationale="synthetic",
        confidence=0.8,
        provenance={
            "atomic_change_id": acu_id,
            "source_span": span,
            "evidence_ids": [f"ev_{acu_id}"],
            "owner_evidence_ids": ["own1"],
        },
        review_required=False,
        validation_status="OK",
        validation_issues=[],
    )
    return validate_patch_contract(c)


# ---------------------------------------------------------------------------
# A–V
# ---------------------------------------------------------------------------


def test_a_single_valid_update_contract():
    c = _ok_contract(op="UPDATE", action="조회", obj=["재고"], span="재고를 조회한다")
    d = generate_semantic_draft(c)
    assert d.draft_text
    assert "시스템" in d.draft_text
    assert "조회" in d.draft_text
    assert d.validation_status in ("VALID", "VALID_WITH_WARNINGS")
    assert d.activation_eligible is True
    assert "implicit_system" not in d.draft_text


def test_b_multiple_contracts_isolated_drafts():
    c1 = _ok_contract(
        cid="PC-ACU-001",
        acu_id="ACU-001",
        action="생성",
        obj=["발주", "요청"],
        span="발주 요청을 생성한다",
    )
    c2 = _ok_contract(
        cid="PC-ACU-002",
        acu_id="ACU-002",
        action="알림",
        recipient="관리자",
        obj=["발주"],
        span="관리자에게 알린다",
    )
    drafts = generate_semantic_drafts([c1, c2])
    assert len(drafts) == 2
    assert drafts[0].atomic_change_id != drafts[1].atomic_change_id
    assert "감사" not in drafts[0].draft_text
    assert "발주" not in drafts[1].draft_text or "알림" in drafts[1].draft_text


def test_c_add():
    d = generate_semantic_draft(_ok_contract(op="ADD", action="생성", obj=["보고서"]))
    assert d.draft_text
    assert d.operation == "ADD"


def test_d_update():
    d = generate_semantic_draft(_ok_contract(op="UPDATE", action="갱신", affected=["좌석"]))
    assert "좌석" in d.draft_text or "갱신" in d.draft_text


def test_e_constrain():
    d = generate_semantic_draft(
        _ok_contract(
            op="CONSTRAIN",
            action="보관",
            constraint=["3년", "기간"],
            condition="처리 완료",
            span="3년간 보관",
        )
    )
    assert d.draft_text
    assert "제약" in d.draft_text or "3년" in d.draft_text


def test_f_replace():
    d = generate_semantic_draft(_ok_contract(op="REPLACE", action="저장", obj=["데이터"]))
    assert d.draft_text
    assert d.operation == "REPLACE"


def test_g_link():
    d = generate_semantic_draft(_ok_contract(op="LINK", action="조회"))
    assert "traceability" in d.draft_text or "연결" in d.draft_text


def test_h_delete():
    d = generate_semantic_draft(_ok_contract(op="DELETE", action="삭제"))
    assert "삭제" in d.draft_text
    assert d.activation_eligible is False


def test_i_no_action():
    d = generate_semantic_draft(_ok_contract(op="NO_ACTION", action="조회"))
    assert d.draft_text == ""
    assert d.generation_mode == "NO_ACTION"


def test_j_review_required_op():
    d = generate_semantic_draft(_ok_contract(op="REVIEW_REQUIRED", action="조회"))
    assert d.draft_text == ""
    assert d.review_required is True


def test_k_missing_required_contract_field_blocks_generation():
    c = _ok_contract()
    c.validation_status = "REVIEW_REQUIRED"
    c.review_required = True
    c.validation_issues = ["incomplete_target"]
    d = generate_semantic_draft(c)
    assert d.draft_text == ""
    assert d.validation_status == "REVIEW_REQUIRED"
    assert "contract_not_valid_for_generation" in d.validation_issues


def test_l_actor_recipient_separation():
    d = generate_semantic_draft(
        _ok_contract(
            action="알림",
            recipient="관리자",
            obj=["잠금"],
            span="관리자에게 알림을 보낸다",
        )
    )
    assert "관리자에게" in d.draft_text
    assert "관리자가" not in d.draft_text
    assert "시스템" in d.draft_text


def test_m_implicit_system_rendering():
    d = generate_semantic_draft(_ok_contract(action="조회", obj=["재고"]))
    assert "시스템" in d.draft_text
    assert "implicit_system" not in d.draft_text


def test_n_or_one_of_preservation():
    d = generate_semantic_draft(
        _ok_contract(
            action="해제",
            affected=["계정"],
            constraint=["관리자 승인", "자동 해제", "또는", "중 하나"],
            span="승인 또는 자동 해제 중 하나",
        )
    )
    assert "또는" in d.draft_text


def test_o_timing_threshold_preservation():
    d = generate_semantic_draft(
        _ok_contract(
            op="CONSTRAIN",
            action="보관",
            condition="처리 완료",
            constraint=["3년"],
            span="3년간 보관한 후 삭제",
        )
    )
    assert "3년" in d.draft_text or "처리" in d.draft_text


def test_p_no_full_cr_input():
    sig = inspect.signature(generate_semantic_draft)
    # Primary API takes contract; CR kwargs only for rejection
    assert "contract" in sig.parameters
    c = _ok_contract()
    d = generate_semantic_draft(c, cr_text="전체 CR 텍스트가 들어가야 한다. 다른 문장도 있다.")
    assert d.validation_status == "INVALID"
    assert "full_cr_input_forbidden" in d.validation_issues
    assert d.draft_text == ""


def test_q_no_whole_cr_output():
    cr = (
        "재고가 최소 수량 이하이면 발주 요청을 생성하고 관리자에게 알린다. "
        "월말 보고서를 생성한다."
    )
    c = _ok_contract(action="생성", obj=["발주", "요청"], span="발주 요청을 생성한다")
    d = generate_semantic_draft(c)
    assert d.draft_text.strip() != cr.strip()
    assert "보고서" not in d.draft_text


def test_r_cross_acu_leakage_rejection():
    c_notify = _ok_contract(
        cid="PC-ACU-001",
        acu_id="ACU-001",
        action="알림",
        recipient="관리자",
        span="관리자에게 알린다",
    )
    c_audit = _ok_contract(
        cid="PC-ACU-002",
        acu_id="ACU-002",
        action="기록",
        obj=["이벤트"],
        output=["감사 기록"],
        span="이벤트를 감사 기록으로 남긴다",
    )
    drafts = generate_semantic_drafts([c_notify, c_audit])
    notify = next(d for d in drafts if d.atomic_change_id == "ACU-001")
    assert "감사" not in notify.draft_text
    assert "기록" not in notify.draft_text or "알림" in notify.draft_text


def test_s_target_terminology_reuse():
    c = _ok_contract(action="조회", obj=["재고"], span="재고를 조회한다")
    d = generate_semantic_draft(
        c, owner_target_text="재고 서비스는 창고 재고 수준을 조회한다."
    )
    assert d.provenance.get("target_context_terms") is not None
    assert "owner_target_text" in d.used_inputs


def test_t_deterministic_draft_ids_order():
    contracts = [
        _ok_contract(cid="PC-ACU-001", acu_id="ACU-001", action="생성", obj=["요청"]),
        _ok_contract(
            cid="PC-ACU-002",
            acu_id="ACU-002",
            action="알림",
            recipient="관리자",
        ),
    ]
    a = generate_semantic_drafts(contracts)
    b = generate_semantic_drafts(contracts)
    assert [d.draft_id for d in a] == [d.draft_id for d in b]
    assert a[0].draft_id == "SD-PC-ACU-001"


def test_u_legacy_docx_unchanged_contract():
    cr = "시스템은 창고 재고 수준을 조회한다."
    mdsr = _block("Req. Inv", "재고 조회", "창고 재고 수준을 조회한다.")
    mddr = _block("Req. Inv", "재고 조회", "재고 서비스가 창고 재고 수준을 조회한다.", "MDDR")
    decision = _consistent("Req. Inv")
    traces = build_propagation_plan(
        cr, [decision], [mdsr, mddr], owner_selection_mode="legacy"
    )
    before = [(t.propagation_decision, t.allow_mdsr_patch) for t in traces]
    legacy = proposed_mdsr_description(decision, cr)
    acus = decompose_change_request(cr)
    plans = build_shadow_patch_plans(cr_text=cr, acus=acus, traces=traces)
    contracts = build_patch_contracts(acus=acus, plans=plans, traces=traces)
    _drafts = generate_semantic_drafts(contracts)
    after = [(t.propagation_decision, t.allow_mdsr_patch) for t in traces]
    assert before == after
    assert proposed_mdsr_description(decision, cr) == legacy
    summary = semantic_generation_summary(contracts=contracts, drafts=_drafts)
    assert summary["actual_generation_changed"] is False
    assert summary["docx_changed"] is False


def test_v_multi_domain_inventory_reservation_reporting_retention():
    cases = [
        (
            "재고가 최소 수량 이하이면 발주 요청을 생성하고 관리자에게 알린다.",
            ["생성", "알림"],
        ),
        (
            "예약 취소 시 좌석을 사용 가능 상태로 바꾸고 대기자에게 알린다.",
            ["갱신", "알림"],
        ),
        (
            "월말 보고서를 생성하고 관리자 화면에서 다운로드할 수 있게 한다.",
            ["생성", "다운로드"],
        ),
        (
            "처리 완료된 요청 기록은 3년간 보관한 후 삭제한다.",
            ["보관", "삭제"],
        ),
    ]
    for cr, expected_actions in cases:
        acus = decompose_change_request(cr)
        # Build synthetic OK contracts from ACU facets (no Req hard-code)
        contracts = []
        for i, acu in enumerate(acus):
            action = (acu.action or ["반영"])[0]
            c = _ok_contract(
                cid=f"PC-{acu.change_id}",
                acu_id=acu.change_id,
                action=action,
                recipient=(acu.recipient[0] if acu.recipient else None),
                obj=list(acu.object or []),
                affected=list(acu.affected_entity or []),
                condition=(acu.condition[0] if acu.condition else None),
                constraint=list(acu.constraint or []),
                output=list(acu.output or []),
                span=acu.source_span,
                rid=f"Req. Syn{i}",
            )
            contracts.append(c)
        drafts = generate_semantic_drafts(contracts)
        assert len(drafts) == len(contracts)
        texts = " ".join(d.draft_text for d in drafts)
        # At least one expected action family appears across drafts
        assert any(a in texts for a in expected_actions)
        assert cr not in texts


def test_account_lock_fixture_shadow_semantics():
    cr = (
        "연속 로그인 실패 시 계정을 잠그고 관리자에게 알림을 보내도록 정책을 강화한다. "
        "잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다. "
        "사용자에게는 잠금 상태와 재시도 가능 시점을 안내해야 하며, "
        "로그인 실패·계정 잠금·잠금 해제 이벤트는 감사 기록으로 남겨야 한다."
    )
    acus = decompose_change_request(cr)
    assert len(acus) >= 4
    contracts = []
    for acu in acus:
        action = (acu.action or [None])[0] or "반영"
        c = _ok_contract(
            cid=f"PC-{acu.change_id}",
            acu_id=acu.change_id,
            action=action,
            recipient=(acu.recipient[0] if acu.recipient else None),
            obj=list(acu.object or []),
            affected=list(acu.affected_entity or []),
            condition=(acu.condition[0] if acu.condition else None),
            constraint=list(acu.constraint or []),
            output=list(acu.output or []),
            span=acu.source_span,
            rid="Req. Syn",
        )
        contracts.append(c)
    drafts = generate_semantic_drafts(contracts)
    by_acu = {d.atomic_change_id: d for d in drafts}
    # Isolated drafts; no whole CR
    for d in drafts:
        assert d.draft_text != cr
        if d.draft_text and d.generation_mode not in ("NO_ACTION", "REVIEW_REQUIRED"):
            assert "정책" not in d.draft_text or "강화" not in d.semantic_intent.get("action", "")
    # Recipient roles
    for acu in acus:
        d = by_acu[acu.change_id]
        if "관리자" in (acu.recipient or []) and d.draft_text:
            assert "관리자에게" in d.draft_text
            assert "관리자가" not in d.draft_text
        if "사용자" in (acu.recipient or []) and d.draft_text:
            assert "사용자에게" in d.draft_text
    # Audit draft should not be the only place for notify concepts mixed wrongly
    audit_drafts = [
        d
        for acu, d in by_acu.items()
        if any(a in (next(x for x in acus if x.change_id == acu).action or []) for a in ("기록", "감사"))
    ]
    notify_drafts = [
        d
        for acu in acus
        if "알림" in (acu.action or [])
        for d in [by_acu[acu.change_id]]
    ]
    for nd in notify_drafts:
        if nd.draft_text:
            assert "감사" not in nd.draft_text


def test_comparison_and_summary_artifacts():
    c = _ok_contract(action="조회", obj=["재고"])
    drafts = generate_semantic_drafts([c])
    cmp = compare_legacy_vs_semantic_drafts(
        legacy_generation_texts=["변경 요청 반영: 전체 CR"],
        drafts=drafts,
        whole_cr="전체 CR",
    )
    assert cmp["whole_cr_used_by_legacy"] is True
    assert cmp["whole_cr_used_by_shadow"] is False
    assert cmp["actual_generation_changed"] is False
    val = validate_semantic_drafts(drafts)
    assert val["total"] == 1
