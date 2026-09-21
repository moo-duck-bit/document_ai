# -*- coding: utf-8 -*-
"""PR-12: Shadow Activation Policy for Requirement Patches.

Decides AUTO_APPLY / REVIEW / BLOCK per RequirementPatch.
Does NOT apply patches to DOCX. Does NOT change legacy generation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.patch_contract import normalize_patch_operation
from document_ai.impact.requirement_patch import RequirementPatch

ActivationDecision = Literal["AUTO_APPLY", "REVIEW", "BLOCK"]


@dataclass
class RequirementActivationDecision:
    patch_id: str
    requirement_id: str | None
    decision: ActivationDecision | str
    reasons: list[str] = field(default_factory=list)
    validation_status: str = ""
    scope_preserved: bool = False
    activation_eligible: bool = False
    review_required: bool = True
    operation: str = ""
    draft_id: str = ""
    atomic_change_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _draft_activation_eligible(patch: RequirementPatch) -> bool:
    prov = patch.provenance or {}
    if "activation_eligible" in prov:
        return bool(prov.get("activation_eligible"))
    return patch.validation_status in ("VALID", "VALID_WITH_WARNINGS", "NO_ACTION")


def _has_duplicate_signal(issues: list[str]) -> bool:
    return any("duplicate" in (i or "").lower() for i in issues)


def _has_scope_violation(patch: RequirementPatch) -> bool:
    issues = " ".join(patch.validation_issues or []).lower()
    if "unrelated_clause_lost" in issues or "unchanged_span_missing" in issues:
        return True
    if not patch.scope_preserved and patch.validation_status == "INVALID":
        return True
    return False


def _has_semantic_mismatch(issues: list[str]) -> bool:
    blob = " ".join(issues or []).lower()
    return "semantic_intent_not_in_patched" in blob or "semantic_mismatch" in blob


def decide_requirement_activation(
    patch: RequirementPatch,
    *,
    confidence: float | None = None,
    multiple_candidates: bool = False,
) -> RequirementActivationDecision:
    """Determine AUTO_APPLY / REVIEW / BLOCK for one shadow requirement patch."""
    op = normalize_patch_operation(str(patch.operation))
    status = str(patch.validation_status or "")
    issues = list(patch.validation_issues or [])
    eligible = _draft_activation_eligible(patch)

    def _out(
        decision: ActivationDecision,
        reasons: list[str],
        *,
        review_required: bool,
        activation_eligible: bool,
    ) -> RequirementActivationDecision:
        return RequirementActivationDecision(
            patch_id=patch.patch_id,
            requirement_id=patch.requirement_id,
            decision=decision,
            reasons=reasons,
            validation_status=status,
            scope_preserved=bool(patch.scope_preserved),
            activation_eligible=activation_eligible,
            review_required=review_required,
            operation=op,
            draft_id=patch.draft_id,
            atomic_change_id=patch.atomic_change_id,
        )

    # ---------- BLOCK ----------
    block_reasons: list[str] = []
    if status == "INVALID":
        block_reasons.append("validation_invalid")
    if _has_scope_violation(patch):
        block_reasons.append("scope_violation")
    if _has_semantic_mismatch(issues):
        block_reasons.append("semantic_mismatch")
    if not patch.requirement_id and op in (
        "ADD",
        "UPDATE",
        "CONSTRAIN",
        "DELETE",
        "REPLACE",
    ):
        block_reasons.append("target_missing")
    if eligible is False and status in ("INVALID",) or (
        eligible is False
        and any("draft_not_eligible" in (i or "").lower() for i in issues)
    ):
        block_reasons.append("activation_eligible_false")
    if eligible is False and status == "INVALID":
        if "activation_eligible_false" not in block_reasons:
            block_reasons.append("activation_eligible_false")

    if block_reasons:
        # Deduplicate while preserving order
        block_reasons = list(dict.fromkeys(block_reasons))
        return _out(
            "BLOCK",
            block_reasons,
            review_required=True,
            activation_eligible=False,
        )

    # ---------- REVIEW ----------
    review_reasons: list[str] = []
    if status == "VALID_WITH_WARNINGS":
        review_reasons.append("validation_warnings")
    if status == "REVIEW_REQUIRED" or op == "REVIEW_REQUIRED":
        review_reasons.append("operation_or_status_review_required")
    if patch.review_required and status != "VALID":
        review_reasons.append("patch_review_required_flag")
    if _has_duplicate_signal(issues):
        review_reasons.append("duplicate_responsibility")
    if multiple_candidates:
        review_reasons.append("multiple_candidates")
    if confidence is not None and confidence < 0.5:
        review_reasons.append("confidence_insufficient")
    if status == "NO_ACTION":
        review_reasons.append("no_action_operation")
    if any((i or "").startswith("warn:") for i in issues):
        review_reasons.append("validation_warnings")
    if not patch.scope_preserved and op not in ("REPLACE", "NO_ACTION", "LINK"):
        review_reasons.append("scope_not_confirmed")
    if eligible is False and status == "REVIEW_REQUIRED":
        review_reasons.append("activation_eligible_false_review")

    if review_reasons:
        review_reasons = list(dict.fromkeys(review_reasons))
        return _out(
            "REVIEW",
            review_reasons,
            review_required=True,
            activation_eligible=status in ("VALID", "VALID_WITH_WARNINGS", "NO_ACTION"),
        )

    # ---------- AUTO_APPLY ----------
    if (
        status == "VALID"
        and patch.scope_preserved
        and not patch.review_required
        and eligible
        and not _has_duplicate_signal(issues)
    ):
        return _out(
            "AUTO_APPLY",
            ["validation_valid", "scope_preserved", "no_review_flags"],
            review_required=False,
            activation_eligible=True,
        )

    # Safe default
    return _out(
        "REVIEW",
        ["default_safe_review"],
        review_required=True,
        activation_eligible=eligible,
    )


def decide_requirement_activations(
    patches: list[RequirementPatch],
    *,
    confidence_by_patch_id: dict[str, float] | None = None,
    multiple_candidate_patch_ids: set[str] | None = None,
) -> list[RequirementActivationDecision]:
    confidence_by_patch_id = confidence_by_patch_id or {}
    multiple_candidate_patch_ids = multiple_candidate_patch_ids or set()
    return [
        decide_requirement_activation(
            p,
            confidence=confidence_by_patch_id.get(p.patch_id),
            multiple_candidates=p.patch_id in multiple_candidate_patch_ids,
        )
        for p in patches
    ]


def build_activation_summary(
    decisions: list[RequirementActivationDecision],
) -> dict[str, Any]:
    by_decision = Counter(d.decision for d in decisions)
    by_op = Counter(d.operation for d in decisions)
    by_val = Counter(d.validation_status for d in decisions)
    auto = [d for d in decisions if d.decision == "AUTO_APPLY"]
    return {
        "stage": "activation_summary",
        "auto_apply_count": by_decision.get("AUTO_APPLY", 0),
        "review_count": by_decision.get("REVIEW", 0),
        "block_count": by_decision.get("BLOCK", 0),
        "total": len(decisions),
        "by_operation": dict(sorted(by_op.items())),
        "by_validation": dict(sorted(by_val.items())),
        "invariants": {
            "auto_apply_all_valid": all(d.validation_status == "VALID" for d in auto),
            "block_never_auto_apply": True,
            "review_human_reviewable": all(
                d.review_required for d in decisions if d.decision == "REVIEW"
            ),
        },
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": (
            "PR-12 activation policy is shadow-only. "
            "AUTO_APPLY does not write DOCX in this PR."
        ),
    }


def compare_legacy_vs_activation(
    *,
    decisions: list[RequirementActivationDecision],
    legacy_generation_texts: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "stage": "legacy_vs_activation",
        "legacy_generation_texts": list(legacy_generation_texts or []),
        "activation_decisions": [d.to_dict() for d in decisions],
        "auto_apply_count": sum(1 for d in decisions if d.decision == "AUTO_APPLY"),
        "review_count": sum(1 for d in decisions if d.decision == "REVIEW"),
        "block_count": sum(1 for d in decisions if d.decision == "BLOCK"),
        "docx_would_change_if_activated": False,
        "actual_docx_changed": False,
        "note": (
            "Shadow activation decisions vs legacy whole-CR path. "
            "Legacy DOCX remains the actual output."
        ),
    }


def validate_activation_decisions(
    decisions: list[RequirementActivationDecision],
) -> dict[str, Any]:
    issues: list[str] = []
    for d in decisions:
        if d.decision == "AUTO_APPLY" and d.validation_status != "VALID":
            issues.append(f"{d.patch_id}:auto_apply_not_valid")
        if d.decision == "AUTO_APPLY" and d.review_required:
            issues.append(f"{d.patch_id}:auto_apply_review_required")
        if d.decision == "REVIEW" and not d.review_required:
            issues.append(f"{d.patch_id}:review_not_flagged")
        if d.decision == "BLOCK" and d.activation_eligible:
            # BLOCK must not be treated as eligible to apply
            issues.append(f"{d.patch_id}:block_marked_eligible")
    return {
        "stage": "activation_policy_validation",
        "ok": not issues,
        "issues": issues,
        "note": "Shadow policy validation only.",
    }


def activation_decisions_to_trace_payload(
    decisions: list[RequirementActivationDecision],
) -> dict[str, Any]:
    return {
        "stage": "requirement_activation_decisions",
        "schema_version": "activation_policy_v1",
        "decision_count": len(decisions),
        "decisions": [d.to_dict() for d in decisions],
        "note": (
            "PR-12 shadow activation policy. "
            "Does not modify DOCX or legacy generation."
        ),
    }
