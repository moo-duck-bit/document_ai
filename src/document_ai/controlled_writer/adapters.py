# -*- coding: utf-8 -*-
"""PR-25: Writer adapters (mutate COPY only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def apply_markdown_block(
    copy_path: Path,
    *,
    operation: str,
    original_text: str | None,
    proposed_text: str | None,
    character_span: tuple[int, int] | None = None,
    link_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply UPDATE/REPLACE/ADD/DELETE/LINK on a markdown copy."""
    op = (operation or "").upper()
    before = _read_text(copy_path)
    after = before
    codes: list[str] = []

    if op in ("UPDATE", "REPLACE"):
        if original_text is None or proposed_text is None:
            return {
                "ok": False,
                "before": before,
                "after": before,
                "reason_codes": ["MISSING_TEXT"],
            }
        if character_span is not None:
            start, end = character_span
            if start < 0 or end > len(before) or start > end:
                return {
                    "ok": False,
                    "before": before,
                    "after": before,
                    "reason_codes": ["INVALID_SPAN"],
                }
            slice_text = before[start:end]
            if slice_text != original_text:
                # fallback: exact replace once
                if original_text not in before:
                    return {
                        "ok": False,
                        "before": before,
                        "after": before,
                        "reason_codes": ["ORIGINAL_TEXT_NOT_FOUND"],
                    }
                after = before.replace(original_text, proposed_text, 1)
                codes.append("FALLBACK_EXACT_REPLACE")
            else:
                after = before[:start] + proposed_text + before[end:]
                codes.append("SPAN_REPLACE")
        else:
            if original_text not in before:
                return {
                    "ok": False,
                    "before": before,
                    "after": before,
                    "reason_codes": ["ORIGINAL_TEXT_NOT_FOUND"],
                }
            after = before.replace(original_text, proposed_text, 1)
            codes.append("EXACT_REPLACE")

    elif op == "ADD":
        if not proposed_text:
            return {
                "ok": False,
                "before": before,
                "after": before,
                "reason_codes": ["MISSING_PROPOSED_TEXT"],
            }
        sep = "" if before.endswith("\n") else "\n"
        after = before + sep + proposed_text + "\n"
        codes.append("APPEND_BLOCK")

    elif op == "DELETE":
        if original_text is None:
            return {
                "ok": False,
                "before": before,
                "after": before,
                "reason_codes": ["MISSING_ORIGINAL_TEXT"],
            }
        if original_text not in before:
            return {
                "ok": False,
                "before": before,
                "after": before,
                "reason_codes": ["ORIGINAL_TEXT_NOT_FOUND"],
            }
        after = before.replace(original_text, "", 1)
        codes.append("DELETE_BLOCK")

    elif op == "LINK":
        meta = link_metadata or {}
        target = meta.get("url") or meta.get("link_target")
        label = proposed_text or meta.get("label") or original_text or "link"
        if not target:
            return {
                "ok": False,
                "before": before,
                "after": before,
                "reason_codes": ["LINK_METADATA_MISSING"],
            }
        link_md = f"[{label}]({target})"
        if original_text and original_text in before:
            after = before.replace(original_text, link_md, 1)
        else:
            sep = "" if before.endswith("\n") else "\n"
            after = before + sep + link_md + "\n"
        codes.append("LINK_INSERTED")
    else:
        return {
            "ok": False,
            "before": before,
            "after": before,
            "reason_codes": ["UNSUPPORTED_OPERATION"],
        }

    if after == before and op not in ("UPDATE", "REPLACE"):
        # ADD/DELETE/LINK that somehow no-op still may be ok for empty cases
        pass

    _write_text(copy_path, after)
    return {
        "ok": True,
        "before": before,
        "after": after,
        "reason_codes": codes + ["WRITE_SUCCEEDED"],
        "changed": after != before,
    }


def apply_docx_paragraph(
    copy_path: Path,
    *,
    operation: str,
    original_text: str | None,
    proposed_text: str | None,
    paragraph_index: int | None = None,
) -> dict[str, Any]:
    """UPDATE/REPLACE on DOCX paragraph copy via python-docx."""
    from docx import Document

    from document_ai.impact.docx_activation_writer import replace_text_preserving_runs

    op = (operation or "").upper()
    if op not in ("UPDATE", "REPLACE"):
        return {
            "ok": False,
            "before": "",
            "after": "",
            "reason_codes": ["DOCX_OPERATION_UNSUPPORTED"],
        }
    if original_text is None or proposed_text is None:
        return {
            "ok": False,
            "before": "",
            "after": "",
            "reason_codes": ["MISSING_TEXT"],
        }

    doc = Document(str(copy_path))
    before_blob = "\n".join(p.text for p in doc.paragraphs)
    target = None
    if paragraph_index is not None and 0 <= paragraph_index < len(doc.paragraphs):
        target = doc.paragraphs[paragraph_index]
    else:
        for p in doc.paragraphs:
            if original_text in (p.text or ""):
                target = p
                break
    if target is None:
        return {
            "ok": False,
            "before": before_blob,
            "after": before_blob,
            "reason_codes": ["PARAGRAPH_NOT_FOUND"],
        }

    ok, msg = replace_text_preserving_runs(target, original_text, proposed_text)
    if not ok:
        return {
            "ok": False,
            "before": before_blob,
            "after": before_blob,
            "reason_codes": ["REPLACE_FAILED", msg],
        }
    doc.save(str(copy_path))
    after_doc = Document(str(copy_path))
    after_blob = "\n".join(p.text for p in after_doc.paragraphs)
    return {
        "ok": True,
        "before": before_blob,
        "after": after_blob,
        "reason_codes": ["DOCX_PARAGRAPH_WRITE_SUCCEEDED"],
        "changed": after_blob != before_blob,
    }


def apply_docx_table_cell(
    copy_path: Path,
    *,
    operation: str,
    original_text: str | None,
    proposed_text: str | None,
    table_index: int | None = None,
    cell_coordinate: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """UPDATE/REPLACE on DOCX table cell copy."""
    from docx import Document

    op = (operation or "").upper()
    if op not in ("UPDATE", "REPLACE"):
        return {
            "ok": False,
            "before": "",
            "after": "",
            "reason_codes": ["DOCX_OPERATION_UNSUPPORTED"],
        }
    if original_text is None or proposed_text is None:
        return {
            "ok": False,
            "before": "",
            "after": "",
            "reason_codes": ["MISSING_TEXT"],
        }

    doc = Document(str(copy_path))
    if not doc.tables:
        return {
            "ok": False,
            "before": "",
            "after": "",
            "reason_codes": ["NO_TABLES"],
        }
    ti = table_index if table_index is not None else 0
    if ti < 0 or ti >= len(doc.tables):
        return {
            "ok": False,
            "before": "",
            "after": "",
            "reason_codes": ["TABLE_INDEX_INVALID"],
        }
    table = doc.tables[ti]
    before_cells = [[c.text for c in row.cells] for row in table.rows]

    cell = None
    if cell_coordinate is not None:
        r, c = cell_coordinate
        try:
            cell = table.rows[r].cells[c]
        except Exception:  # noqa: BLE001
            return {
                "ok": False,
                "before": json.dumps(before_cells, ensure_ascii=False),
                "after": json.dumps(before_cells, ensure_ascii=False),
                "reason_codes": ["CELL_COORDINATE_INVALID"],
            }
    else:
        for row in table.rows:
            for c in row.cells:
                if original_text in (c.text or ""):
                    cell = c
                    break
            if cell is not None:
                break

    if cell is None:
        return {
            "ok": False,
            "before": json.dumps(before_cells, ensure_ascii=False),
            "after": json.dumps(before_cells, ensure_ascii=False),
            "reason_codes": ["CELL_NOT_FOUND"],
        }

    # Simple cell text replace (first paragraph)
    if original_text not in (cell.text or ""):
        return {
            "ok": False,
            "before": json.dumps(before_cells, ensure_ascii=False),
            "after": json.dumps(before_cells, ensure_ascii=False),
            "reason_codes": ["CELL_TEXT_MISMATCH"],
        }
    new_text = (cell.text or "").replace(original_text, proposed_text, 1)
    # clear and set
    for p in cell.paragraphs:
        for run in p.runs:
            run.text = ""
        if p.runs:
            p.runs[0].text = new_text
        else:
            p.add_run(new_text)
        break
    else:
        cell.text = new_text

    doc.save(str(copy_path))
    after_doc = Document(str(copy_path))
    after_cells = [
        [c.text for c in row.cells] for row in after_doc.tables[ti].rows
    ]
    return {
        "ok": True,
        "before": json.dumps(before_cells, ensure_ascii=False),
        "after": json.dumps(after_cells, ensure_ascii=False),
        "reason_codes": ["DOCX_TABLE_CELL_WRITE_SUCCEEDED"],
        "changed": after_cells != before_cells,
    }


def dispatch_adapter(
    adapter: str,
    copy_path: Path,
    *,
    operation: str,
    original_text: str | None,
    proposed_text: str | None,
    character_span: tuple[int, int] | None = None,
    paragraph_index: int | None = None,
    table_index: int | None = None,
    cell_coordinate: tuple[int, int] | None = None,
    link_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = (adapter or "").upper()
    if name == "MARKDOWN_BLOCK_WRITER":
        return apply_markdown_block(
            copy_path,
            operation=operation,
            original_text=original_text,
            proposed_text=proposed_text,
            character_span=character_span,
            link_metadata=link_metadata,
        )
    if name == "DOCX_PARAGRAPH_WRITER":
        return apply_docx_paragraph(
            copy_path,
            operation=operation,
            original_text=original_text,
            proposed_text=proposed_text,
            paragraph_index=paragraph_index,
        )
    if name == "DOCX_TABLE_CELL_WRITER":
        return apply_docx_table_cell(
            copy_path,
            operation=operation,
            original_text=original_text,
            proposed_text=proposed_text,
            table_index=table_index,
            cell_coordinate=cell_coordinate,
        )
    return {
        "ok": False,
        "before": "",
        "after": "",
        "reason_codes": ["UNSUPPORTED_WRITER"],
    }
