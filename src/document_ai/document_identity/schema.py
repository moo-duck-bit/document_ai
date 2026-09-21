# -*- coding: utf-8 -*-
"""Document identity / pack routing schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DecisionStatus = Literal["AUTO_SELECTED", "REVIEW_REQUIRED", "UNRESOLVED", "INVALID"]
RoutingStatus = Literal["ROUTED", "REVIEW_REQUIRED", "UNRESOLVED", "INVALID"]
CandidateStatus = Literal["CANDIDATE", "STRONG_CANDIDATE", "CONFLICTED", "INVALID"]


@dataclass
class DocumentSignal:
    signal_id: str
    document_source_id: str
    signal_type: str
    signal_value: str
    normalized_value: str = ""
    confidence: float = 0.0
    source: str = ""
    source_locator: dict[str, Any] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)
    independent_group: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentIdentityCandidate:
    candidate_id: str
    source_document_id: str
    canonical_document_id: str
    short_id: str | None = None
    document_type: str | None = None
    document_role: str | None = None
    domain_pack_id: str | None = None
    template_id: str | None = None
    score: float = 0.0
    rank: int = 0
    rank_tier: int = 5
    status: CandidateStatus = "CANDIDATE"
    reason_codes: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentIdentityDecision:
    decision_id: str
    source_document_id: str
    canonical_document_id: str | None
    short_id: str | None = None
    document_type: str | None = None
    document_role: str | None = None
    domain_pack_id: str | None = None
    template_id: str | None = None
    decision_status: DecisionStatus = "UNRESOLVED"
    top_score: float = 0.0
    second_score: float = 0.0
    score_margin: float = 0.0
    rank_tier: int = 5
    reason_codes: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    human_review_required: bool = True
    auto_selected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DomainPackRoutingDecision:
    routing_id: str
    source_document_id: str
    selected_pack_id: str | None
    candidate_pack_ids: list[str] = field(default_factory=list)
    routing_status: RoutingStatus = "UNRESOLVED"
    score: float = 0.0
    score_margin: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    human_review_required: bool = True
    actual_pack_invoked: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
