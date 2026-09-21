# -*- coding: utf-8 -*-
"""PR-24: Patch Contract validation (observational)."""

from __future__ import annotations

from typing import Any

from document_ai.patch_contract.schema import (
    CONTRACT_STATUSES,
    PREVIEW_STATUSES,
    PatchContract,
    PatchContractInput,
    PatchOperationPlan,
    PatchPrecondition,
    WriterPlanPreview,
)


def validate_patch_contracts(
    *,
    inputs: list[PatchContractInput],
    contracts: list[PatchContract],
    preconditions: list[PatchPrecondition],
    plans: list[PatchOperationPlan],
    previews: list[WriterPlanPreview],
    summary: dict[str, Any] | None = None,
    external_activation_flag: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    # Unique IDs
    for label, ids in (
        ("patch_contract_id", [c.patch_contract_id for c in contracts]),
        ("precondition_id", [p.precondition_id for p in preconditions]),
        ("operation_plan_id", [p.operation_plan_id for p in plans]),
        ("writer_plan_preview_id", [p.writer_plan_preview_id for p in previews]),
        (
            "patch_contract_input_id",
            [i.patch_contract_input_id for i in inputs],
        ),
    ):
        if len(ids) != len(set(ids)):
            issues.append(f"duplicate_{label}")

    intent_ids = {i.patch_intent_id for i in inputs if i.intent_reference_valid}
    target_ids = {
        i.patch_target_candidate_id for i in inputs if i.target_reference_valid
    }
    primary_ids = {i.primary_location_id for i in inputs if i.primary_reference_valid}
    plan_by_id = {p.operation_plan_id: p for p in plans}
    pc_by_contract: dict[str, list[PatchPrecondition]] = {}
    for p in preconditions:
        pc_by_contract.setdefault(p.patch_contract_id, []).append(p)

    input_by_id = {i.patch_contract_input_id: i for i in inputs}

    for c in contracts:
        if c.contract_status not in CONTRACT_STATUSES:
            issues.append(f"forbidden_or_invalid_contract_status:{c.patch_contract_id}")
        if c.contract_status in ("CONTRACT_EXECUTABLE", "EXECUTED", "APPLIED"):
            issues.append(f"forbidden_contract_status:{c.patch_contract_id}")
        if c.contract_executable:
            issues.append(f"contract_executable_true:{c.patch_contract_id}")
        if c.activation_allowed:
            issues.append(f"activation_allowed_true:{c.patch_contract_id}")
        if c.actual_patch_created or c.actual_document_changed or c.actual_writer_called:
            issues.append(f"actual_mutation_true:{c.patch_contract_id}")
        if c.actual_docx_changed:
            issues.append(f"actual_docx_changed_true:{c.patch_contract_id}")
        if c.operation_plan_id and c.operation_plan_id not in plan_by_id:
            issues.append(f"invalid_operation_plan_ref:{c.patch_contract_id}")
        if c.patch_contract_input_id not in input_by_id:
            issues.append(f"invalid_input_ref:{c.patch_contract_id}")
        else:
            inp = input_by_id[c.patch_contract_input_id]
            if inp.intent_reference_valid and c.patch_intent_id not in intent_ids:
                # still same input's intent — ok if self-consistent
                pass
            if c.document_id != inp.document_id and inp.intent_reference_valid:
                if c.contract_status != "CONTRACT_INVALID":
                    issues.append(f"document_id_inconsistent:{c.patch_contract_id}")
            if (
                inp.template_node_id
                and c.evidence.get("template_node_id")
                and c.evidence.get("template_node_id") != inp.template_node_id
            ):
                issues.append(f"template_node_mismatch:{c.patch_contract_id}")

        # precondition refs
        for pid in c.precondition_ids:
            if not any(p.precondition_id == pid for p in preconditions):
                issues.append(f"invalid_precondition_ref:{pid}")

    for prev in previews:
        if prev.preview_status not in PREVIEW_STATUSES:
            issues.append(f"forbidden_or_invalid_preview_status:{prev.writer_plan_preview_id}")
        if prev.preview_status == "PREVIEW_READY":
            issues.append(f"forbidden_preview_ready:{prev.writer_plan_preview_id}")
        if prev.contract_executable or prev.activation_allowed:
            issues.append(f"preview_activation_leak:{prev.writer_plan_preview_id}")
        if (
            prev.actual_writer_called
            or prev.actual_document_changed
            or prev.actual_patch_created
        ):
            issues.append(f"preview_mutation_true:{prev.writer_plan_preview_id}")
        if prev.would_modify_document:
            # observational: should remain false
            issues.append(f"would_modify_document_true:{prev.writer_plan_preview_id}")

    for plan in plans:
        if plan.activation_allowed or plan.actual_writer_called or plan.actual_document_changed:
            issues.append(f"plan_mutation_or_activation:{plan.operation_plan_id}")
        if plan.span_kind == "SOURCE_ABSOLUTE":
            # ok, but still not executable in PR-24
            pass
        elif plan.character_span is not None and plan.span_kind not in (
            "ESTIMATED_BLOCK_LOCAL",
            "OOXML_LOCAL",
            "NONE",
        ):
            warnings.append(f"unexpected_span_kind:{plan.operation_plan_id}")

    if summary:
        if summary.get("actual_patch_created_count", 0) != 0:
            issues.append("summary_patch_nonzero")
        if summary.get("actual_document_changed_count", 0) != 0:
            issues.append("summary_doc_nonzero")
        if summary.get("actual_writer_called_count", 0) != 0:
            issues.append("summary_writer_nonzero")
        if summary.get("actual_docx_changed_count", 0) != 0:
            issues.append("summary_docx_nonzero")
        if summary.get("preview_ready_count", 0) != 0:
            issues.append("summary_preview_ready_nonzero")
        if summary.get("contract_executable_count", 0) != 0:
            issues.append("summary_executable_nonzero")
        if summary.get("activation_allowed_count", 0) != 0:
            issues.append("summary_activation_nonzero")
        if summary.get("input_count") != len(inputs):
            issues.append("summary_input_mismatch")

    no_mutation = (
        all(not c.actual_patch_created for c in contracts)
        and all(not c.actual_document_changed for c in contracts)
        and all(not c.actual_writer_called for c in contracts)
        and all(not c.actual_docx_changed for c in contracts)
        and all(not p.actual_writer_called for p in previews)
        and all(not p.actual_document_changed for p in previews)
        and all(not p.actual_patch_created for p in previews)
    )
    no_executable = all(not c.contract_executable for c in contracts) and all(
        not p.contract_executable for p in previews
    )
    no_activation = all(not c.activation_allowed for c in contracts) and all(
        not p.activation_allowed for p in previews
    )
    no_preview_ready = all(p.preview_status != "PREVIEW_READY" for p in previews)
    no_contract_executable_status = all(
        c.contract_status not in ("CONTRACT_EXECUTABLE", "EXECUTED", "APPLIED")
        for c in contracts
    )
    observational_ok = (
        no_mutation
        and no_executable
        and no_activation
        and no_preview_ready
        and no_contract_executable_status
        and (summary is None or summary.get("observational_gate_forced_off") is True)
    )

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "patch_contract_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": {
            "unique_contract_ids": "duplicate_patch_contract_id" not in issues,
            "unique_precondition_ids": "duplicate_precondition_id" not in issues,
            "unique_operation_plan_ids": "duplicate_operation_plan_id" not in issues,
            "unique_preview_ids": "duplicate_writer_plan_preview_id" not in issues,
            "no_preview_ready": no_preview_ready
            and not any(i.startswith("forbidden_preview_ready") for i in issues),
            "no_contract_executable_status": no_contract_executable_status,
            "contract_executable_always_false": no_executable,
            "activation_allowed_always_false": no_activation,
            "actual_patch_created_false": all(
                not c.actual_patch_created for c in contracts
            ),
            "actual_document_changed_false": all(
                not c.actual_document_changed for c in contracts
            ),
            "actual_writer_called_false": all(
                not c.actual_writer_called for c in contracts
            ),
            "actual_docx_changed_false": all(
                not c.actual_docx_changed for c in contracts
            ),
            "observational_only": observational_ok,
            "observational_gate_forced_off": True,
            "external_activation_flag": external_activation_flag,
            "activation_blocked_despite_external_flag": observational_ok,
            "summary_counts_consistent": not any(
                i.startswith("summary_") for i in issues
            ),
        },
        "external_activation_flag": external_activation_flag,
        "observational_gate_forced_off": True,
        "activation_allowed": False,
        "actual_patch_created": False,
        "actual_document_changed": False,
        "actual_writer_called": False,
        "actual_docx_changed": False,
        "note": (
            "PR-24 observational patch contract validation. "
            "External Feature Flag ON still blocked by observational gate."
        ),
    }
