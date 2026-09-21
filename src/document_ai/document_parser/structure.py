# -*- coding: utf-8 -*-
"""PR-20: Shared document structure models (observational)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ParagraphModel:
    paragraph_id: str
    text: str
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TableModel:
    table_id: str
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ListModel:
    list_id: str
    items: list[str] = field(default_factory=list)
    ordered: bool = False
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SectionModel:
    section_id: str
    heading: str
    heading_level: int
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    paragraphs: list[ParagraphModel] = field(default_factory=list)
    tables: list[TableModel] = field(default_factory=list)
    lists: list[ListModel] = field(default_factory=list)
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "heading_level": self.heading_level,
            "parent": self.parent,
            "children": list(self.children),
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "tables": [t.to_dict() for t in self.tables],
            "lists": [lst.to_dict() for lst in self.lists],
            "order": self.order,
            "metadata": dict(self.metadata),
        }


@dataclass
class DocumentModel:
    document_id: str
    document_type: str
    title: str
    source_format: str  # markdown | docx | object
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[SectionModel] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_type": self.document_type,
            "title": self.title,
            "source_format": self.source_format,
            "metadata": dict(self.metadata),
            "sections": [s.to_dict() for s in self.sections],
        }


@dataclass
class LocatorCandidate:
    candidate_id: str
    section_id: str
    heading_path: list[str]
    section_name: str
    heading_text: str
    locator_type: str  # heading_path | section_name | heading_text
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
