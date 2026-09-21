# -*- coding: utf-8 -*-
"""PR-20: Normalize in-memory objects and clean DocumentModel trees."""

from __future__ import annotations

import re
from typing import Any

from document_ai.document_parser.structure import (
    DocumentModel,
    ListModel,
    ParagraphModel,
    SectionModel,
    TableModel,
)


def _slug(text: str, order: int) -> str:
    raw = re.sub(r"[^\w가-힣]+", "_", (text or "").strip().lower())
    raw = re.sub(r"_+", "_", raw).strip("_") or "section"
    return f"sec_{order:03d}_{raw[:48]}"


def document_from_object(
    obj: dict[str, Any],
    *,
    document_id: str | None = None,
    document_type: str | None = None,
) -> DocumentModel:
    """Build DocumentModel from an in-memory nested dict (PR-19 sample shape OK)."""
    title = str(obj.get("title") or document_id or "document")
    dtype = document_type or str(obj.get("document_type") or "unknown")
    did = document_id or str(obj.get("sample_document_id") or obj.get("document_id") or "object_doc")
    sections_obj = obj.get("sections") or {}
    sections: list[SectionModel] = []
    order = 0

    # root
    order += 1
    root_id = _slug("document", order)
    root = SectionModel(
        section_id=root_id,
        heading=title,
        heading_level=0,
        parent=None,
        order=order,
    )
    sections.append(root)

    if isinstance(sections_obj, dict):
        items = list(sections_obj.items())
    elif isinstance(sections_obj, list):
        items = []
        for idx, sec in enumerate(sections_obj):
            if isinstance(sec, dict):
                key = str(sec.get("section_id") or sec.get("heading") or f"section_{idx}")
                items.append((key, sec))
    else:
        items = []

    for key, sec in items:
        if not isinstance(sec, dict):
            continue
        order += 1
        heading = str(sec.get("title") or sec.get("heading") or key)
        sid = _slug(heading, order)
        root.children.append(sid)
        section = SectionModel(
            section_id=sid,
            heading=heading,
            heading_level=1,
            parent=root_id,
            order=order,
            metadata={"source_key": key},
        )
        # body / fields → paragraphs
        para_i = 0
        for field_key in (
            "body",
            "approach",
            "data_sources",
            "limitations",
            "summary",
            "mitigation",
            "schedule",
        ):
            val = sec.get(field_key)
            if isinstance(val, str) and val.strip():
                para_i += 1
                section.paragraphs.append(
                    ParagraphModel(
                        paragraph_id=f"p_{para_i:03d}",
                        text=val.strip(),
                        order=para_i,
                        metadata={"field": field_key},
                    )
                )
        # list-like fields
        list_i = 0
        for field_key in (
            "key_findings",
            "recommendations",
            "differentiators",
            "phases",
            "deliverables",
            "items",
            "assumptions",
        ):
            val = sec.get(field_key)
            if isinstance(val, list) and val:
                list_i += 1
                section.lists.append(
                    ListModel(
                        list_id=f"lst_{list_i:03d}",
                        items=[str(x) for x in val],
                        ordered=False,
                        order=list_i,
                        metadata={"field": field_key},
                    )
                )
        # tables field
        tables = sec.get("tables")
        if isinstance(tables, list):
            for ti, tbl in enumerate(tables, start=1):
                if isinstance(tbl, dict):
                    section.tables.append(
                        TableModel(
                            table_id=f"tbl_{ti:03d}",
                            headers=list(tbl.get("headers") or []),
                            rows=list(tbl.get("rows") or []),
                            order=ti,
                        )
                    )
        sections.append(section)

    return DocumentModel(
        document_id=did,
        document_type=dtype,
        title=title,
        source_format="object",
        metadata={"source": "in_memory_object"},
        sections=sections,
    )


def normalize_document(doc: DocumentModel) -> DocumentModel:
    """Deterministic cleanup: sort children, strip empty texts, rebuild child links."""
    by_id = {s.section_id: s for s in doc.sections}
    # rebuild children from parent pointers
    for s in doc.sections:
        s.children = []
    for s in sorted(doc.sections, key=lambda x: x.order):
        if s.parent and s.parent in by_id:
            parent = by_id[s.parent]
            if s.section_id not in parent.children:
                parent.children.append(s.section_id)
    for s in doc.sections:
        s.heading = (s.heading or "").strip()
        s.paragraphs = [
            ParagraphModel(
                paragraph_id=p.paragraph_id,
                text=(p.text or "").strip(),
                order=p.order,
                metadata=dict(p.metadata),
            )
            for p in sorted(s.paragraphs, key=lambda x: x.order)
            if (p.text or "").strip()
        ]
        s.lists = sorted(s.lists, key=lambda x: x.order)
        s.tables = sorted(s.tables, key=lambda x: x.order)
        s.children = list(s.children)
    doc.sections = sorted(doc.sections, key=lambda x: x.order)
    doc.title = (doc.title or "").strip() or doc.document_id
    return doc


def build_section_tree(doc: DocumentModel) -> dict[str, Any]:
    """Nested tree view for artifact (deterministic)."""
    by_id = {s.section_id: s for s in doc.sections}
    roots = [s for s in doc.sections if not s.parent or s.parent not in by_id]

    def _node(sec: SectionModel) -> dict[str, Any]:
        return {
            "section_id": sec.section_id,
            "heading": sec.heading,
            "heading_level": sec.heading_level,
            "paragraph_count": len(sec.paragraphs),
            "table_count": len(sec.tables),
            "list_count": len(sec.lists),
            "children": [
                _node(by_id[cid]) for cid in sec.children if cid in by_id
            ],
        }

    return {
        "document_id": doc.document_id,
        "title": doc.title,
        "roots": [_node(r) for r in sorted(roots, key=lambda x: x.order)],
    }
