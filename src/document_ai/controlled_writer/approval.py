# -*- coding: utf-8 -*-
"""PR-25: Approval check."""

from __future__ import annotations

from typing import Any

from document_ai.controlled_writer.schema import (
    APPROVAL_DECISIONS,
    ApprovalDecision,
    ControlledWriterInput,
)


def evaluate_approval(
    inp: ControlledWriterInput,
) -> dict[str, Any]:
    """Return approval gate outcome. DELETE requires APPROVED (not AUTO)."""
    approval = inp.approval
    op = (inp.requested_operation or "").upper()

    if approval is None:
        return {
            "approved": False,
            "decision": "MANUAL_REQUIRED",
            "reason_codes": ["APPROVAL_MISSING"],
            "approval": None,
        }

    decision = str(approval.decision or "").upper()
    if decision not in APPROVAL_DECISIONS:
        return {
            "approved": False,
            "decision": decision or "INVALID",
            "reason_codes": ["APPROVAL_DECISION_INVALID"],
            "approval": approval.to_dict(),
        }

    if decision == "REJECTED":
        return {
            "approved": False,
            "decision": decision,
            "reason_codes": ["APPROVAL_REJECTED"],
            "approval": approval.to_dict(),
        }

    if decision == "MANUAL_REQUIRED":
        return {
            "approved": False,
            "decision": decision,
            "reason_codes": ["APPROVAL_MANUAL_REQUIRED"],
            "approval": approval.to_dict(),
        }

    if op == "DELETE" and decision != "APPROVED":
        return {
            "approved": False,
            "decision": decision,
            "reason_codes": ["DELETE_REQUIRES_EXPLICIT_APPROVAL"],
            "approval": approval.to_dict(),
        }

    if decision in ("APPROVED", "AUTO_APPROVED"):
        return {
            "approved": True,
            "decision": decision,
            "reason_codes": ["APPROVAL_GRANTED"],
            "approval": approval.to_dict(),
        }

    return {
        "approved": False,
        "decision": decision,
        "reason_codes": ["APPROVAL_NOT_GRANTED"],
        "approval": approval.to_dict(),
    }


def make_approval(
    *,
    approval_id: str,
    patch_contract_id: str,
    decision: str,
    approved_by: str | None = "tester",
    approved_at: str | None = "2026-07-27T00:00:00Z",
    reason: str = "",
) -> ApprovalDecision:
    return ApprovalDecision(
        approval_id=approval_id,
        patch_contract_id=patch_contract_id,
        decision=decision,
        approved_by=approved_by,
        approved_at=approved_at,
        reason=reason,
    )
