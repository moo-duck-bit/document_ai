# -*- coding: utf-8 -*-
"""Gold row schema for Business Proposal node labeling (Cycle 6)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

NodeEvaluationMode = Literal["REQUIRED", "AMBIGUOUS", "OPTIONAL", "NOT_APPLICABLE"]
ReferenceType = Literal["STABLE", "TEMPLATE", "PHYSICAL", "VIRTUAL"]
PhysicalNodeType = Literal["HEADING", "PARAGRAPH", "TABLE", "NONE"]
LocationType = Literal["SECTION", "TABLE", "PARAGRAPH", "DOCUMENT_LEVEL", "VIRTUAL"]
OperationType = Literal["ADD", "UPDATE", "DELETE", "REPLACE", "REVIEW", "UNKNOWN"]

ALLOWED_MODES = frozenset({"REQUIRED", "AMBIGUOUS", "OPTIONAL", "NOT_APPLICABLE"})
ALLOWED_REFERENCE_TYPES = frozenset({"STABLE", "TEMPLATE", "PHYSICAL", "VIRTUAL"})
ALLOWED_PHYSICAL_NODE_TYPES = frozenset({"HEADING", "PARAGRAPH", "TABLE", "NONE"})
ALLOWED_LOCATION_TYPES = frozenset({"SECTION", "TABLE", "PARAGRAPH", "DOCUMENT_LEVEL", "VIRTUAL"})
ALLOWED_OPERATIONS = frozenset({"ADD", "UPDATE", "DELETE", "REPLACE", "REVIEW", "UNKNOWN"})


@dataclass
class PrimaryReference:
    """A single reference to a gold node, preferring stable > template > physical."""

    reference_type: str = "TEMPLATE"
    stable_node_id: str | None = None
    template_node_id: str | None = None
    document_node_id: str | None = None
    stable_locator: dict[str, Any] = field(default_factory=dict)
    canonical_concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any] | None) -> "PrimaryReference | None":
        if not d:
            return None
        return PrimaryReference(
            reference_type=d.get("reference_type") or "TEMPLATE",
            stable_node_id=d.get("stable_node_id"),
            template_node_id=d.get("template_node_id"),
            document_node_id=d.get("document_node_id"),
            stable_locator=dict(d.get("stable_locator") or {}),
            canonical_concepts=list(d.get("canonical_concepts") or []),
        )


@dataclass
class BusinessProposalGoldRow:
    """One gold node-evaluation label for a single Business Proposal case."""

    case_id: str
    document_id: str
    node_evaluation_mode: str

    primary_reference: dict[str, Any] | None = None
    acceptable_references: list[dict[str, Any]] = field(default_factory=list)
    acceptable_groups: list[list[str]] = field(default_factory=list)

    expected_node_type: str | None = None
    expected_structural_role: str | None = None
    expected_template_node_id: str | None = None
    expected_physical_node_type: str | None = None
    expected_location_type: str | None = None
    expected_operation: str | None = None

    label_rationale: str = ""
    label_source: str = "document_structure_and_change_request"
    labeled_by: str = ""
    labeled_at: str = ""
    label_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "BusinessProposalGoldRow":
        return BusinessProposalGoldRow(
            case_id=d["case_id"],
            document_id=d["document_id"],
            node_evaluation_mode=d["node_evaluation_mode"],
            primary_reference=d.get("primary_reference"),
            acceptable_references=list(d.get("acceptable_references") or []),
            acceptable_groups=[list(g) for g in (d.get("acceptable_groups") or [])],
            expected_node_type=d.get("expected_node_type"),
            expected_structural_role=d.get("expected_structural_role"),
            expected_template_node_id=d.get("expected_template_node_id"),
            expected_physical_node_type=d.get("expected_physical_node_type"),
            expected_location_type=d.get("expected_location_type"),
            expected_operation=d.get("expected_operation"),
            label_rationale=d.get("label_rationale") or "",
            label_source=d.get("label_source") or "document_structure_and_change_request",
            labeled_by=d.get("labeled_by") or "",
            labeled_at=d.get("labeled_at") or "",
            label_confidence=float(d.get("label_confidence") or 0.0),
        )
