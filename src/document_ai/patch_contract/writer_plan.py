# -*- coding: utf-8 -*-
"""PR-24: Writer adapter selection (no Writer calls)."""

from __future__ import annotations

from typing import Any


def select_writer_adapter(
    *,
    source_format: str,
    location_type: str | None,
    requested_operation: str,
) -> dict[str, Any]:
    """Decide adapter name only — never invoke a Writer."""
    fmt = (source_format or "").lower()
    loc = (location_type or "").upper()
    op = (requested_operation or "").upper()

    if op in ("ADD", "DELETE", "LINK"):
        # PR-24: these ops have no controlled writer path yet
        return {
            "writer_adapter": "UNSUPPORTED_WRITER",
            "writer_supported": False,
            "reason_codes": ["WRITER_ADAPTER_UNSUPPORTED_FOR_OPERATION"],
        }

    if fmt in ("docx", "ooxml") and loc in ("PARAGRAPH", "HEADING", "SECTION", "BLOCK"):
        return {
            "writer_adapter": "DOCX_PARAGRAPH_WRITER",
            "writer_supported": True,
            "reason_codes": ["DOCX_PARAGRAPH_ADAPTER_SELECTED"],
        }
    if fmt in ("docx", "ooxml") and loc in ("TABLE", "TABLE_CELL"):
        return {
            "writer_adapter": "DOCX_TABLE_CELL_WRITER",
            "writer_supported": True,
            "reason_codes": ["DOCX_TABLE_CELL_ADAPTER_SELECTED"],
        }
    if fmt in ("markdown", "md", "object", "sample") and loc in (
        "PARAGRAPH",
        "HEADING",
        "SECTION",
        "LIST",
        "BLOCK",
        "TABLE",
        "TABLE_CELL",
    ):
        return {
            "writer_adapter": "MARKDOWN_BLOCK_WRITER",
            "writer_supported": True,
            "reason_codes": ["MARKDOWN_BLOCK_ADAPTER_SELECTED"],
        }

    return {
        "writer_adapter": "UNSUPPORTED_WRITER",
        "writer_supported": False,
        "reason_codes": ["WRITER_ADAPTER_UNSUPPORTED"],
    }
