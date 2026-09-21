# -*- coding: utf-8 -*-
"""PR-23: Physical locator schemas (observational)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

LOCATION_TYPES = frozenset(
    {"SECTION", "HEADING", "PARAGRAPH", "LIST", "TABLE", "TABLE_CELL", "BLOCK"}
)
LOCATION_STATUSES = frozenset({"RESOLVED", "REVIEW", "UNRESOLVED", "INVALID"})


@dataclass
class PhysicalLocatorInput:
    physical_locator_input_id: str
    patch_target_candidate_id: str
    document_id: str
    template_id: str | None
    template_node_id: str | None
    section_id: str | None
    field_id: str | None
    target_status: str
    heading_path_hint: list[str] = field(default_factory=list)
    field_label_hint: str | None = None
    preferred_location_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PhysicalLocationCandidate:
    physical_candidate_id: str
    patch_target_candidate_id: str
    document_id: str
    template_id: str | None
    template_node_id: str | None
    location_type: str
    section_id: str | None
    heading_path: list[str] = field(default_factory=list)
    paragraph_index: int | None = None
    list_index: int | None = None
    table_index: int | None = None
    cell_coordinate: tuple[int, int] | None = None
    block_id: str | None = None
    character_span: tuple[int, int] | None = None
    # ESTIMATED_BLOCK_LOCAL | SOURCE_ABSOLUTE | OOXML_LOCAL | NONE
    span_kind: str = "NONE"
    location_score: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    rank: int = 0
    score_components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.cell_coordinate is not None:
            d["cell_coordinate"] = list(self.cell_coordinate)
        if self.character_span is not None:
            d["character_span"] = list(self.character_span)
        return d


@dataclass
class PrimaryPhysicalLocation:
    primary_location_id: str
    patch_target_candidate_id: str
    document_id: str
    physical_candidate_id: str | None
    location_status: str
    location_type: str | None = None
    section_id: str | None = None
    heading_path: list[str] = field(default_factory=list)
    location_score: float = 0.0
    top1_score: float | None = None
    top2_score: float | None = None
    score_margin: float | None = None
    candidate_count: int = 0
    reason_codes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    actual_docx_changed: bool = False
    actual_writer_called: bool = False
    actual_patch_created: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
