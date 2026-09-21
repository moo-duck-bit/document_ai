# -*- coding: utf-8 -*-
"""PR-24: Observational Patch Contract schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

REQUESTED_OPERATIONS = frozenset({"UPDATE", "REPLACE", "ADD", "DELETE", "LINK"})

CONTRACT_STATUSES = frozenset(
    {
        "CONTRACT_READY_FOR_REVIEW",
        "CONTRACT_BLOCKED",
        "CONTRACT_REVIEW",
        "CONTRACT_INVALID",
    }
)
# Forbidden in PR-24: CONTRACT_EXECUTABLE, EXECUTED, APPLIED

PRECONDITION_TYPES = frozenset(
    {
        "DOCUMENT_EXISTS",
        "DOCUMENT_ID_MATCH",
        "TARGET_RESOLVED",
        "LOCATION_RESOLVED",
        "SOURCE_FINGERPRINT_MATCH",
        "BLOCK_EXISTS",
        "ORIGINAL_TEXT_MATCH",
        "OPERATION_ALLOWED",
        "WRITER_CAPABILITY_SUPPORTED",
        "HUMAN_APPROVAL_PRESENT",
        "OBSERVATIONAL_GATE_DISABLED",
    }
)
PRECONDITION_STATUSES = frozenset(
    {"SATISFIED", "UNSATISFIED", "REVIEW", "NOT_APPLICABLE", "INVALID"}
)

PREVIEW_STATUSES = frozenset(
    {"PREVIEW_BLOCKED", "PREVIEW_REVIEW", "PREVIEW_INVALID"}
)
# Forbidden: PREVIEW_READY

SPAN_KINDS = frozenset(
    {"ESTIMATED_BLOCK_LOCAL", "SOURCE_ABSOLUTE", "OOXML_LOCAL", "NONE"}
)

WRITER_ADAPTERS = frozenset(
    {
        "DOCX_PARAGRAPH_WRITER",
        "DOCX_TABLE_CELL_WRITER",
        "MARKDOWN_BLOCK_WRITER",
        "UNSUPPORTED_WRITER",
    }
)


@dataclass
class PatchContractInput:
    patch_contract_input_id: str
    change_id: str
    patch_intent_id: str
    patch_target_candidate_id: str
    primary_location_id: str
    document_id: str
    requested_operation: str
    proposed_text: str | None
    intent_status: str
    target_status: str
    location_status: str
    template_id: str | None
    template_node_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional observational context
    physical_candidate_id: str | None = None
    location_type: str | None = None
    section_id: str | None = None
    block_id: str | None = None
    paragraph_index: int | None = None
    list_index: int | None = None
    table_index: int | None = None
    cell_coordinate: tuple[int, int] | None = None
    character_span: tuple[int, int] | None = None
    span_kind: str = "NONE"
    original_text: str | None = None
    source_format: str = "markdown"
    heading_path: list[str] = field(default_factory=list)
    # Fingerprint observation inputs
    observed_document_fingerprint: str | None = None
    expected_document_fingerprint: str | None = None
    observed_block_fingerprint: str | None = None
    expected_block_fingerprint: str | None = None
    observed_original_text_fingerprint: str | None = None
    expected_original_text_fingerprint: str | None = None
    fingerprint_status: str = "AVAILABLE"  # AVAILABLE | NOT_AVAILABLE | STALE
    human_approval_present: bool = False
    link_metadata: dict[str, Any] | None = None
    # Reference integrity flags for INVALID fixtures
    intent_reference_valid: bool = True
    target_reference_valid: bool = True
    primary_reference_valid: bool = True
    document_exists: bool = True
    expected_document_id: str | None = None
    external_activation_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.cell_coordinate is not None:
            d["cell_coordinate"] = list(self.cell_coordinate)
        if self.character_span is not None:
            d["character_span"] = list(self.character_span)
        return d


@dataclass
class PatchPrecondition:
    precondition_id: str
    patch_contract_id: str
    precondition_type: str
    expected_value: Any
    observed_value: Any
    precondition_status: str
    reason_codes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PatchOperationPlan:
    operation_plan_id: str
    patch_contract_id: str
    operation: str
    document_id: str
    location_type: str | None
    section_id: str | None
    block_id: str | None
    paragraph_index: int | None
    list_index: int | None
    table_index: int | None
    cell_coordinate: tuple[int, int] | None
    character_span: tuple[int, int] | None
    span_kind: str
    original_text: str | None
    proposed_text: str | None
    normalized_original_text: str | None
    normalized_proposed_text: str | None
    writer_supported: bool
    template_allowed: bool
    activation_allowed: bool = False
    actual_writer_called: bool = False
    actual_document_changed: bool = False
    writer_adapter: str = "UNSUPPORTED_WRITER"
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.cell_coordinate is not None:
            d["cell_coordinate"] = list(self.cell_coordinate)
        if self.character_span is not None:
            d["character_span"] = list(self.character_span)
        return d


@dataclass
class PatchContract:
    patch_contract_id: str
    patch_contract_input_id: str
    change_id: str
    patch_intent_id: str
    patch_target_candidate_id: str
    primary_location_id: str
    document_id: str
    contract_status: str
    requested_operation: str
    operation_plan_id: str | None
    precondition_ids: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    contract_executable: bool = False
    activation_allowed: bool = False
    actual_patch_created: bool = False
    actual_document_changed: bool = False
    actual_writer_called: bool = False
    actual_docx_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WriterPlanPreview:
    writer_plan_preview_id: str
    patch_contract_id: str
    writer_adapter: str
    intended_action: str
    intended_location: dict[str, Any]
    intended_payload: dict[str, Any]
    preview_status: str
    blocking_reasons: list[str] = field(default_factory=list)
    would_modify_document: bool = False
    contract_executable: bool = False
    activation_allowed: bool = False
    actual_writer_called: bool = False
    actual_document_changed: bool = False
    actual_patch_created: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
