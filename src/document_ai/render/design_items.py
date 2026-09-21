from __future__ import annotations

from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, paragraph_deep_text, table_matrix
from document_ai.learn.extract_design_items import _parse_req_heading
from document_ai.learn.req_ids import normalize_requirement_id as normalize_req_id
from document_ai.render.requirements import _req_id_from_table, _set_description_cell

DESIGN_LABELS = {"목적", "기준", "설명"}


def _find_req_table(doc: Document, req_id: str) -> Table | None:
    target = normalize_req_id(req_id)
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        raw = _req_id_from_table(block)
        if raw and normalize_req_id(raw) == target:
            return block
        header = block.rows[0].cells[0].text.strip() if block.rows else ""
        parsed, _, _ = _parse_req_heading(header)
        if parsed == target:
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

        text = paragraph_deep_text(block) or block.text.strip()
        if not text:
            continue

        current, _, _ = _parse_req_heading(text)
        if current:
            if capturing:
                break
            if current == target:
                heading = block
                capturing = True
                # Body already embedded in this paragraph — no following content paras needed
                if "\n" in text and len(text.split("\n", 1)[1].strip()) > 20:
                    return heading, []
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
        text = paragraph_deep_text(heading) or heading.text.strip()
        req_id, _, suffix = _parse_req_heading(text)
        if not req_id:
            return False
        title = suffix.strip()
        # Keep Mindrium one-paragraph shape: Req. N\n<body>
        heading.text = f"{req_id}\n{design_description}" if not title else f"{req_id} {title}\n{design_description}"
        return True
    return False


def _collect_existing_req_ids(doc: Document) -> set[str]:
    found: set[str] = set()
    for block in iter_blocks(doc):
        if isinstance(block, Table):
            raw = _req_id_from_table(block)
            rid = normalize_req_id(raw) if raw else None
            if not rid and block.rows:
                rid, _, _ = _parse_req_heading(block.rows[0].cells[0].text.strip())
            if rid:
                found.add(rid)
            continue
        if isinstance(block, Paragraph):
            text = paragraph_deep_text(block) or block.text.strip()
            rid, _, _ = _parse_req_heading(text)
            if rid:
                found.add(rid)
    return found


def _insert_req_paragraph_section(
    doc: Document,
    req_id: str,
    design_description: str,
    title_suffix: str = "",
) -> None:
    normalized = normalize_req_id(req_id) or req_id
    suffix = title_suffix.strip()
    heading_text = f"{normalized} {suffix}".strip() if suffix else normalized
    doc.add_paragraph(f"{heading_text}\n{design_description}")


def consolidate_mddr_design_paragraphs(doc: Document) -> int:
    """Merge split Req heading + body paragraphs into one block (Mindrium style)."""
    paragraphs = [b for b in iter_blocks(doc) if isinstance(b, Paragraph)]
    merged = 0
    i = 0
    while i < len(paragraphs) - 1:
        text = (paragraph_deep_text(paragraphs[i]) or paragraphs[i].text).strip()
        req_id, _, suffix = _parse_req_heading(text.split("\n", 1)[0].strip())
        if not req_id:
            i += 1
            continue
        if "\n" in text and len(text.split("\n", 1)[1].strip()) > 20:
            i += 1
            continue
        nxt = (paragraph_deep_text(paragraphs[i + 1]) or paragraphs[i + 1].text).strip()
        if not nxt or _parse_req_heading(nxt)[0] or nxt in DESIGN_LABELS:
            i += 1
            continue
        paragraphs[i].text = f"{req_id}\n{nxt}"
        paragraphs[i + 1].text = ""
        merged += 1
        i += 2
    return merged


def fill_thin_mddr_design_headings(doc: Document, design_changes: list[dict[str, Any]]) -> int:
    """Fill template placeholder headings (e.g. Req.9) that were not patched."""
    by_id: dict[str, str] = {}
    for item in design_changes:
        req_id = normalize_req_id(item.get("req_id", ""))
        body = item.get("design_description") or item.get("title_suffix")
        if req_id and body:
            by_id[req_id] = body

    filled = 0
    for block in iter_blocks(doc):
        if not isinstance(block, Paragraph):
            continue
        text = (paragraph_deep_text(block) or block.text).strip()
        req_id, _, _ = _parse_req_heading(text.split("\n", 1)[0].strip())
        if not req_id:
            continue
        body = by_id.get(req_id)
        if not body:
            continue
        if "\n" in text and len(text.split("\n", 1)[1].strip()) > 20:
            continue
        block.text = f"{req_id}\n{body}"
        filled += 1
    return filled


def patch_mddr_design_items(doc: Document, design_changes: list[dict[str, Any]]) -> list[str]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in design_changes:
        req_id = normalize_req_id(item.get("req_id", ""))
        if req_id:
            by_id[req_id] = item

    existing = _collect_existing_req_ids(doc)
    patched: list[str] = []
    for req_id, change in by_id.items():
        design_description = change.get("design_description") or change.get("title_suffix")
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
            # Normalize thin headings like "Req.9" left in template slots.
            if heading is not None:
                heading.text = f"{normalize_req_id(req_id)}\n{design_description}"
                patched.append(req_id)
                continue
            # Avoid duplicate blocks on repeated generate/patch passes
            if req_id in existing:
                continue
            _insert_req_paragraph_section(
                doc,
                normalize_req_id(req_id) or req_id,
                design_description,
                change.get("title_suffix", ""),
            )
            existing.add(req_id)
            patched.append(req_id)

    return patched
