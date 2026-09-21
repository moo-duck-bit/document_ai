# -*- coding: utf-8 -*-
"""Workflow state and record schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

WorkflowState = Literal[
    "CREATED",
    "UPLOADED",
    "ANALYZING",
    "REVIEW_READY",
    "WAITING_APPROVAL",
    "WRITING",
    "VALIDATING",
    "COMPLETED",
    "FAILED",
]

WORKFLOW_STATES: tuple[str, ...] = (
    "CREATED",
    "UPLOADED",
    "ANALYZING",
    "REVIEW_READY",
    "WAITING_APPROVAL",
    "WRITING",
    "VALIDATING",
    "COMPLETED",
    "FAILED",
)

DocumentSetKind = Literal["ec_sw", "general_report", "business_proposal"]

ItemDecision = Literal["PENDING", "APPROVED", "REJECTED", "BLOCKED"]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ApprovalItem:
    item_id: str
    document_id: str
    node_id: str | None = None
    decision: str = "PENDING"
    reason: str = ""
    decided_by: str | None = None
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentResultRow:
    document_id: str
    status: str
    review: str = ""
    applied: int = 0
    rejected: int = 0
    blocked: int = 0
    validation: str = "N/A"
    diff_available: bool = False
    download: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowRecord:
    workflow_id: str
    document_set: str
    state: str = "CREATED"
    change_request: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    documents: list[dict[str, Any]] = field(default_factory=list)
    impacted_documents: list[str] = field(default_factory=list)
    review_required: list[dict[str, Any]] = field(default_factory=list)
    patch_candidates: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    writer_result: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    result_rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def touch(self, state: str | None = None) -> None:
        if state:
            self.state = state
        self.updated_at = utc_now()

    def add_event(self, event: str, detail: str = "") -> None:
        self.timeline.append(
            {"at": utc_now(), "state": self.state, "event": event, "detail": detail}
        )
