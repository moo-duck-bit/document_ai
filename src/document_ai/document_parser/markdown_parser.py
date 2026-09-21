# -*- coding: utf-8 -*-
"""PR-20: Markdown → DocumentModel (rule-based, no LLM)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_ai.document_parser.structure import (
    DocumentModel,
    ListModel,
    ParagraphModel,
    SectionModel,
    TableModel,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_UL_RE = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_OL_RE = re.compile(r"^(\s*)\d+[.)]\s+(.+)$")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")


def _slug(text: str, order: int) -> str:
    raw = re.sub(r"[^\w가-힣]+", "_", (text or "").strip().lower())
    raw = re.sub(r"_+", "_", raw).strip("_") or "section"
    return f"sec_{order:03d}_{raw[:48]}"


def _parse_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def parse_markdown_text(
    text: str,
    *,
    document_id: str = "md_document",
    document_type: str = "unknown",
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DocumentModel:
    """Parse Markdown into a hierarchical DocumentModel."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[SectionModel] = []
    stack: list[tuple[int, str]] = []  # (level, section_id)
    current: SectionModel | None = None
    order = 0
    para_i = 0
    table_i = 0
    list_i = 0
    doc_title = title or ""
    i = 0
    pending_list: ListModel | None = None

    def _flush_list() -> None:
        nonlocal pending_list, list_i
        if pending_list is not None and current is not None:
            current.lists.append(pending_list)
            pending_list = None
            list_i += 1

    def _ensure_root() -> SectionModel:
        nonlocal current, order
        if current is not None:
            return current
        order += 1
        sid = _slug("document", order)
        current = SectionModel(
            section_id=sid,
            heading=doc_title or "Document",
            heading_level=0,
            parent=None,
            order=order,
        )
        sections.append(current)
        stack.clear()
        stack.append((0, sid))
        return current

    while i < len(lines):
        line = lines[i]
        hm = _HEADING_RE.match(line)
        if hm:
            _flush_list()
            level = len(hm.group(1))
            heading = hm.group(2).strip()
            if level == 1 and not doc_title:
                doc_title = heading
            order += 1
            sid = _slug(heading, order)
            # pop stack to parent of this level
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            if parent:
                for s in sections:
                    if s.section_id == parent and sid not in s.children:
                        s.children.append(sid)
            sec = SectionModel(
                section_id=sid,
                heading=heading,
                heading_level=level,
                parent=parent,
                order=order,
            )
            sections.append(sec)
            stack.append((level, sid))
            current = sec
            i += 1
            continue

        # table block
        if "|" in line and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            _flush_list()
            cur = _ensure_root()
            headers = _parse_table_row(line)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_parse_table_row(lines[i]))
                i += 1
            table_i += 1
            cur.tables.append(
                TableModel(
                    table_id=f"tbl_{table_i:03d}",
                    headers=headers,
                    rows=rows,
                    order=table_i,
                )
            )
            continue

        ul = _UL_RE.match(line)
        ol = _OL_RE.match(line)
        if ul or ol:
            cur = _ensure_root()
            item = (ul or ol).group(2).strip()  # type: ignore[union-attr]
            ordered = bool(ol)
            if pending_list is None or pending_list.ordered != ordered:
                _flush_list()
                list_i += 1
                pending_list = ListModel(
                    list_id=f"lst_{list_i:03d}",
                    items=[item],
                    ordered=ordered,
                    order=list_i,
                )
            else:
                pending_list.items.append(item)
            i += 1
            continue

        _flush_list()
        stripped = line.strip()
        if stripped:
            cur = _ensure_root()
            para_i += 1
            cur.paragraphs.append(
                ParagraphModel(
                    paragraph_id=f"p_{para_i:03d}",
                    text=stripped,
                    order=para_i,
                )
            )
        i += 1

    _flush_list()
    return DocumentModel(
        document_id=document_id,
        document_type=document_type,
        title=doc_title or document_id,
        source_format="markdown",
        metadata=dict(metadata or {}),
        sections=sections,
    )


def parse_markdown_file(
    path: str | Path,
    *,
    document_id: str | None = None,
    document_type: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> DocumentModel:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_markdown_text(
        text,
        document_id=document_id or p.stem,
        document_type=document_type,
        metadata={**(metadata or {}), "source_path": str(p)},
    )
