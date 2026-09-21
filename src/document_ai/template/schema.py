# -*- coding: utf-8 -*-
"""PR-18: Template schema definitions (observational)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

VALID_OPERATIONS = frozenset(
    {"ADD", "UPDATE", "DELETE", "CONSTRAIN", "REPLACE", "LINK", "NO_ACTION", "REVIEW_REQUIRED"}
)

WRITER_SUPPORTED_OPERATIONS = frozenset({"UPDATE", "CONSTRAIN", "REPLACE"})


def slugify_requirement_id(req_id: str | None) -> str | None:
    """Deterministic slug for requirement ids. Returns None if empty."""
    if req_id is None:
        return None
    raw = str(req_id).strip()
    if not raw:
        return None
    s = raw.lower()
    s = s.replace("req.", "req_")
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or None


@dataclass
class LocatorHints:
    strategies: list[str] = field(default_factory=list)
    source_requirement_id: str | None = None
    source_field: str | None = None
    heading_path: list[str] = field(default_factory=list)
    heading_text: str | None = None
    section_id: str | None = None
    table_header: str | None = None
    field_label: str | None = None
    exact_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OperationPolicy:
    allowed_operations: list[str] = field(default_factory=list)
    review_required_operations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FieldDefinition:
    field_id: str
    display_name: str
    field_type: str = "custom"
    required: bool = False
    repeatable: bool = False
    editable: bool = True
    allowed_operations: list[str] = field(default_factory=list)
    content_type: str = "text"
    locator_hints: LocatorHints = field(default_factory=LocatorHints)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class SectionDefinition:
    section_id: str
    display_name: str
    section_type: str = "section"
    parent_section_id: str | None = None
    order: int = 0
    repeatable: bool = False
    required: bool = False
    fields: list[FieldDefinition] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "display_name": self.display_name,
            "section_type": self.section_type,
            "parent_section_id": self.parent_section_id,
            "order": self.order,
            "repeatable": self.repeatable,
            "required": self.required,
            "fields": [f.to_dict() for f in self.fields],
            "metadata": dict(self.metadata),
        }


@dataclass
class TemplateDefinition:
    template_id: str
    schema_version: str
    document_type: str
    display_name: str
    description: str = ""
    language: str = "ko"
    source_format: str = "docx"
    sections: list[SectionDefinition] = field(default_factory=list)
    allowed_operations: list[str] = field(default_factory=list)
    operation_policy: OperationPolicy = field(default_factory=OperationPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "schema_version": self.schema_version,
            "document_type": self.document_type,
            "display_name": self.display_name,
            "description": self.description,
            "language": self.language,
            "source_format": self.source_format,
            "sections": [s.to_dict() for s in self.sections],
            "allowed_operations": list(self.allowed_operations),
            "operation_policy": self.operation_policy.to_dict(),
            "metadata": dict(self.metadata),
            "operation_capability": {
                op: {
                    "template_allowed": op in self.allowed_operations,
                    "writer_supported": op in WRITER_SUPPORTED_OPERATIONS,
                }
                for op in sorted(set(self.allowed_operations) | set(WRITER_SUPPORTED_OPERATIONS))
            },
        }


@dataclass
class TemplateNode:
    template_node_id: str
    template_id: str
    document_type: str
    section_id: str
    field_id: str
    parent_node_id: str | None = None
    node_type: str = "field"
    display_name: str = ""
    order: int = 0
    source_document: str = ""
    source_requirement_id: str | None = None
    source_field: str = ""
    locator_hints: LocatorHints = field(default_factory=LocatorHints)
    allowed_operations: list[str] = field(default_factory=list)
    editable: bool = True
    mapping_status: str = "MAPPED"
    mapping_reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_node_id": self.template_node_id,
            "template_id": self.template_id,
            "document_type": self.document_type,
            "section_id": self.section_id,
            "field_id": self.field_id,
            "parent_node_id": self.parent_node_id,
            "node_type": self.node_type,
            "display_name": self.display_name,
            "order": self.order,
            "source_document": self.source_document,
            "source_requirement_id": self.source_requirement_id,
            "source_field": self.source_field,
            "locator_hints": self.locator_hints.to_dict(),
            "allowed_operations": list(self.allowed_operations),
            "editable": self.editable,
            "mapping_status": self.mapping_status,
            "mapping_reason_codes": list(self.mapping_reason_codes),
            "metadata": dict(self.metadata),
        }


def make_template_node_id(
    template_id: str,
    *,
    requirement_slug: str | None,
    field_id: str,
) -> str:
    """Deterministic node id: {template}.requirements.{req_slug}.{field}."""
    if not requirement_slug:
        raise ValueError("requirement_slug required for deterministic node id")
    return f"{template_id}.requirements.{requirement_slug}.{field_id}"
