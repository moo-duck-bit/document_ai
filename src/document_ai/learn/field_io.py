from __future__ import annotations

from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks


def read_field_value(doc: Document, location: dict[str, Any]) -> str:
    if location["type"] == "table_cell":
        table_index = location["table_index"]
        row, col = location["row"], location["col"]
        idx = -1
        for block in iter_blocks(doc):
            if isinstance(block, Table):
                idx += 1
                if idx == table_index:
                    if row < len(block.rows) and col < len(block.rows[row].cells):
                        return block.rows[row].cells[col].text.strip()
                    return ""
        return ""

    if location["type"] == "paragraph":
        para_index = location["paragraph_index"]
        idx = -1
        for block in iter_blocks(doc):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                idx += 1
                if idx == para_index:
                    return text
        return ""

    return ""


def extract_schema_values(filled_path, schema: dict[str, Any]) -> dict[str, str]:
    from document_ai.learn.docx_io import load_document

    doc = load_document(filled_path)
    values: dict[str, str] = {}
    for fld in schema.get("fields", []):
        value = read_field_value(doc, fld["location"])
        if value:
            values[fld["field_id"]] = value
    return values
