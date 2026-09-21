# -*- coding: utf-8 -*-
"""PR-24: Observational Patch Contract / Writer Plan Bridge orchestrator."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.patch_contract.contract_builder import build_contract
from document_ai.patch_contract.fingerprint import fingerprint_text, sha256_hex
from document_ai.patch_contract.preview import build_writer_plan_preview
from document_ai.patch_contract.schema import (
    PatchContract,
    PatchContractInput,
    PatchOperationPlan,
    PatchPrecondition,
    WriterPlanPreview,
)
from document_ai.patch_contract.validation import validate_patch_contracts


def _fp(text: str) -> str:
    return fingerprint_text(text)["fingerprint"]


def sample_patch_contract_inputs() -> list[PatchContractInput]:
    """Deterministic fixtures covering required PR-24 scenarios."""
    orig_para = "내부 artifact 및 샘플 fixture"
    orig_cell = "항목A"
    orig_list = "핵심 발견 1"
    doc_fp = sha256_hex("sample_md_general_report_001")
    block_fp = _fp("block:methodology:data_sources")

    return [
        # 1. RESOLVED paragraph UPDATE → CONTRACT_READY_FOR_REVIEW / PREVIEW_BLOCKED
        PatchContractInput(
            patch_contract_input_id="PCI-0001",
            change_id="CHG-001",
            patch_intent_id="PI-0001",
            patch_target_candidate_id="PTC-0001",
            primary_location_id="PPL-0001",
            document_id="sample_md_general_report_001",
            requested_operation="UPDATE",
            proposed_text="내부 artifact, 샘플 fixture 및 공개 데이터셋",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            physical_candidate_id="PLC01-0003",
            location_type="PARAGRAPH",
            section_id="methodology",
            block_id="para-data-sources",
            paragraph_index=0,
            character_span=(0, len(orig_para)),
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text=orig_para,
            source_format="markdown",
            expected_document_fingerprint=doc_fp,
            observed_document_fingerprint=doc_fp,
            expected_block_fingerprint=block_fp,
            observed_block_fingerprint=block_fp,
            expected_original_text_fingerprint=_fp(orig_para),
            observed_original_text_fingerprint=_fp(orig_para),
            fingerprint_status="AVAILABLE",
            metadata={"case": "resolved_paragraph_update"},
        ),
        # 2. RESOLVED table cell UPDATE
        PatchContractInput(
            patch_contract_input_id="PCI-0002",
            change_id="CHG-002",
            patch_intent_id="PI-0002",
            patch_target_candidate_id="PTC-0002",
            primary_location_id="PPL-0002",
            document_id="sample_md_general_report_001",
            requested_operation="UPDATE",
            proposed_text="항목A-갱신",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            physical_candidate_id="PLC02-0010",
            location_type="TABLE_CELL",
            section_id="methodology",
            block_id="tbl-1:r0c0",
            table_index=0,
            cell_coordinate=(0, 0),
            character_span=(0, len(orig_cell)),
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text=orig_cell,
            source_format="markdown",
            expected_original_text_fingerprint=_fp(orig_cell),
            observed_original_text_fingerprint=_fp(orig_cell),
            fingerprint_status="AVAILABLE",
            metadata={"case": "resolved_table_cell_update"},
        ),
        # 3. RESOLVED list UPDATE
        PatchContractInput(
            patch_contract_input_id="PCI-0003",
            change_id="CHG-003",
            patch_intent_id="PI-0003",
            patch_target_candidate_id="PTC-0003",
            primary_location_id="PPL-0003",
            document_id="sample_md_general_report_001",
            requested_operation="UPDATE",
            proposed_text="핵심 발견 1 (보강)",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.results.key_findings",
            physical_candidate_id="PLC03-0005",
            location_type="LIST",
            section_id="results",
            block_id="list-key-findings",
            list_index=0,
            character_span=(0, len(orig_list)),
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text=orig_list,
            source_format="markdown",
            expected_original_text_fingerprint=_fp(orig_list),
            observed_original_text_fingerprint=_fp(orig_list),
            fingerprint_status="AVAILABLE",
            metadata={"case": "resolved_list_update"},
        ),
        # 4. ADD writer unsupported → CONTRACT_BLOCKED
        PatchContractInput(
            patch_contract_input_id="PCI-0004",
            change_id="CHG-004",
            patch_intent_id="PI-0004",
            patch_target_candidate_id="PTC-0004",
            primary_location_id="PPL-0004",
            document_id="sample_md_business_proposal_001",
            requested_operation="ADD",
            proposed_text="검수 단계 추가",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="business_proposal_v1",
            template_node_id="business_proposal_v1.execution_plan.schedule",
            physical_candidate_id="PLC04-0002",
            location_type="PARAGRAPH",
            section_id="execution_plan",
            block_id="para-schedule",
            paragraph_index=0,
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text=None,
            source_format="markdown",
            fingerprint_status="NOT_AVAILABLE",
            metadata={"case": "add_unsupported"},
        ),
        # 5. REVIEW physical location → CONTRACT_REVIEW
        PatchContractInput(
            patch_contract_input_id="PCI-0005",
            change_id="CHG-005",
            patch_intent_id="PI-0005",
            patch_target_candidate_id="PTC-0005",
            primary_location_id="PPL-0005",
            document_id="sample_dup_headings_001",
            requested_operation="UPDATE",
            proposed_text="결과 본문 보강",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="REVIEW",
            template_id="general_report_v1",
            template_node_id="general_report_v1.results.body",
            physical_candidate_id="PLC05-0001",
            location_type="PARAGRAPH",
            section_id="results",
            block_id="para-dup",
            paragraph_index=0,
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text="결과",
            source_format="object",
            expected_original_text_fingerprint=_fp("결과"),
            observed_original_text_fingerprint=_fp("결과"),
            fingerprint_status="AVAILABLE",
            metadata={"case": "review_physical"},
        ),
        # 6. UNRESOLVED physical → CONTRACT_BLOCKED
        PatchContractInput(
            patch_contract_input_id="PCI-0006",
            change_id="CHG-006",
            patch_intent_id="PI-0006",
            patch_target_candidate_id="PTC-0006",
            primary_location_id="PPL-0006",
            document_id="sample_empty_001",
            requested_operation="UPDATE",
            proposed_text="x",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="UNRESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.approach",
            physical_candidate_id=None,
            location_type=None,
            span_kind="NONE",
            original_text="",
            source_format="markdown",
            fingerprint_status="NOT_AVAILABLE",
            metadata={"case": "unresolved_physical"},
        ),
        # 7. INVALID target reference → CONTRACT_INVALID
        PatchContractInput(
            patch_contract_input_id="PCI-0007",
            change_id="CHG-007",
            patch_intent_id="PI-0007",
            patch_target_candidate_id="PTC-BAD",
            primary_location_id="PPL-0007",
            document_id="sample_md_general_report_001",
            requested_operation="UPDATE",
            proposed_text="y",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            physical_candidate_id="PLC07-0001",
            location_type="PARAGRAPH",
            section_id="methodology",
            block_id="para-x",
            paragraph_index=0,
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text="y",
            target_reference_valid=False,
            fingerprint_status="NOT_AVAILABLE",
            metadata={"case": "invalid_target_ref"},
        ),
        # 8. Missing proposed_text → CONTRACT_BLOCKED
        PatchContractInput(
            patch_contract_input_id="PCI-0008",
            change_id="CHG-008",
            patch_intent_id="PI-0008",
            patch_target_candidate_id="PTC-0008",
            primary_location_id="PPL-0008",
            document_id="sample_md_general_report_001",
            requested_operation="UPDATE",
            proposed_text="",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            physical_candidate_id="PLC08-0001",
            location_type="PARAGRAPH",
            section_id="methodology",
            block_id="para-ds",
            paragraph_index=0,
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text=orig_para,
            expected_original_text_fingerprint=_fp(orig_para),
            observed_original_text_fingerprint=_fp(orig_para),
            fingerprint_status="AVAILABLE",
            metadata={"case": "missing_proposed_text"},
        ),
        # 9. DELETE without approval → CONTRACT_REVIEW
        PatchContractInput(
            patch_contract_input_id="PCI-0009",
            change_id="CHG-009",
            patch_intent_id="PI-0009",
            patch_target_candidate_id="PTC-0009",
            primary_location_id="PPL-0009",
            document_id="sample_md_business_proposal_001",
            requested_operation="DELETE",
            proposed_text=None,
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="business_proposal_v1",
            template_node_id="business_proposal_v1.schedule.body",
            physical_candidate_id="PLC09-0001",
            location_type="PARAGRAPH",
            section_id="schedule",
            block_id="para-sched-body",
            paragraph_index=0,
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text="일정 본문",
            human_approval_present=False,
            fingerprint_status="AVAILABLE",
            expected_original_text_fingerprint=_fp("일정 본문"),
            observed_original_text_fingerprint=_fp("일정 본문"),
            metadata={"case": "delete_without_approval"},
        ),
        # 10. LINK missing metadata → CONTRACT_BLOCKED
        PatchContractInput(
            patch_contract_input_id="PCI-0010",
            change_id="CHG-010",
            patch_intent_id="PI-0010",
            patch_target_candidate_id="PTC-0010",
            primary_location_id="PPL-0010",
            document_id="sample_md_general_report_001",
            requested_operation="LINK",
            proposed_text="link",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.references.entries",
            physical_candidate_id="PLC10-0001",
            location_type="PARAGRAPH",
            section_id="references",
            block_id="para-ref",
            paragraph_index=0,
            span_kind="NONE",
            original_text="ref",
            link_metadata=None,
            fingerprint_status="NOT_AVAILABLE",
            metadata={"case": "link_missing_metadata"},
        ),
        # 11. document_id mismatch → CONTRACT_INVALID
        PatchContractInput(
            patch_contract_input_id="PCI-0011",
            change_id="CHG-011",
            patch_intent_id="PI-0011",
            patch_target_candidate_id="PTC-0011",
            primary_location_id="PPL-0011",
            document_id="sample_md_general_report_001",
            expected_document_id="other_document_id",
            requested_operation="UPDATE",
            proposed_text="z",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            physical_candidate_id="PLC11-0001",
            location_type="PARAGRAPH",
            section_id="methodology",
            block_id="para-z",
            paragraph_index=0,
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text="z",
            fingerprint_status="NOT_AVAILABLE",
            metadata={"case": "document_id_mismatch"},
        ),
        # 12. stale source fingerprint → CONTRACT_BLOCKED
        PatchContractInput(
            patch_contract_input_id="PCI-0012",
            change_id="CHG-012",
            patch_intent_id="PI-0012",
            patch_target_candidate_id="PTC-0012",
            primary_location_id="PPL-0012",
            document_id="sample_md_general_report_001",
            requested_operation="UPDATE",
            proposed_text="갱신본",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            physical_candidate_id="PLC12-0001",
            location_type="PARAGRAPH",
            section_id="methodology",
            block_id="para-stale",
            paragraph_index=0,
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text=orig_para,
            expected_document_fingerprint=doc_fp,
            observed_document_fingerprint=sha256_hex("stale-document-content"),
            expected_original_text_fingerprint=_fp(orig_para),
            observed_original_text_fingerprint=_fp("다른 원문"),
            fingerprint_status="STALE",
            metadata={"case": "stale_fingerprint"},
        ),
        # 13. external Feature Flag ON → still blocked
        PatchContractInput(
            patch_contract_input_id="PCI-0013",
            change_id="CHG-013",
            patch_intent_id="PI-0013",
            patch_target_candidate_id="PTC-0013",
            primary_location_id="PPL-0013",
            document_id="sample_md_general_report_001",
            requested_operation="UPDATE",
            proposed_text="플래그 ON에서도 차단",
            intent_status="ELIGIBLE",
            target_status="RESOLVED",
            location_status="RESOLVED",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.approach",
            physical_candidate_id="PLC13-0001",
            location_type="PARAGRAPH",
            section_id="methodology",
            block_id="para-approach",
            paragraph_index=0,
            character_span=(0, 10),
            span_kind="ESTIMATED_BLOCK_LOCAL",
            original_text="정적 Template 기반 매핑",
            expected_original_text_fingerprint=_fp("정적 Template 기반 매핑"),
            observed_original_text_fingerprint=_fp("정적 Template 기반 매핑"),
            fingerprint_status="AVAILABLE",
            external_activation_flag=True,
            metadata={
                "case": "external_flag_on",
                "external_activation_flag": True,
            },
        ),
    ]


def build_summary(
    inputs: list[PatchContractInput],
    contracts: list[PatchContract],
    preconditions: list[PatchPrecondition],
    plans: list[PatchOperationPlan],
    previews: list[WriterPlanPreview],
    *,
    external_activation_flag: bool = False,
) -> dict[str, Any]:
    status_counts = Counter(c.contract_status for c in contracts)
    op_counts = Counter(c.requested_operation for c in contracts)
    adapter_counts = Counter(p.writer_adapter for p in plans)
    pc_counts = Counter(p.precondition_status for p in preconditions)
    preview_counts = Counter(p.preview_status for p in previews)

    if status_counts.get("CONTRACT_INVALID", 0) > 0:
        global_status = "INVALID"
    elif status_counts.get("CONTRACT_BLOCKED", 0) > 0:
        global_status = "BLOCKED"
    elif status_counts.get("CONTRACT_REVIEW", 0) > 0:
        global_status = "REVIEW"
    else:
        global_status = "VALID"

    return {
        "stage": "patch_contract_summary",
        "input_count": len(inputs),
        "contract_count": len(contracts),
        "precondition_count": len(preconditions),
        "operation_plan_count": len(plans),
        "preview_count": len(previews),
        "contract_status_counts": dict(sorted(status_counts.items())),
        "ready_for_review_count": status_counts.get("CONTRACT_READY_FOR_REVIEW", 0),
        "blocked_count": status_counts.get("CONTRACT_BLOCKED", 0),
        "review_count": status_counts.get("CONTRACT_REVIEW", 0),
        "invalid_count": status_counts.get("CONTRACT_INVALID", 0),
        "operation_counts": dict(sorted(op_counts.items())),
        "adapter_counts": dict(sorted(adapter_counts.items())),
        "precondition_status_counts": dict(sorted(pc_counts.items())),
        "preview_status_counts": dict(sorted(preview_counts.items())),
        "preview_ready_count": preview_counts.get("PREVIEW_READY", 0),
        "preview_blocked_count": preview_counts.get("PREVIEW_BLOCKED", 0),
        "preview_review_count": preview_counts.get("PREVIEW_REVIEW", 0),
        "preview_invalid_count": preview_counts.get("PREVIEW_INVALID", 0),
        "contract_executable_count": sum(1 for c in contracts if c.contract_executable),
        "activation_allowed_count": sum(1 for c in contracts if c.activation_allowed),
        "actual_patch_created_count": 0,
        "actual_document_changed_count": 0,
        "actual_docx_changed_count": 0,
        "actual_writer_called_count": 0,
        "writer_import_call_count": 0,
        "docx_markdown_mutation_count": 0,
        "full_candidate_count": None,  # PR-23 bridge field (N/A standalone)
        "artifact_candidate_count": None,
        "external_activation_flag": external_activation_flag,
        "observational_gate_forced_off": True,
        "activation_allowed": False,
        "global_patch_contract_status": global_status,
        "actual_patch_created": False,
        "actual_document_changed": False,
        "actual_docx_changed": False,
        "actual_writer_called": False,
        "note": (
            "PR-24 observational patch contract / writer plan bridge. "
            "No Writer call, no DOCX/Markdown mutation."
        ),
    }


def run_patch_contract_engine(
    *,
    inputs: list[PatchContractInput] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Observational dry-run: build contracts/previews without Writer/DOCX writes."""
    env = dict(env or {})
    inputs = list(inputs) if inputs is not None else sample_patch_contract_inputs()
    external_flag = bool(is_docx_activation_enabled(env=env))

    contracts: list[PatchContract] = []
    preconditions: list[PatchPrecondition] = []
    plans: list[PatchOperationPlan] = []
    previews: list[WriterPlanPreview] = []

    for seq, inp in enumerate(
        sorted(inputs, key=lambda x: x.patch_contract_input_id), start=1
    ):
        # Propagate env-observed external flag into evidence for all cases
        if external_flag:
            meta = dict(inp.metadata)
            meta["external_activation_flag"] = True
            inp.metadata = meta
            inp.external_activation_flag = True

        contract, pcs, plan = build_contract(inp, seq=seq, env=env)
        caps = {
            "external_activation_flag": external_flag or bool(inp.external_activation_flag),
            "observational_gate_forced_off": True,
            "activation_allowed": False,
        }
        preview = build_writer_plan_preview(
            contract, plan, inp, seq=seq, caps=caps
        )
        contracts.append(contract)
        preconditions.extend(pcs)
        plans.append(plan)
        previews.append(preview)

    summary = build_summary(
        inputs,
        contracts,
        preconditions,
        plans,
        previews,
        external_activation_flag=external_flag,
    )
    validation = validate_patch_contracts(
        inputs=inputs,
        contracts=contracts,
        preconditions=preconditions,
        plans=plans,
        previews=previews,
        summary=summary,
        external_activation_flag=external_flag,
    )

    return {
        "stage": "patch_contract_engine",
        "schema_version": "patch_contract_v1",
        "observational_only": True,
        "generated_from_pr22": True,
        "generated_from_pr23": True,
        "inputs": [i.to_dict() for i in sorted(inputs, key=lambda x: x.patch_contract_input_id)],
        "contracts": [c.to_dict() for c in contracts],
        "preconditions": [p.to_dict() for p in preconditions],
        "operation_plans": [p.to_dict() for p in plans],
        "writer_plan_previews": [p.to_dict() for p in previews],
        "summary": summary,
        "validation": validation,
        "external_activation_flag": external_flag,
        "observational_gate_forced_off": True,
        "activation_allowed": False,
        "contract_executable": False,
        "actual_patch_created": False,
        "actual_document_changed": False,
        "actual_docx_changed": False,
        "actual_writer_called": False,
        "writer_import_call_count": 0,
        "docx_markdown_mutation_count": 0,
        "note": (
            "PR-24 observational Patch Contract / Writer Plan Bridge. "
            "Does not mutate DOCX/Markdown or call Writer. "
            "PREVIEW_READY and CONTRACT_EXECUTABLE are forbidden."
        ),
    }
