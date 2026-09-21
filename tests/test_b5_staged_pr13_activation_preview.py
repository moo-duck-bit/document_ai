# -*- coding: utf-8 -*-
"""PR-13: Shadow activation preview builder."""

from __future__ import annotations

from document_ai.impact.activation_policy import RequirementActivationDecision
from document_ai.impact.activation_preview import (
    build_activation_preview,
    build_activation_preview_entries,
    build_aggregated_requirement_previews,
)
from document_ai.impact.requirement_patch import RequirementPatch


def _patch(
    *,
    patch_id: str,
    acu: str = "ACU-001",
    rid: str = "Req. Inv",
    original: str = "원문 A.\n원문 B.",
    patched: str | None = None,
    draft: str = "시스템은 재고를 조회해야 한다.",
    op: str = "ADD",
    status: str = "VALID",
    scope: bool = True,
) -> RequirementPatch:
    return RequirementPatch(
        patch_id=patch_id,
        draft_id=f"SD-{patch_id}",
        contract_id=f"PC-{acu}",
        atomic_change_id=acu,
        requirement_id=rid,
        document="MDSR",
        field="description",
        operation=op,
        original_requirement=original,
        semantic_draft=draft,
        patched_requirement=patched if patched is not None else (original + "\n" + draft).strip(),
        changed_spans=[f"+ {draft}"],
        unchanged_spans=["원문 A.", "원문 B."],
        validation_status=status,
        validation_issues=[],
        review_required=False,
        scope_preserved=scope,
        provenance={"activation_eligible": True},
    )


def _dec(
    patch_id: str,
    decision: str,
    *,
    rid: str = "Req. Inv",
    status: str = "VALID",
    reasons: list[str] | None = None,
) -> RequirementActivationDecision:
    return RequirementActivationDecision(
        patch_id=patch_id,
        requirement_id=rid,
        decision=decision,
        reasons=reasons or [decision.lower()],
        validation_status=status,
        scope_preserved=True,
        activation_eligible=decision == "AUTO_APPLY",
        review_required=decision != "AUTO_APPLY",
        operation="ADD",
        draft_id=f"SD-{patch_id}",
        atomic_change_id="ACU-001",
    )


ORIGINAL = "시스템은 창고 재고를 조회해야 한다.\n시스템은 이력을 기록해야 한다."


def test_1_auto_apply_reflected_in_preview():
    p = _patch(
        patch_id="RP-1",
        original=ORIGINAL,
        patched=ORIGINAL + "\n시스템은 관리자에게 알림을 제공해야 한다.",
        draft="시스템은 관리자에게 알림을 제공해야 한다.",
    )
    d = _dec("RP-1", "AUTO_APPLY")
    entries, _, _ = build_activation_preview_entries([p], [d])
    assert entries[0].applied_in_preview is True
    assert entries[0].preview_requirement == p.patched_requirement
    assert "알림" in entries[0].preview_requirement


def test_2_review_keeps_original():
    p = _patch(patch_id="RP-2", original=ORIGINAL)
    d = _dec("RP-2", "REVIEW", status="VALID_WITH_WARNINGS", reasons=["validation_warnings"])
    entries, review_q, _ = build_activation_preview_entries([p], [d])
    assert entries[0].applied_in_preview is False
    assert entries[0].preview_requirement == ORIGINAL
    assert review_q and review_q[0]["patch_id"] == "RP-2"


def test_3_block_keeps_original():
    p = _patch(patch_id="RP-3", original=ORIGINAL, status="INVALID", scope=False)
    d = _dec("RP-3", "BLOCK", status="INVALID", reasons=["validation_invalid"])
    entries, _, blocked_q = build_activation_preview_entries([p], [d])
    assert entries[0].applied_in_preview is False
    assert entries[0].preview_requirement == ORIGINAL
    assert blocked_q and blocked_q[0]["patch_id"] == "RP-3"


def test_4_missing_decision_not_auto_applied():
    p = _patch(patch_id="RP-4", original=ORIGINAL)
    entries, review_q, _ = build_activation_preview_entries([p], [])
    assert entries[0].activation_decision == "REVIEW"
    assert entries[0].applied_in_preview is False
    assert "missing_activation_decision" in entries[0].reasons
    assert review_q


def test_5_patch_id_mismatch_blocked():
    p = _patch(patch_id="RP-5", original=ORIGINAL)
    orphan = _dec("RP-ORPHAN", "AUTO_APPLY")
    payload = build_activation_preview(patches=[p], decisions=[orphan])
    # patch itself missing decision → REVIEW
    assert payload["entries"][0]["applied_in_preview"] is False
    assert any(b["patch_id"] == "RP-ORPHAN" for b in payload["blocked_queue"])


def test_6_only_auto_apply_has_applied_true():
    patches = [
        _patch(patch_id="RP-A", original=ORIGINAL),
        _patch(patch_id="RP-B", original=ORIGINAL),
        _patch(patch_id="RP-C", original=ORIGINAL),
    ]
    decisions = [
        _dec("RP-A", "AUTO_APPLY"),
        _dec("RP-B", "REVIEW"),
        _dec("RP-C", "BLOCK", status="INVALID"),
    ]
    entries, _, _ = build_activation_preview_entries(patches, decisions)
    applied = [e for e in entries if e.applied_in_preview]
    assert len(applied) == 1
    assert applied[0].activation_decision == "AUTO_APPLY"


def test_7_multi_patch_deterministic_order():
    original = "베이스 요구사항이다."
    p1 = _patch(
        patch_id="RP-Z",
        acu="ACU-002",
        original=original,
        draft="시스템은 B를 생성해야 한다.",
        patched=original + "\n시스템은 B를 생성해야 한다.",
    )
    p2 = _patch(
        patch_id="RP-A",
        acu="ACU-001",
        original=original,
        draft="시스템은 A를 생성해야 한다.",
        patched=original + "\n시스템은 A를 생성해야 한다.",
    )
    decisions = [_dec("RP-Z", "AUTO_APPLY"), _dec("RP-A", "AUTO_APPLY")]
    agg = build_aggregated_requirement_previews([p1, p2], decisions)
    assert len(agg) == 1
    # Order by atomic_change_id then patch_id → ACU-001 before ACU-002
    assert agg[0].applied_patch_ids == ["RP-A", "RP-Z"] or agg[0].conflict_detected


def test_8_multi_patch_merge_success():
    original = "시스템은 기본 상태를 유지해야 한다."
    p1 = _patch(
        patch_id="RP-1",
        acu="ACU-001",
        original=original,
        draft="시스템은 발주 요청을 생성해야 한다.",
        patched=original + "\n시스템은 발주 요청을 생성해야 한다.",
        op="ADD",
    )
    p2 = _patch(
        patch_id="RP-2",
        acu="ACU-002",
        original=original,
        draft="시스템은 관리자에게 알림을 제공해야 한다.",
        patched=original + "\n시스템은 관리자에게 알림을 제공해야 한다.",
        op="ADD",
    )
    decisions = [_dec("RP-1", "AUTO_APPLY"), _dec("RP-2", "AUTO_APPLY")]
    agg = build_aggregated_requirement_previews([p1, p2], decisions)[0]
    assert agg.conflict_detected is False
    assert "발주" in agg.final_preview_requirement
    assert "알림" in agg.final_preview_requirement
    assert set(agg.applied_patch_ids) == {"RP-1", "RP-2"}


def test_9_multi_patch_conflict_review():
    # Inconsistent originals → conflict, keep original
    p1 = _patch(
        patch_id="RP-1",
        acu="ACU-001",
        original="원문 버전1.",
        draft="A",
        patched="원문 버전1.\nA",
    )
    p2 = _patch(
        patch_id="RP-2",
        acu="ACU-002",
        original="원문 버전2.",
        draft="B",
        patched="원문 버전2.\nB",
    )
    decisions = [_dec("RP-1", "AUTO_APPLY"), _dec("RP-2", "AUTO_APPLY")]
    payload = build_activation_preview(patches=[p1, p2], decisions=decisions)
    agg = payload["aggregated_requirement_previews"][0]
    assert agg["conflict_detected"] is True
    assert agg["final_preview_requirement"] in ("원문 버전1.", "원문 버전2.")
    assert payload["validation"]["conflict_count"] >= 1


def test_10_11_review_and_blocked_queues():
    patches = [
        _patch(patch_id="RP-R", original=ORIGINAL),
        _patch(patch_id="RP-B", original=ORIGINAL, status="INVALID"),
    ]
    decisions = [
        _dec("RP-R", "REVIEW"),
        _dec("RP-B", "BLOCK", status="INVALID"),
    ]
    _, review_q, blocked_q = build_activation_preview_entries(patches, decisions)
    assert any(r["patch_id"] == "RP-R" for r in review_q)
    assert any(b["patch_id"] == "RP-B" for b in blocked_q)


def test_12_13_docx_and_legacy_flags_unchanged():
    p = _patch(patch_id="RP-1", original=ORIGINAL)
    d = _dec("RP-1", "AUTO_APPLY")
    payload = build_activation_preview(
        patches=[p],
        decisions=[d],
        legacy_generation_texts=["변경 요청 반영: whole CR"],
    )
    assert payload["summary"]["actual_docx_changed"] is False
    assert payload["summary"]["actual_generation_changed"] is False
    assert payload["preview_vs_legacy"]["actual_docx_changed"] is False
    assert payload["validation"]["invariants"]["actual_docx_unchanged"] is True


def test_14_only_auto_apply_invariant_in_validation():
    patches = [
        _patch(patch_id="RP-1", original=ORIGINAL),
        _patch(patch_id="RP-2", original=ORIGINAL),
    ]
    decisions = [_dec("RP-1", "AUTO_APPLY"), _dec("RP-2", "REVIEW")]
    payload = build_activation_preview(patches=patches, decisions=decisions)
    assert payload["validation"]["invariants"]["only_auto_apply_applied"] is True
    assert payload["summary"]["applied_in_preview_count"] == 1
