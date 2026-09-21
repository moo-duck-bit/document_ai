from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, load_document, paragraph_deep_text, table_matrix
from document_ai.learn.extract_requirements import _req_id_sort_key
from document_ai.learn.req_ids import normalize_requirement_id as normalize_req_id
from document_ai.render.requirements import _req_id_from_table

# Optional section number prefix: "4.2.1 Req. 1", "5.2.3. Req. 102"
REQ_HEADING = re.compile(
    r"^(?:(\d+(?:\.\d+)*)\.?\s+)?Req\.\s*(\d+)\.?\s*(.*)$",
    re.IGNORECASE,
)
DESIGN_LABELS = ("목적", "기준", "설명", "component", "interface", "interfaces")


def _design_text_from_item(item: dict[str, Any]) -> str:
    """Unified design body for coverage / similarity (suffix + description + fields)."""
    parts: list[str] = []
    suffix = (item.get("title_suffix") or "").strip()
    desc = (item.get("design_description") or "").strip()
    if suffix:
        parts.append(suffix)
    if desc and desc != suffix:
        parts.append(desc)
    for value in (item.get("fields") or {}).values():
        text = str(value).strip()
        if text and text not in parts:
            parts.append(text)
    return "\n".join(parts).strip()


def _parse_req_heading(text: str) -> tuple[str | None, str, str]:
    """Return (req_id, section_prefix, same_line_suffix) from a Req heading line."""
    first_line = text.split("\n", 1)[0].strip()
    match = REQ_HEADING.match(first_line)
    if not match:
        return None, "", ""
    section = (match.group(1) or "").strip()
    req_id = normalize_req_id(f"Req. {match.group(2)}")
    suffix = (match.group(3) or "").strip()
    return req_id, section, suffix


def _body_from_paragraph(text: str) -> str:
    """Body after first line when Req heading and design share one paragraph."""
    if "\n" not in text:
        return ""
    return text.split("\n", 1)[1].strip()


def _design_fields_from_matrix(matrix: list[list[str]]) -> tuple[str, dict[str, str]]:
    design_description = ""
    fields: dict[str, str] = {}

    for row in matrix[1:]:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) >= 2:
            label = row[0].strip()
            value = row[1].strip()
            if not value:
                continue
            if label.lower() in DESIGN_LABELS or label in {"목적", "기준", "설명"}:
                fields[label] = value
            elif not design_description:
                design_description = value
        elif row[0].strip() and not design_description:
            design_description = row[0].strip()

    if not design_description and fields:
        design_description = fields.get("목적") or fields.get("설명") or next(iter(fields.values()), "")
    return design_description, fields


def _normalize_table_req_id(raw: str | None) -> str | None:
    if not raw:
        return None
    return normalize_req_id(raw) or normalize_req_id(raw.split("\n", 1)[0])


def _item_from_req_table(table: Table, block_index: int) -> dict[str, Any] | None:
    raw = _req_id_from_table(table)
    req_id = _normalize_table_req_id(raw)
    if not req_id:
        # Cell may contain "4.2.1 Req. 1" or multi-line heading
        header = table.rows[0].cells[0].text.strip() if table.rows else ""
        req_id, _, same_line = _parse_req_heading(header)
        if not req_id:
            return None
        matrix = table_matrix(table)
        design_description, fields = _design_fields_from_matrix(matrix)
        if same_line and not design_description:
            design_description = same_line
        return {
            "req_id": req_id,
            "block_kind": "table",
            "block_index": block_index,
            "design_description": design_description,
            "fields": fields,
        }

    matrix = table_matrix(table)
    design_description, fields = _design_fields_from_matrix(matrix)
    return {
        "req_id": req_id,
        "block_kind": "table",
        "block_index": block_index,
        "design_description": design_description,
        "fields": fields,
    }


def _flush_paragraph_item(
    req_id: str,
    heading_index: int,
    title_suffix: str,
    content_parts: list[str],
    *,
    section_prefix: str = "",
) -> dict[str, Any]:
    body = "\n".join(part for part in content_parts if part and str(part).strip()).strip()
    # Promote same-line / first-paragraph body into design_description
    if not body and title_suffix:
        body = title_suffix
        title_suffix = ""
    return {
        "req_id": req_id,
        "block_kind": "paragraph",
        "block_index": heading_index,
        "section_prefix": section_prefix,
        "title_suffix": title_suffix.strip(),
        "design_description": body,
        "fields": {},
    }


def extract_design_items_docx(path: Path) -> dict[str, Any]:
    doc = load_document(path)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    current_req: str | None = None
    current_heading_index = -1
    current_title_suffix = ""
    current_section = ""
    current_parts: list[str] = []

    def flush_paragraph() -> None:
        nonlocal current_req, current_heading_index, current_title_suffix, current_parts, current_section
        if not current_req or current_req in seen:
            current_req = None
            current_parts = []
            current_title_suffix = ""
            current_section = ""
            return
        item = _flush_paragraph_item(
            current_req,
            current_heading_index,
            current_title_suffix,
            current_parts,
            section_prefix=current_section,
        )
        if _design_text_from_item(item) or item.get("title_suffix"):
            items.append(item)
            seen.add(current_req)
        current_req = None
        current_parts = []
        current_title_suffix = ""
        current_section = ""

    for block_index, block in enumerate(iter_blocks(doc)):
        if isinstance(block, Table):
            table_item = _item_from_req_table(block, block_index)
            if table_item:
                flush_paragraph()
                if table_item["req_id"] not in seen:
                    items.append(table_item)
                    seen.add(table_item["req_id"])
                continue
            if current_req:
                matrix = table_matrix(block)
                flat = " | ".join(" ".join(row) for row in matrix if any(cell.strip() for cell in row))
                if flat.strip():
                    current_parts.append(flat)
            continue

        if not isinstance(block, Paragraph):
            continue

        text = paragraph_deep_text(block) or block.text.strip()
        if not text:
            continue

        req_id, section, same_line_suffix = _parse_req_heading(text)
        if req_id:
            flush_paragraph()
            current_req = req_id
            current_heading_index = block_index
            current_section = section
            current_title_suffix = same_line_suffix
            same_para_body = _body_from_paragraph(text)
            current_parts = [same_para_body] if same_para_body else []
            # Same-line short title with no newline body stays as title_suffix
            continue

        if current_req:
            current_parts.append(text)

    flush_paragraph()
    items.sort(key=lambda item: _req_id_sort_key(item["req_id"]))
    return {"source": str(path), "items": items}


def save_design_items(data: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_design_items(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class DesignItemIndex:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.by_req_id = {item["req_id"]: item for item in items if item.get("req_id")}

    def has(self, req_id: str) -> bool:
        normalized = normalize_req_id(req_id)
        return bool(normalized and normalized in self.by_req_id)

    def req_ids_for(self, req_ids: list[str]) -> list[str]:
        normalized = [normalize_req_id(r) for r in req_ids]
        return [r for r in normalized if r and r in self.by_req_id]

    def get(self, req_id: str) -> dict[str, Any] | None:
        normalized = normalize_req_id(req_id)
        if not normalized:
            return None
        return self.by_req_id.get(normalized)
