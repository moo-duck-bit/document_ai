# -*- coding: utf-8 -*-
"""PR-25: Controlled Writer schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

APPROVAL_DECISIONS = frozenset(
    {"APPROVED", "REJECTED", "AUTO_APPROVED", "MANUAL_REQUIRED"}
)

WRITER_RESULT_STATUSES = frozenset(
    {
        "APPLIED",
        "SKIPPED",
        "REJECTED",
        "BLOCKED",
        "FAILED",
        "ROLLED_BACK",
    }
)

OPERATIONS = frozenset({"UPDATE", "REPLACE", "ADD", "DELETE", "LINK"})


@dataclass
class ApprovalDecision:
    approval_id: str
    patch_contract_id: str
    decision: str
    approved_by: str | None = None
    approved_at: str | None = None
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ControlledWriterInput:
    writer_input_id: str
    patch_contract_id: str
    change_id: str
    document_id: str
    requested_operation: str
    proposed_text: str | None
    original_text: str | None
    contract_status: str
    writer_adapter: str
    source_path: str
    location_type: str | None = None
    section_id: str | None = None
    block_id: str | None = None
    paragraph_index: int | None = None
    list_index: int | None = None
    table_index: int | None = None
    cell_coordinate: tuple[int, int] | None = None
    character_span: tuple[int, int] | None = None
    span_kind: str = "NONE"
    source_format: str = "markdown"
    expected_fingerprint: str | None = None
    link_metadata: dict[str, Any] | None = None
    approval: ApprovalDecision | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.cell_coordinate is not None:
            d["cell_coordinate"] = list(self.cell_coordinate)
        if self.character_span is not None:
            d["character_span"] = list(self.character_span)
        if self.approval is not None:
            d["approval"] = self.approval.to_dict()
        return d


@dataclass
class WriterPlan:
    writer_plan_id: str
    patch_contract_id: str
    writer_adapter: str
    operation: str
    source_path: str
    copy_path: str
    intended_location: dict[str, Any]
    intended_payload: dict[str, Any]
    activation_allowed: bool
    blocking_reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackPoint:
    rollback_id: str
    patch_contract_id: str
    copy_path: str
    snapshot_path: str
    snapshot_fingerprint: str
    created_before_write: bool = True
    rolled_back: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiffResult:
    diff_id: str
    patch_contract_id: str
    before_text: str
    after_text: str
    changed_blocks: list[str] = field(default_factory=list)
    changed_paragraphs: list[str] = field(default_factory=list)
    changed_tables: list[str] = field(default_factory=list)
    operation_count: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WriterResult:
    writer_result_id: str
    patch_contract_id: str
    writer_plan_id: str
    result_status: str
    source_path: str
    copy_path: str
    original_unchanged: bool
    copy_modified: bool
    operation: str
    reason_codes: list[str] = field(default_factory=list)
    diff_id: str | None = None
    rollback_id: str | None = None
    actual_writer_called: bool = False
    actual_document_changed: bool = False  # True only if COPY changed
    actual_original_changed: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
