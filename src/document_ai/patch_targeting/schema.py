# -*- coding: utf-8 -*-
"""PR-22: Patch targeting schemas (observational)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

REQUESTED_OPERATIONS = frozenset({"UPDATE", "ADD", "DELETE", "LINK"})

INTENT_STATUSES = frozenset({"ELIGIBLE", "REVIEW_REQUIRED", "BLOCKED", "INVALID"})
TARGET_STATUSES = frozenset({"RESOLVED", "REVIEW", "UNRESOLVED", "INVALID"})
PREVIEW_STATUSES = frozenset(
    {"PREVIEW_READY", "PREVIEW_REVIEW", "PREVIEW_BLOCKED", "PREVIEW_INVALID"}
)


@dataclass
class PatchTargetingInput:
    change_id: str
    document_id: str
    locator_candidate_id: str
    semantic_match_id: str
    template_id: str | None
    template_node_id: str | None
    requested_operation: str
    change_type: str = ""
    source_text: str | None = None
    proposed_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Embedded PR-21 primary match context
    match_status: str = "UNMAPPED"
    combined_score: float = 0.0
    score_margin: float | None = None
    ambiguity_status: str = "CLEAR"
    match_reason_codes: list[str] = field(default_factory=list)
    match_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PatchIntent:
    patch_intent_id: str
    change_id: str
    document_id: str
    semantic_match_id: str
    template_id: str | None
    template_node_id: str | None
    requested_operation: str
    intent_status: str
    reason_codes: list[str] = field(default_factory=list)
    source_text: str | None = None
    proposed_text: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    actual_patch_created: bool = False
    actual_document_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PatchTargetCandidate:
    patch_target_candidate_id: str
    patch_intent_id: str
    template_id: str | None
    template_node_id: str | None
    section_id: str | None
    field_id: str | None
    target_status: str
    template_allowed: bool
    writer_supported: bool
    activation_allowed: bool
    match_status: str
    combined_score: float
    score_margin: float | None
    ambiguity_status: str
    reason_codes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActivationPreview:
    preview_id: str
    patch_intent_id: str
    target_candidate_id: str
    preview_status: str
    would_modify_document: bool
    would_require_review: bool
    blocked: bool
    blocking_reasons: list[str] = field(default_factory=list)
    allowed_operations: list[str] = field(default_factory=list)
    requested_operation: str = ""
    actual_document_changed: bool = False
    actual_writer_called: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
