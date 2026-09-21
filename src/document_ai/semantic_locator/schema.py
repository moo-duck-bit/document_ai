# -*- coding: utf-8 -*-
"""PR-21: Semantic locator schemas (observational)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SemanticLocatorInput:
    document_id: str
    locator_candidate_id: str
    template_id: str | None = None
    heading_path: list[str] = field(default_factory=list)
    heading_text: str = ""
    section_name: str = ""
    field_label: str | None = None
    exact_text: str | None = None
    candidate_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TemplateNodeCandidate:
    template_node_id: str
    template_id: str
    section_id: str
    field_id: str
    display_name: str
    locator_hints: dict[str, Any] = field(default_factory=dict)
    source_requirement_id: str | None = None
    allowed_operations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticMatchResult:
    semantic_match_id: str
    document_id: str
    locator_candidate_id: str
    template_id: str | None
    template_node_id: str | None
    rule_score: float
    semantic_score: float
    combined_score: float
    rank: int
    match_status: str  # MATCHED | REVIEW | UNMAPPED | INVALID
    reason_codes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    ambiguity_status: str = "CLEAR"  # CLEAR | AMBIGUOUS
    score_margin: float | None = None
    top_1_score: float | None = None
    top_2_score: float | None = None
    candidate_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
