from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.req_ids import normalize_requirement_id as normalize_req_id
from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix
from document_ai.learn.extract_requirements import _req_id_sort_key
from document_ai.learn.extract_requirements import _req_id_sort_key
from document_ai.render.requirements import _req_id_from_table

REQ_PARAGRAPH = re.compile(r"^Req\.\s*(\d+)\.?\s*(.*)$", re.IGNORECASE)
DESIGN_LABELS = ("목적", "기준", "설명", "component", "interface", "interfaces")


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


def _item_from_req_table(table: Table, block_index: int) -> dict[str, Any] | None:
    req_id = _req_id_from_table(table)
    if not req_id:
        return None
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
) -> dict[str, Any]:
    return {
        "req_id": req_id,
        "block_kind": "paragraph",
        "block_index": heading_index,
        "title_suffix": title_suffix.strip(),
        "design_description": "\n".join(content_parts).strip(),
        "fields": {},
    }


def extract_design_items_docx(path: Path) -> dict[str, Any]:
    doc = load_document(path)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    current_req: str | None = None
    current_heading_index = -1
    current_title_suffix = ""
    current_parts: list[str] = []

    def flush_paragraph() -> None:
        nonlocal current_req, current_heading_index, current_title_suffix, current_parts
        if not current_req or current_req in seen:
            current_req = None
            current_parts = []
            return
        item = _flush_paragraph_item(current_req, current_heading_index, current_title_suffix, current_parts)
        if item["design_description"] or item["title_suffix"]:
            items.append(item)
            seen.add(current_req)
        current_req = None
        current_parts = []

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

        text = block.text.strip()
        if not text:
            continue

        match = REQ_PARAGRAPH.match(text)
        if match:
            flush_paragraph()
            current_req = normalize_req_id(f"Req. {match.group(1)}")
            current_heading_index = block_index
            current_title_suffix = match.group(2).strip()
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
