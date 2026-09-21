# -*- coding: utf-8 -*-
"""PR-24: Writer Plan Preview (observational; never PREVIEW_READY)."""

from __future__ import annotations

from typing import Any

from document_ai.patch_contract.schema import (
    PatchContract,
    PatchContractInput,
    PatchOperationPlan,
    WriterPlanPreview,
)


def build_writer_plan_preview(
    contract: PatchContract,
    plan: PatchOperationPlan,
    inp: PatchContractInput,
    *,
    seq: int,
    caps: dict[str, Any] | None = None,
) -> WriterPlanPreview:
    """Build observational writer plan preview — never PREVIEW_READY."""
    caps = caps or {}
    blocking: list[str] = [
        "OBSERVATIONAL_GATE_FORCED_OFF",
        "ACTIVATION_ALLOWED_FALSE",
        "CONTRACT_NOT_EXECUTABLE",
        "WRITER_NOT_CALLED",
    ]

    if contract.contract_status == "CONTRACT_INVALID":
        preview_status = "PREVIEW_INVALID"
        blocking.append("CONTRACT_INVALID")
    elif contract.contract_status == "CONTRACT_REVIEW":
        preview_status = "PREVIEW_REVIEW"
        blocking.append("CONTRACT_REVIEW")
    elif contract.contract_status == "CONTRACT_BLOCKED":
        preview_status = "PREVIEW_BLOCKED"
        blocking.append("CONTRACT_BLOCKED")
    else:
        # CONTRACT_READY_FOR_REVIEW still cannot execute in PR-24
        preview_status = "PREVIEW_BLOCKED"
        blocking.append("READY_FOR_REVIEW_BUT_EXECUTION_BLOCKED")

    if inp.span_kind != "SOURCE_ABSOLUTE":
        blocking.append("SPAN_KIND_NOT_EXECUTABLE")

    intended_location = {
        "document_id": plan.document_id,
        "location_type": plan.location_type,
        "section_id": plan.section_id,
        "block_id": plan.block_id,
        "paragraph_index": plan.paragraph_index,
        "list_index": plan.list_index,
        "table_index": plan.table_index,
        "cell_coordinate": list(plan.cell_coordinate)
        if plan.cell_coordinate is not None
        else None,
        "character_span": list(plan.character_span)
        if plan.character_span is not None
        else None,
        "span_kind": plan.span_kind,
    }
    intended_payload = {
        "operation": plan.operation,
        "original_text": plan.original_text,
        "proposed_text": plan.proposed_text,
        "normalized_proposed_text": plan.normalized_proposed_text,
    }

    return WriterPlanPreview(
        writer_plan_preview_id=f"WPP-{seq:04d}",
        patch_contract_id=contract.patch_contract_id,
        writer_adapter=plan.writer_adapter,
        intended_action=plan.operation,
        intended_location=intended_location,
        intended_payload=intended_payload,
        preview_status=preview_status,
        blocking_reasons=blocking,
        would_modify_document=False,  # observational: would not actually modify
        contract_executable=False,
        activation_allowed=False,
        actual_writer_called=False,
        actual_document_changed=False,
        actual_patch_created=False,
        evidence={
            "observational_only": True,
            "external_activation_flag": caps.get("external_activation_flag", False),
            "observational_gate_forced_off": True,
            "contract_status": contract.contract_status,
            "note": "PR-24 dry-run preview. PREVIEW_READY is forbidden.",
        },
    )
