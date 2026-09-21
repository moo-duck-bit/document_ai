# -*- coding: utf-8 -*-
"""PR-11: Shadow requirement-level patch application."""

from __future__ import annotations

from document_ai.impact.requirement_patch import (
    apply_requirement_patch,
    apply_requirement_patches,
    compare_legacy_vs_requirement_patches,
    validate_requirement_patch,
    validate_requirement_patches,
)
from document_ai.impact.semantic_draft import SemanticDraft


def _draft(
    *,
    draft_id: str = "SD-PC-ACU-001",
    contract_id: str = "PC-ACU-001",
    acu_id: str = "ACU-001",
    op: str = "UPDATE",
    text: str = "시스템은 재고를 조회해야 한다.",
    rid: str = "Req. Inv",
    field: str = "description",
    doc: str = "MDSR",
    status: str = "VALID",
    intent: dict | None = None,
) -> SemanticDraft:
    return SemanticDraft(
        draft_id=draft_id,
        contract_id=contract_id,
        atomic_change_id=acu_id,
        target={
            "document": doc,
            "requirement_id": rid,
            "field": field,
            "section": f"{doc}.{field}",
            "anchor": f"{rid}:{field}",
        },
        operation=op,
        draft_text=text,
        generation_mode="RULE_BASED_SHADOW",
        used_inputs=["patch_contract"],
        omitted_inputs=["full_change_request"],
        source_span=text,
        provenance={},
        validation_status=status,
        validation_issues=[],
        review_required=False,
        activation_eligible=status in ("VALID", "VALID_WITH_WARNINGS"),
        semantic_intent=intent
        or {
            "actor": "implicit_system",
            "action": "조회",
            "object": ["재고"],
            "recipient": None,
            "condition": None,
            "constraint": [],
            "output": [],
            "affected_entity": [],
        },
    )


ORIGINAL = (
    "시스템은 창고 재고 수준을 조회해야 한다.\n"
    "시스템은 재고 변동을 기록해야 한다."
)


def test_single_responsibility_update():
    d = _draft(
        text="시스템은 창고 재고 수준을 실시간으로 조회해야 한다.",
        intent={"action": "조회", "object": ["재고"], "actor": "implicit_system"},
    )
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert "실시간으로 조회" in p.patched_requirement
    assert "재고 변동을 기록" in p.patched_requirement  # unrelated preserved
    assert p.scope_preserved is True
    assert p.validation_status in ("VALID", "VALID_WITH_WARNINGS")


def test_multiple_independent_patches():
    d1 = _draft(
        draft_id="SD-1",
        contract_id="PC-1",
        acu_id="ACU-001",
        text="시스템은 발주 요청을 생성해야 한다.",
        op="ADD",
        intent={"action": "생성", "object": ["발주", "요청"]},
    )
    d2 = _draft(
        draft_id="SD-2",
        contract_id="PC-2",
        acu_id="ACU-002",
        text="시스템은 관리자에게 알림을 제공해야 한다.",
        op="ADD",
        intent={"action": "알림", "recipient": "관리자"},
    )
    patches = apply_requirement_patches(
        drafts=[d1, d2],
        requirement_texts={"Req. Inv": ORIGINAL},
    )
    assert len(patches) == 2
    assert patches[0].atomic_change_id != patches[1].atomic_change_id


def test_add():
    d = _draft(op="ADD", text="시스템은 관리자에게 알림을 제공해야 한다.")
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert "알림" in p.patched_requirement
    assert "창고 재고" in p.patched_requirement
    assert any(s.startswith("+ ") for s in p.changed_spans)


def test_update():
    d = _draft(
        op="UPDATE",
        text="시스템은 창고 재고 수준을 주기적으로 조회해야 한다.",
    )
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert "주기적으로 조회" in p.patched_requirement
    assert "기록해야" in p.patched_requirement


def test_constrain():
    d = _draft(
        op="CONSTRAIN",
        text="다음 제약을 적용해야 한다: 최소 수량 이하.",
        intent={"action": "조회", "constraint": ["최소 수량 이하"], "condition": None},
    )
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert "최소 수량" in p.patched_requirement or "제약" in p.patched_requirement
    assert "기록해야" in p.patched_requirement


def test_delete():
    d = _draft(
        op="DELETE",
        text="삭제 의도: Req. Inv.description",
        intent={"action": "기록", "object": ["재고", "변동"]},
    )
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert "기록해야" not in p.patched_requirement
    assert "조회해야" in p.patched_requirement
    assert any(s.startswith("- ") for s in p.changed_spans)


def test_link_does_not_rewrite_prose():
    d = _draft(
        op="LINK",
        text="MDSR Req. Inv의 description 필드에 대해 ACU ACU-001 traceability 연결을 유지해야 한다.",
    )
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert p.patched_requirement == ORIGINAL
    assert p.changed_spans
    assert "LINK:" in p.changed_spans[0]


def test_replace():
    d = _draft(op="REPLACE", text="시스템은 재고 API를 제공해야 한다.")
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert p.patched_requirement == "시스템은 재고 API를 제공해야 한다."
    assert "기록해야" not in p.patched_requirement


def test_scope_preservation():
    d = _draft(
        op="UPDATE",
        text="시스템은 창고 재고 수준을 안전하게 조회해야 한다.",
    )
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert any("기록" in u for u in p.unchanged_spans)
    assert p.scope_preserved is True


def test_duplicate_prevention():
    dup = "시스템은 창고 재고 수준을 조회해야 한다."
    d = _draft(op="ADD", text=dup)
    p = apply_requirement_patch(original_requirement=ORIGINAL, draft=d)
    assert p.patched_requirement == ORIGINAL
    assert "duplicate_responsibility_skipped" in p.validation_issues


def test_no_action_and_review():
    d1 = _draft(op="NO_ACTION", text="")
    p1 = apply_requirement_patch(original_requirement=ORIGINAL, draft=d1)
    assert p1.patched_requirement == ORIGINAL
    assert p1.validation_status == "NO_ACTION"

    d2 = _draft(op="UPDATE", text="x", status="REVIEW_REQUIRED")
    d2.review_required = True
    d2.activation_eligible = False
    p2 = apply_requirement_patch(original_requirement=ORIGINAL, draft=d2)
    assert p2.validation_status == "REVIEW_REQUIRED"
    assert p2.patched_requirement == ORIGINAL


def test_validation_and_comparison_artifacts():
    d = _draft(op="ADD", text="시스템은 보고서를 생성해야 한다.")
    patches = apply_requirement_patches(
        drafts=[d], requirement_texts={"Req. Inv": ORIGINAL}
    )
    report = validate_requirement_patches(patches)
    assert report["total"] == 1
    cmp = compare_legacy_vs_requirement_patches(
        patches=patches, legacy_generation_texts=["변경 요청 반영: whole CR"]
    )
    assert cmp["actual_docx_changed"] is False
    assert cmp["actual_generation_changed"] is False
