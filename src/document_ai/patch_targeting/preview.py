# -*- coding: utf-8 -*-
"""PR-22: Observational activation preview (never writes)."""

from __future__ import annotations

from document_ai.patch_targeting.schema import (
    ActivationPreview,
    PatchIntent,
    PatchTargetCandidate,
)


def build_activation_preview(
    intent: PatchIntent,
    target: PatchTargetCandidate,
    *,
    seq: int,
    allowed_operations: list[str] | None = None,
) -> ActivationPreview:
    blocking: list[str] = []
    would_modify = False
    would_review = False
    blocked = True

    if intent.intent_status == "INVALID" or target.target_status == "INVALID":
        preview_status = "PREVIEW_INVALID"
        if "SEMANTIC_INVALID" in intent.reason_codes:
            blocking.append("SEMANTIC_INVALID")
        else:
            blocking.append("SEMANTIC_INVALID")
    elif intent.intent_status == "REVIEW_REQUIRED" or target.target_status == "REVIEW":
        preview_status = "PREVIEW_REVIEW"
        would_review = True
        if "SEMANTIC_REVIEW_REQUIRED" in intent.reason_codes:
            blocking.append("SEMANTIC_REVIEW_REQUIRED")
        if "AMBIGUOUS_MATCH" in intent.reason_codes:
            blocking.append("AMBIGUOUS_MATCH")
        if "DELETE_REQUIRES_REVIEW" in intent.reason_codes:
            blocking.append("DELETE_REQUIRES_REVIEW")
        if "LOW_SCORE_MARGIN" in intent.reason_codes:
            blocking.append("LOW_SCORE_MARGIN")
    elif intent.intent_status == "BLOCKED" or target.target_status == "UNRESOLVED":
        preview_status = "PREVIEW_BLOCKED"
        for code in (
            "SEMANTIC_UNMAPPED",
            "PROPOSED_TEXT_MISSING",
            "OPERATION_TEMPLATE_NOT_ALLOWED",
            "LINK_METADATA_MISSING",
            "ADD_PARENT_TARGET_MISSING",
            "TEMPLATE_NODE_MISSING",
        ):
            if code in intent.reason_codes and code not in blocking:
                blocking.append(code)
    else:
        # ELIGIBLE + RESOLVED
        would_modify = True
        if not target.writer_supported:
            preview_status = "PREVIEW_BLOCKED"
            blocking.append("OPERATION_WRITER_NOT_SUPPORTED")
        else:
            # Feature flag OFF → PREVIEW_BLOCKED (safe default for PR-22)
            preview_status = "PREVIEW_BLOCKED"
            blocking.append("ACTIVATION_DISABLED")

    if not target.activation_allowed and "ACTIVATION_DISABLED" not in blocking:
        blocking.append("ACTIVATION_DISABLED")
    if "OBSERVATIONAL_GATE_FORCED_OFF" not in blocking:
        blocking.append("OBSERVATIONAL_GATE_FORCED_OFF")
    if "ACTUAL_WRITER_NOT_CALLED" not in blocking:
        blocking.append("ACTUAL_WRITER_NOT_CALLED")
    if "ACTUAL_DOCUMENT_UNCHANGED" not in blocking:
        blocking.append("ACTUAL_DOCUMENT_UNCHANGED")

    blocked = True  # PR-22 never activates
    if preview_status == "PREVIEW_READY":
        preview_status = "PREVIEW_BLOCKED"
        if "ACTIVATION_DISABLED" not in blocking:
            blocking.append("ACTIVATION_DISABLED")
        if "OBSERVATIONAL_GATE_FORCED_OFF" not in blocking:
            blocking.append("OBSERVATIONAL_GATE_FORCED_OFF")

    uniq: list[str] = []
    seen: set[str] = set()
    for r in blocking:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    return ActivationPreview(
        preview_id=f"AP-{seq:04d}",
        patch_intent_id=intent.patch_intent_id,
        target_candidate_id=target.patch_target_candidate_id,
        preview_status=preview_status,
        would_modify_document=bool(would_modify and intent.intent_status == "ELIGIBLE"),
        would_require_review=bool(
            would_review or intent.intent_status == "REVIEW_REQUIRED"
        ),
        blocked=blocked,
        blocking_reasons=uniq,
        allowed_operations=list(allowed_operations or []),
        requested_operation=intent.requested_operation,
        actual_document_changed=False,
        actual_writer_called=False,
        evidence={
            "template_allowed": target.template_allowed,
            "writer_supported": target.writer_supported,
            "activation_allowed": target.activation_allowed,
            "external_activation_flag": (target.evidence or {}).get(
                "external_activation_flag", False
            ),
            "observational_gate_forced_off": (target.evidence or {}).get(
                "observational_gate_forced_off", True
            ),
            "observational_only": True,
        },
    )
