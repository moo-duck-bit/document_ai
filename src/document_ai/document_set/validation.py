# -*- coding: utf-8 -*-
"""Validation for thin document-set core."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.document_set.schema import DocumentDescriptor, DocumentNode


def validate_descriptors(
    descriptors: list[DocumentDescriptor],
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    _ = project_root
    issues: list[str] = []
    doc_ids = [d.document_id for d in descriptors]
    short_ids = [d.short_id for d in descriptors]
    if len(doc_ids) != len(set(doc_ids)):
        issues.append("duplicate_document_id")
    if len(short_ids) != len(set(short_ids)):
        issues.append("duplicate_short_id")
    missing: list[str] = []
    for d in descriptors:
        if not Path(d.source_path).is_file():
            missing.append(d.short_id)
            issues.append(f"missing_file:{d.short_id}")
    return {
        "ok": not issues,
        "descriptor_count": len(descriptors),
        "unique_document_ids": len(set(doc_ids)),
        "unique_short_ids": len(set(short_ids)),
        "missing_files": missing,
        "issues": issues,
    }


def validate_nodes(
    nodes: list[DocumentNode],
    *,
    document_id: str | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    node_ids = [n.node_id for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        issues.append("duplicate_node_id")
    if document_id:
        for n in nodes:
            if n.document_id != document_id:
                issues.append(f"document_id_mismatch:{n.node_id}")
                break
    empty_id_rows = sum(
        1
        for n in nodes
        if n.node_type == "TABLE_ROW"
        and not (n.source_identifiers.get("requirement_ids") or [])
        and not (n.source_identifiers.get("design_ids") or [])
        and not (n.source_identifiers.get("test_ids") or [])
    )
    return {
        "ok": not issues,
        "node_count": len(nodes),
        "unique_node_ids": len(set(node_ids)),
        "empty_identifier_rows": empty_id_rows,
        "issues": issues,
    }
