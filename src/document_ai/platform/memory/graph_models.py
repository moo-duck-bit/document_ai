from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class NodeType(StrEnum):
    REQUIREMENT = "Requirement"
    DESIGN_ITEM = "DesignItem"
    SECURITY_CONTROL = "SecurityControl"
    SECURITY_TEST = "SecurityTest"
    DOCUMENT = "Document"


class EdgeType(StrEnum):
    TRACES_TO = "TRACES_TO"
    IMPLEMENTS = "IMPLEMENTS"
    VERIFIES = "VERIFIES"
    BELONGS_TO = "BELONGS_TO"


def make_node_id(case_id: str, node_type: NodeType, normalized_id: str) -> str:
    slug = node_type.value.lower().replace(" ", "_")
    return f"{case_id}:{slug}:{normalized_id}"


@dataclass
class GraphNode:
    id: str
    type: NodeType
    label: str
    normalized_id: str
    case_id: str
    source_file: str = ""
    document_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "normalized_id": self.normalized_id,
            "case_id": self.case_id,
            "source_file": self.source_file,
            "document_type": self.document_type,
            "metadata": self.metadata,
            "raw_text": self.raw_text,
        }


@dataclass
class GraphEdge:
    source: str
    target: str
    type: EdgeType
    confidence: float = 1.0
    evidence: str = ""
    source_file: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_file": self.source_file,
            "metadata": self.metadata,
        }


@dataclass
class GraphStats:
    node_count: int = 0
    edge_count: int = 0
    orphan_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)
