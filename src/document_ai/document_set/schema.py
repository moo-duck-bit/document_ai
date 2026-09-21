# -*- coding: utf-8 -*-
"""Thin Generic Core schemas for document-set expansion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DocumentRole = Literal[
    "requirements",
    "design",
    "traceability",
    "verification_plan",
    "development_plan",
    "process",
    "test_result",
    "security_verification_report",
    "general_report",
    "custom",
]

NodeType = Literal[
    "SECTION",
    "PARAGRAPH",
    "TABLE",
    "TABLE_ROW",
    "TABLE_CELL",
    "LIST",
    "REQUIREMENT",
    "DESIGN_ITEM",
    "CUSTOM",
]

ColumnRoleStatus = Literal["CONFIRMED", "CANDIDATE", "UNKNOWN", "REVIEW_REQUIRED"]

ChangeCandidateStatus = Literal[
    "PATCH_CANDIDATE",
    "REVIEW_REQUIRED",
    "UNRELATED",
    "INVALID",
]


@dataclass
class DocumentDescriptor:
    document_id: str
    short_id: str
    document_type: str
    document_role: str
    source_path: str
    source_format: str = "docx"
    template_id: str | None = None
    domain_pack_id: str = "ec_sw_v1"
    priority: int = 100
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentNode:
    node_id: str
    document_id: str
    document_type: str
    document_role: str
    node_type: str
    display_name: str
    text: str = ""
    normalized_text: str = ""
    order: int = 0
    section_id: str | None = None
    block_id: str | None = None
    field_id: str | None = None
    source_locator: dict[str, Any] = field(default_factory=dict)
    source_identifiers: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RelationHint:
    relation_hint_id: str
    source_node_id: str
    relation_type: str  # TRACE_ROW_CONTAINS | REFERENCES | UNKNOWN
    target_identifiers: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChangeCandidate:
    candidate_id: str
    node_id: str
    document_id: str
    status: str
    matched_requirement_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    human_review_required: bool = True
    patch_preview: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
