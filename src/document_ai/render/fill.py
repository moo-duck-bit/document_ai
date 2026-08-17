from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from docx import Document

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix
from document_ai.render.requirements import apply_requirements_payload

def _set_cell_text(cell, text: str) -> None:
    cell.text = text


def apply_table_field(doc: Document, location: dict, value: str) -> bool:
    table_index = location["table_index"]
    row, col = location["row"], location["col"]
    idx = -1
    for block in iter_blocks(doc):
        from docx.table import Table

        if isinstance(block, Table):
            idx += 1
            if idx == table_index:
                if row < len(block.rows) and col < len(block.rows[row].cells):
                    _set_cell_text(block.rows[row].cells[col], str(value))
                    return True
                return False
    return False


def apply_paragraph_field(doc: Document, location: dict, value: str) -> bool:
    para_index = location["paragraph_index"]
    idx = -1
    for block in iter_blocks(doc):
        from docx.text.paragraph import Paragraph

        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            idx += 1
            if idx == para_index:
                block.text = str(value)
                return True
    return False


def apply_approval_dates(doc: Document, facts: dict[str, Any]) -> list[str]:
    approval_date = facts.get("approval_date")
    if not approval_date:
        return []

    applied: list[str] = []
    from docx.table import Table

    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        for row in block.rows:
            if len(row.cells) < 5:
                continue
            label = row.cells[0].text.strip()
            if label in {"승인자", "검토자", "작성자"}:
                _set_cell_text(row.cells[4], str(approval_date))
                applied.append(label)
    return applied


def apply_labelled_rows(doc: Document, facts: dict[str, Any]) -> list[str]:
    """Fill table rows where column 0 is a Korean/English label."""
    label_to_fact = {
        "제품명": facts.get("product_name"),
        "모델명": facts.get("model_name") or facts.get("product_name"),
        "소프트웨어명": facts.get("software_name") or facts.get("product_name"),
        "Code language": facts.get("code_language"),
        "Platform": facts.get("platform"),
        "Editor": facts.get("editor"),
    }
    applied: list[str] = []
    from docx.table import Table

    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        for row in block.rows:
            if len(row.cells) < 2:
                continue
            label = row.cells[0].text.strip()
            value = label_to_fact.get(label)
            if value is not None:
                _set_cell_text(row.cells[1], str(value))
                applied.append(label)
    return applied


def merge_content_facts(
    facts: dict[str, Any],
    content_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(facts)
    if not content_payload:
        return merged

    for key, value in content_payload.get("fields", {}).items():
        if key not in merged and value:
            merged[key] = value

    standards = facts.get("standards")
    if isinstance(standards, list):
        for idx, standard in enumerate(standards):
            merged.setdefault(f"paragraph_{2 + idx}", standard)

    hints = facts.get("free_text_hints") or content_payload.get("free_text_hints") or {}
    if isinstance(hints, dict):
        if hints.get("system_overview"):
            merged.setdefault("paragraph_6", hints["system_overview"])
        if hints.get("architecture_narrative"):
            merged.setdefault("paragraph_8", hints["architecture_narrative"])

    return merged


def fill_from_facts(
    template_path: Path,
    schema: dict[str, Any],
    facts: dict[str, Any],
    out_path: Path,
    requirements_payload: dict[str, Any] | None = None,
    content_payload: dict[str, Any] | None = None,
    design_items_payload: dict[str, Any] | None = None,
    overwrite_requirements: bool = False,
) -> dict[str, Any]:
    doc = load_document(template_path)
    merged_facts = merge_content_facts(facts, content_payload)
    applied: list[str] = []
    skipped: list[str] = []

    mdsr_content = merged_facts.get("mdsr_content") or (content_payload or {}).get("mdsr")
    mddr_content = merged_facts.get("mddr_content") or (content_payload or {}).get("mddr")
    req_stats: dict[str, Any] = {}

    if mddr_content:
        from document_ai.render.mddr import apply_mddr_full

        req_stats = apply_mddr_full(
            doc,
            mddr_content,
            design_items_payload,
            schema,
            merged_facts,
        )
        applied.append("mddr_full")
    elif mdsr_content and requirements_payload:
        from document_ai.render.mdsr import apply_mdsr_full

        req_stats = apply_mdsr_full(doc, mdsr_content, requirements_payload)
        applied.append("mdsr_full")
    else:
        applied.extend(apply_labelled_rows(doc, merged_facts))
        applied.extend(apply_approval_dates(doc, merged_facts))

        for fld in schema.get("fields", []):
            fid = fld["field_id"]
            if fid in applied:
                continue
            loc = fld["location"]
            value = merged_facts.get(fid)
            if value is None and fld.get("label"):
                value = merged_facts.get(fld["label"])
            if value is None:
                skipped.append(fid)
                continue
            ok = False
            if loc["type"] == "table_cell":
                ok = apply_table_field(doc, loc, value)
            elif loc["type"] == "paragraph":
                ok = apply_paragraph_field(doc, loc, value)
            if ok:
                applied.append(fid)
            else:
                skipped.append(fid)

        if requirements_payload:
            req_stats = apply_requirements_payload(
                doc, requirements_payload, overwrite_descriptions=overwrite_requirements
            )
            from document_ai.render.mdsr import apply_traceability_details

            req_stats["traceability_details_filled"] = apply_traceability_details(
                doc, requirements_payload.get("traceability", [])
            )
        if mdsr_content:
            from document_ai.render.mdsr import apply_mdsr_content

            req_stats["mdsr_content"] = apply_mdsr_content(doc, mdsr_content)

    design_stats: dict[str, Any] = {}
    if design_items_payload and "mddr_full" not in applied:
        from document_ai.render.design_items import patch_mddr_design_items

        patched = patch_mddr_design_items(doc, design_items_payload.get("items", []))
        design_stats = {"req_ids_filled": patched, "total_items": len(design_items_payload.get("items", []))}
    elif req_stats.get("design_items"):
        design_stats = req_stats["design_items"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = Path(tempfile.gettempdir()) / f"document_ai_out_{out_path.name}"
    doc.save(str(tmp_out))
    shutil.copy2(tmp_out, out_path)
    return {
        "applied": applied,
        "skipped": skipped,
        "requirements": req_stats,
        "design_items": design_stats,
        "output": str(out_path),
    }


def create_xxcs_skeleton(
    filled_path: Path,
    out_path: Path,
    strip_headers: tuple[str, ...] = ("시험결과", "적용", "비고", "만족"),
) -> dict[str, Any]:
    """Copy filled XXCS and clear test-result cells."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(filled_path, out_path)
    doc = load_document(out_path)

    cleared = 0
    tables_processed = 0
    for block in iter_blocks(doc):
        from docx.table import Table

        if not isinstance(block, Table):
            continue
        tables_processed += 1
        matrix = table_matrix(block)
        if not matrix:
            continue
        header = " ".join(matrix[0])
        if "시험결과" not in header and "적용" not in header:
            continue
        # find column indices
        col_map: dict[str, int] = {}
        for ci, h in enumerate(matrix[0]):
            for sh in strip_headers:
                if sh in h:
                    col_map[sh] = ci
        if not col_map and len(matrix[0]) >= 3:
            # fallback: last 3 cols often result/apply/notes
            for ci in range(1, len(matrix[0])):
                col_map[f"col{ci}"] = ci

        for ri in range(1, len(block.rows)):
            for ci in range(len(block.rows[ri].cells)):
                h0 = matrix[0][ci] if ci < len(matrix[0]) else ""
                if any(sh in h0 for sh in strip_headers) or (
                    ci > 0 and "시험" in header
                ):
                    cell_text = block.rows[ri].cells[ci].text.strip()
                    if cell_text and cell_text not in {"-", "N/A"}:
                        _set_cell_text(block.rows[ri].cells[ci], "")
                        cleared += 1
                    elif cell_text in {"적용", "N/A", "만족", "불만족"}:
                        _set_cell_text(block.rows[ri].cells[ci], "")
                        cleared += 1

    doc.save(str(out_path))
    return {
        "output": str(out_path),
        "tables_processed": tables_processed,
        "cells_cleared": cleared,
    }
