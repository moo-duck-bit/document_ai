# -*- coding: utf-8 -*-
"""PR-12: Shadow activation policy for requirement patches."""

from __future__ import annotations

from document_ai.impact.activation_policy import (
    build_activation_summary,
    decide_requirement_activation,
    decide_requirement_activations,
    validate_activation_decisions,
)
from document_ai.impact.requirement_patch import RequirementPatch


def _patch(
    *,
    patch_id: str = "RP-SD-1",
    rid: str | None = "Req. Inv",
    status: str = "VALID",
    scope: bool = True,
    review: bool = False,
    op: str = "UPDATE",
    issues: list[str] | None = None,
    eligible: bool = True,
    original: str = "원문 A.\n원문 B.",
    patched: str | None = None,
) -> RequirementPatch:
    return RequirementPatch(
        patch_id=patch_id,
        draft_id="SD-1",
        contract_id="PC-1",
        atomic_change_id="ACU-001",
        requirement_id=rid,
        document="MDSR",
        field="description",
        operation=op,
        original_requirement=original,
        semantic_draft="시스템은 재고를 조회해야 한다.",
        patched_requirement=patched if patched is not None else original,
        changed_spans=[],
        unchanged_spans=["원문 B."] if scope else [],
        validation_status=status,
        validation_issues=list(issues or []),
        review_required=review,
        scope_preserved=scope,
        provenance={"activation_eligible": eligible},
    )


def test_valid_auto_apply():
    d = decide_requirement_activation(_patch(status="VALID", scope=True, review=False))
    assert d.decision == "AUTO_APPLY"
    assert d.review_required is False
    assert d.activation_eligible is True


def test_review_required_to_review():
    d = decide_requirement_activation(
        _patch(status="REVIEW_REQUIRED", review=True, op="REVIEW_REQUIRED", eligible=False)
    )
    assert d.decision == "REVIEW"
    assert d.review_required is True


def test_invalid_to_block():
    d = decide_requirement_activation(
        _patch(
            status="INVALID",
            scope=False,
            review=True,
            eligible=False,
            issues=["unrelated_clause_lost"],
        )
    )
    assert d.decision == "BLOCK"
    assert d.activation_eligible is False


def test_scope_violation_to_block():
    d = decide_requirement_activation(
        _patch(
            status="INVALID",
            scope=False,
            issues=["unchanged_span_missing_in_patched"],
            eligible=False,
        )
    )
    assert d.decision == "BLOCK"
    assert "scope_violation" in d.reasons or "validation_invalid" in d.reasons


def test_duplicate_to_review():
    d = decide_requirement_activation(
        _patch(
            status="VALID_WITH_WARNINGS",
            scope=True,
            review=False,
            issues=["duplicate_responsibility_skipped"],
        )
    )
    assert d.decision == "REVIEW"
    assert any("duplicate" in r for r in d.reasons) or "validation_warnings" in d.reasons


def test_missing_target_block():
    d = decide_requirement_activation(
        _patch(rid=None, status="VALID", scope=True, op="UPDATE")
    )
    assert d.decision == "BLOCK"
    assert "target_missing" in d.reasons


def test_auto_apply_invariant_and_summary():
    patches = [
        _patch(patch_id="RP-1", status="VALID", scope=True, review=False),
        _patch(
            patch_id="RP-2",
            status="VALID_WITH_WARNINGS",
            issues=["warn:x"],
        ),
        _patch(
            patch_id="RP-3",
            status="INVALID",
            scope=False,
            eligible=False,
            issues=["semantic_intent_not_in_patched"],
        ),
    ]
    decisions = decide_requirement_activations(patches)
    assert decisions[0].decision == "AUTO_APPLY"
    assert decisions[1].decision == "REVIEW"
    assert decisions[2].decision == "BLOCK"
    summary = build_activation_summary(decisions)
    assert summary["auto_apply_count"] == 1
    assert summary["review_count"] == 1
    assert summary["block_count"] == 1
    assert summary["actual_docx_changed"] is False
    assert summary["invariants"]["auto_apply_all_valid"] is True
    policy = validate_activation_decisions(decisions)
    assert policy["ok"] is True


def test_activation_eligible_false_blocks_when_invalid():
    d = decide_requirement_activation(
        _patch(
            status="INVALID",
            eligible=False,
            issues=["draft_not_eligible_for_patch"],
        )
    )
    assert d.decision == "BLOCK"
