# -*- coding: utf-8 -*-
"""PR-24: Patch Contract + Operation Plan builder (observational)."""

from __future__ import annotations

from typing import Any

from document_ai.patch_contract.capability_gate import evaluate_contract_capabilities
from document_ai.patch_contract.fingerprint import normalize_for_fingerprint
from document_ai.patch_contract.preconditions import build_preconditions
from document_ai.patch_contract.schema import (
    REQUESTED_OPERATIONS,
    PatchContract,
    PatchContractInput,
    PatchOperationPlan,
    PatchPrecondition,
)
from document_ai.patch_contract.writer_plan import select_writer_adapter
from document_ai.semantic_locator.text_normalization import normalize_text


def _location_consistent(inp: PatchContractInput) -> bool:
    if not inp.physical_candidate_id and inp.location_status in ("RESOLVED", "REVIEW"):
        return False
    if inp.location_type == "TABLE_CELL" and inp.cell_coordinate is None:
        return False
    if inp.location_type == "PARAGRAPH" and inp.paragraph_index is None and not inp.block_id:
        return False
    return True


def decide_contract_status(
    inp: PatchContractInput,
    preconditions: list[PatchPrecondition],
    *,
    caps: dict[str, Any],
    adapter: dict[str, Any],
) -> tuple[str, list[str]]:
    """Map inputs + preconditions → contract_status (never EXECUTABLE)."""
    reasons: list[str] = []
    op = (inp.requested_operation or "").upper()

    # Broken references → INVALID
    if not inp.intent_reference_valid:
        return "CONTRACT_INVALID", ["BROKEN_PATCH_INTENT_REFERENCE"]
    if not inp.target_reference_valid:
        return "CONTRACT_INVALID", ["BROKEN_TARGET_REFERENCE"]
    if not inp.primary_reference_valid:
        return "CONTRACT_INVALID", ["BROKEN_PRIMARY_LOCATION_REFERENCE"]
    if not inp.document_exists:
        return "CONTRACT_INVALID", ["DOCUMENT_MISSING"]
    expected_doc = inp.expected_document_id or inp.document_id
    if inp.document_id != expected_doc:
        return "CONTRACT_INVALID", ["DOCUMENT_ID_MISMATCH"]

    if op not in REQUESTED_OPERATIONS:
        return "CONTRACT_INVALID", ["INVALID_OPERATION"]

    # Status gates
    if inp.intent_status == "INVALID" or inp.target_status == "INVALID":
        return "CONTRACT_INVALID", ["INVALID_UPSTREAM_STATUS"]
    if inp.location_status == "INVALID":
        return "CONTRACT_INVALID", ["INVALID_LOCATION_STATUS"]

    if inp.intent_status != "ELIGIBLE":
        if inp.intent_status in ("REVIEW_REQUIRED", "REVIEW"):
            reasons.append("INTENT_REVIEW_REQUIRED")
            return "CONTRACT_REVIEW", reasons
        reasons.append("INTENT_NOT_ELIGIBLE")
        return "CONTRACT_BLOCKED", reasons

    if inp.target_status == "REVIEW" or inp.location_status == "REVIEW":
        reasons.append("PHYSICAL_OR_TARGET_AMBIGUITY")
        return "CONTRACT_REVIEW", reasons

    if inp.target_status != "RESOLVED":
        reasons.append("TARGET_UNRESOLVED")
        return "CONTRACT_BLOCKED", reasons

    if inp.location_status == "UNRESOLVED":
        reasons.append("LOCATION_UNRESOLVED")
        return "CONTRACT_BLOCKED", reasons

    if inp.location_status != "RESOLVED":
        reasons.append("LOCATION_NOT_RESOLVED")
        return "CONTRACT_BLOCKED", reasons

    if not inp.physical_candidate_id:
        reasons.append("MISSING_PHYSICAL_CANDIDATE")
        return "CONTRACT_BLOCKED", reasons

    if not _location_consistent(inp):
        reasons.append("LOCATION_INCONSISTENT")
        return "CONTRACT_BLOCKED", reasons

    # Operation-specific
    if op in ("UPDATE", "REPLACE"):
        if not (inp.proposed_text and str(inp.proposed_text).strip()):
            reasons.append("MISSING_PROPOSED_TEXT")
            return "CONTRACT_BLOCKED", reasons
        if inp.original_text is None:
            reasons.append("ORIGINAL_TEXT_NOT_OBSERVABLE")
            return "CONTRACT_BLOCKED", reasons
    if op == "ADD":
        if not (inp.section_id or inp.block_id):
            reasons.append("MISSING_INSERTION_ANCHOR")
            return "CONTRACT_BLOCKED", reasons
        if not adapter.get("writer_supported") or not caps.get("writer_supported"):
            reasons.append("ADD_WRITER_UNSUPPORTED")
            return "CONTRACT_BLOCKED", reasons
    if op == "DELETE":
        reasons.append("DELETE_REQUIRES_REVIEW")
        if not inp.human_approval_present:
            reasons.append("HUMAN_APPROVAL_MISSING")
        if inp.original_text is None:
            reasons.append("ORIGINAL_TEXT_MISSING_FOR_DELETE")
        return "CONTRACT_REVIEW", reasons
    if op == "LINK":
        if not inp.link_metadata:
            reasons.append("LINK_METADATA_MISSING")
            return "CONTRACT_BLOCKED", reasons
        if not caps.get("writer_supported"):
            reasons.append("LINK_WRITER_UNSUPPORTED")
            return "CONTRACT_BLOCKED", reasons

    # Fingerprint stale / mismatch blocks
    for pc in preconditions:
        if pc.precondition_type == "SOURCE_FINGERPRINT_MATCH":
            if pc.precondition_status == "UNSATISFIED":
                reasons.append("STALE_OR_MISMATCHED_FINGERPRINT")
                return "CONTRACT_BLOCKED", reasons
        if pc.precondition_type == "ORIGINAL_TEXT_MATCH":
            if pc.precondition_status == "UNSATISFIED" and op in (
                "UPDATE",
                "REPLACE",
            ):
                reasons.append("ORIGINAL_TEXT_MISMATCH")
                return "CONTRACT_BLOCKED", reasons

    if not caps.get("writer_supported") and op in ("UPDATE", "REPLACE"):
        # markdown adapters still supported via select_writer_adapter
        if not adapter.get("writer_supported"):
            reasons.append("WRITER_UNSUPPORTED")
            return "CONTRACT_BLOCKED", reasons

    # Template node presence for ready-for-review
    if not inp.template_node_id:
        reasons.append("MISSING_TEMPLATE_NODE")
        return "CONTRACT_BLOCKED", reasons

    reasons.append("CONTRACT_READY_OBSERVATIONAL")
    reasons.append("EXECUTION_BLOCKED_BY_OBSERVATIONAL_GATE")
    return "CONTRACT_READY_FOR_REVIEW", reasons


def build_operation_plan(
    inp: PatchContractInput,
    *,
    patch_contract_id: str,
    seq: int,
    caps: dict[str, Any],
    adapter: dict[str, Any],
) -> PatchOperationPlan:
    op = (inp.requested_operation or "").upper()
    return PatchOperationPlan(
        operation_plan_id=f"POP-{seq:04d}",
        patch_contract_id=patch_contract_id,
        operation=op,
        document_id=inp.document_id,
        location_type=inp.location_type,
        section_id=inp.section_id,
        block_id=inp.block_id,
        paragraph_index=inp.paragraph_index,
        list_index=inp.list_index,
        table_index=inp.table_index,
        cell_coordinate=inp.cell_coordinate,
        character_span=inp.character_span,
        span_kind=inp.span_kind or "NONE",
        original_text=inp.original_text,
        proposed_text=inp.proposed_text,
        normalized_original_text=(
            normalize_for_fingerprint(inp.original_text)
            if inp.original_text is not None
            else None
        ),
        normalized_proposed_text=(
            normalize_text(inp.proposed_text) if inp.proposed_text is not None else None
        ),
        writer_supported=bool(
            caps.get("writer_supported") and adapter.get("writer_supported")
        ),
        template_allowed=bool(caps.get("template_allowed")),
        activation_allowed=False,
        actual_writer_called=False,
        actual_document_changed=False,
        writer_adapter=str(adapter.get("writer_adapter") or "UNSUPPORTED_WRITER"),
        evidence={
            "span_kind_note": (
                "character_span is not executable unless span_kind=SOURCE_ABSOLUTE"
            ),
            "observational_only": True,
            "adapter_reasons": list(adapter.get("reason_codes") or []),
        },
    )


def build_contract(
    inp: PatchContractInput,
    *,
    seq: int,
    env: dict[str, str] | None = None,
    allowed_operations: list[str] | None = None,
) -> tuple[PatchContract, list[PatchPrecondition], PatchOperationPlan]:
    """Build observational contract + preconditions + operation plan."""
    patch_contract_id = f"PCT-{seq:04d}"
    caps = evaluate_contract_capabilities(
        inp.requested_operation,
        location_type=inp.location_type,
        source_format=inp.source_format,
        allowed_operations=allowed_operations
        or ["UPDATE", "REPLACE", "ADD", "DELETE", "LINK"],
        env=env,
        external_activation_flag=inp.external_activation_flag
        if inp.metadata.get("force_external_flag") is not None
        else None,
    )
    # Allow fixture to force external flag observation
    if "external_activation_flag" in inp.metadata:
        caps = dict(caps)
        caps["external_activation_flag"] = bool(inp.metadata["external_activation_flag"])
        # Keep activation forced off
        caps["activation_allowed"] = False
        caps["observational_gate_forced_off"] = True

    adapter = select_writer_adapter(
        source_format=inp.source_format,
        location_type=inp.location_type,
        requested_operation=inp.requested_operation,
    )

    # For UPDATE/REPLACE with markdown adapter, treat writer_supported as True for caps
    # when adapter supports it (capability_gate uses WRITER_SUPPORTED_OPERATIONS which
    # includes UPDATE/REPLACE).
    if adapter.get("writer_supported") and (inp.requested_operation or "").upper() in (
        "UPDATE",
        "REPLACE",
    ):
        caps = dict(caps)
        caps["writer_supported"] = True

    if (inp.requested_operation or "").upper() in ("ADD", "DELETE", "LINK"):
        caps = dict(caps)
        caps["writer_supported"] = False

    preconditions = build_preconditions(
        inp, patch_contract_id=patch_contract_id, seq=seq, caps=caps
    )
    status, reasons = decide_contract_status(
        inp, preconditions, caps=caps, adapter=adapter
    )
    plan = build_operation_plan(
        inp,
        patch_contract_id=patch_contract_id,
        seq=seq,
        caps=caps,
        adapter=adapter,
    )

    contract = PatchContract(
        patch_contract_id=patch_contract_id,
        patch_contract_input_id=inp.patch_contract_input_id,
        change_id=inp.change_id,
        patch_intent_id=inp.patch_intent_id,
        patch_target_candidate_id=inp.patch_target_candidate_id,
        primary_location_id=inp.primary_location_id,
        document_id=inp.document_id,
        contract_status=status,
        requested_operation=(inp.requested_operation or "").upper(),
        operation_plan_id=plan.operation_plan_id,
        precondition_ids=[p.precondition_id for p in preconditions],
        reason_codes=reasons,
        evidence={
            "observational_only": True,
            "external_activation_flag": caps.get("external_activation_flag", False),
            "observational_gate_forced_off": True,
            "physical_candidate_id": inp.physical_candidate_id,
            "template_id": inp.template_id,
            "template_node_id": inp.template_node_id,
            "span_kind": inp.span_kind,
            "fingerprint_status": inp.fingerprint_status,
            "case": inp.metadata.get("case"),
        },
        contract_executable=False,
        activation_allowed=False,
        actual_patch_created=False,
        actual_document_changed=False,
        actual_writer_called=False,
        actual_docx_changed=False,
    )
    return contract, preconditions, plan
