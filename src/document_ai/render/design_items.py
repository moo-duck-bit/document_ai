from __future__ import annotations

import re
from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.req_ids import normalize_requirement_id as normalize_req_id
from document_ai.learn.docx_io import iter_blocks, table_matrix
from document_ai.render.requirements import _req_id_from_table, _set_description_cell

REQ_PARAGRAPH = re.compile(r"^Req\.\s*(\d+)\.?\s*(.*)$", re.IGNORECASE)
DESIGN_LABELS = {"목적", "기준", "설명"}


def _find_req_table(doc: Document, req_id: str) -> Table | None:
    for block in iter_blocks(doc):
        if isinstance(block, Table) and _req_id_from_table(block) == req_id:
            return block
    return None


def _find_req_paragraph_section(doc: Document, req_id: str) -> tuple[Paragraph | None, list[Paragraph]]:
    target = normalize_req_id(req_id)
    heading: Paragraph | None = None
    content: list[Paragraph] = []
    capturing = False

    for block in iter_blocks(doc):
        if not isinstance(block, Paragraph):
            if capturing:
                break
            continue

        text = block.text.strip()
        if not text:
            continue

        match = REQ_PARAGRAPH.match(text)
        if match:
            current = normalize_req_id(f"Req. {match.group(1)}")
            if capturing:
                break
            if current == target:
                heading = block
                capturing = True
            continue

        if capturing:
            content.append(block)

    return heading, content


def _patch_req_table(table: Table, design_description: str | None, fields: dict[str, str]) -> bool:
    patched = False

    if design_description:
        _set_description_cell(table, design_description, overwrite=True)
        patched = True

    if not fields:
        return patched

    for row in table.rows[1:]:
        if len(row.cells) < 2:
            continue
        label = row.cells[0].text.strip()
        if label in fields:
            row.cells[1].text = fields[label]
            patched = True
        elif label in DESIGN_LABELS:
            for key, value in fields.items():
                if key.lower() == label.lower() or key == label:
                    row.cells[1].text = value
                    patched = True
    return patched or bool(design_description)


def _patch_req_paragraph_section(
    heading: Paragraph | None,
    content: list[Paragraph],
    design_description: str | None,
) -> bool:
    if not design_description:
        return False
    if content:
        content[0].text = design_description
        for para in content[1:]:
            para.text = ""
        return True
    if heading is not None:
        suffix = heading.text.strip()
        if REQ_PARAGRAPH.match(suffix):
            match = REQ_PARAGRAPH.match(suffix)
            base = f"Req. {int(match.group(1))}" if match else suffix
            title = match.group(2).strip() if match else ""
            heading.text = f"{base}. {title}\n{design_description}" if title else f"{base}\n{design_description}"
            return True
    return False


def _insert_req_paragraph_section(
    doc: Document,
    req_id: str,
    design_description: str,
    title_suffix: str = "",
) -> None:
    heading_text = f"{req_id} {title_suffix}".strip()
    doc.add_paragraph(heading_text)
    doc.add_paragraph(design_description)


def patch_mddr_design_items(doc: Document, design_changes: list[dict[str, Any]]) -> list[str]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in design_changes:
        req_id = normalize_req_id(item.get("req_id", ""))
        if req_id:
            by_id[req_id] = item

    patched: list[str] = []
    for req_id, change in by_id.items():
        design_description = change.get("design_description")
        fields = change.get("fields") or {}

        table = _find_req_table(doc, req_id)
        if table and _patch_req_table(table, design_description, fields):
            patched.append(req_id)
            continue

        heading, content = _find_req_paragraph_section(doc, req_id)
        if _patch_req_paragraph_section(heading, content, design_description):
            patched.append(req_id)
            continue

        if design_description:
            _insert_req_paragraph_section(
                doc,
                req_id,
                design_description,
                change.get("title_suffix", ""),
            )
            patched.append(req_id)

    return patched
