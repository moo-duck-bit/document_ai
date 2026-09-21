# -*- coding: utf-8 -*-
"""Read-only MDTM DOCX structure analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document
from docx.table import Table

from document_ai.domain_packs.ec_sw.mdtm_schema import guess_column_roles, refine_roles_with_body


def _cell_text(cell) -> str:
    return (cell.text or "").strip()


def _count_merged_approx(table: Table) -> int:
    """Approximate merged cells via duplicate consecutive cell object ids / same text spans."""
    # python-docx exposes grid_span on tcPr; count cells with gridSpan > 1
    count = 0
    for row in table.rows:
        for cell in row.cells:
            tc = cell._tc
            tcPr = tc.tcPr
            if tcPr is None:
                continue
            grid = tcPr.gridSpan
            if grid is not None and int(grid.val) > 1:
                count += 1
    return count


def analyze_mdtm_structure(
    source_path: str | Path,
    *,
    document_id: str = "MDTM",
) -> dict[str, Any]:
    path = Path(source_path)
    warnings: list[str] = []
    if not path.is_file():
        return {
            "document_id": document_id,
            "source_path": str(path).replace("\\", "/"),
            "table_count": 0,
            "tables": [],
            "header_candidates": [],
            "column_role_candidates": [],
            "merged_cell_count": 0,
            "empty_cell_ratio": 1.0,
            "duplicate_identifier_counts": {},
            "analysis_status": "INVALID",
            "warnings": ["missing_file"],
            "primary_table_index": None,
        }

    doc = Document(str(path))
    tables_out: list[dict[str, Any]] = []
    total_cells = 0
    empty_cells = 0
    merged_total = 0
    primary_idx = None
    primary_score = -1

    for ti, table in enumerate(doc.tables):
        rows = table.rows
        nrows = len(rows)
        ncols = len(rows[0].cells) if nrows else 0
        row_texts: list[list[str]] = []
        for row in rows:
            cells = [_cell_text(c) for c in row.cells]
            # python-docx repeats merged cell text; keep as-is for analysis
            row_texts.append(cells)
            for c in cells:
                total_cells += 1
                if not c:
                    empty_cells += 1
        merged = _count_merged_approx(table)
        merged_total += merged

        header_candidates = []
        for hi in range(min(3, nrows)):
            header_candidates.append({"row_index": hi, "cells": row_texts[hi]})

        # Prefer table with Req. in body
        req_hits = sum(1 for r in row_texts for c in r if c.lower().startswith("req"))
        score = req_hits * 10 + nrows
        if score > primary_score:
            primary_score = score
            primary_idx = ti

        # column roles from best header-ish row (row 1 often labels for MDTM)
        header_row = row_texts[1] if nrows > 1 else (row_texts[0] if row_texts else [])
        body_samples = row_texts[2:12] if nrows > 2 else row_texts[1:8]
        roles = guess_column_roles(header_row)
        roles = refine_roles_with_body(roles, body_samples)

        if nrows < 2 or req_hits == 0:
            warnings.append(f"table_{ti}_weak_or_empty")

        tables_out.append(
            {
                "table_index": ti,
                "rows": nrows,
                "cols": ncols,
                "merged_cell_count": merged,
                "req_like_cells": req_hits,
                "header_candidates": header_candidates,
                "column_role_candidates": roles,
            }
        )

    empty_ratio = (empty_cells / total_cells) if total_cells else 1.0
    status = "OK"
    if primary_idx is None:
        status = "INVALID"
        warnings.append("no_primary_table")
    elif empty_ratio > 0.95 and primary_score < 10:
        status = "REVIEW_REQUIRED"
        warnings.append("mostly_empty")

    # duplicate req ids in primary
    dup_counts: dict[str, int] = {}
    if primary_idx is not None:
        pt = tables_out[primary_idx]
        # collect from body
        # rebuild from doc
        primary = doc.tables[primary_idx]
        seen: dict[str, int] = {}
        for ri, row in enumerate(primary.rows):
            if ri < 2:
                continue
            for cell in row.cells:
                t = _cell_text(cell)
                if t.lower().startswith("req"):
                    seen[t] = seen.get(t, 0) + 1
        dup_counts = {k: v for k, v in seen.items() if v > 1}

    return {
        "document_id": document_id,
        "source_path": str(path).replace("\\", "/"),
        "table_count": len(doc.tables),
        "tables": tables_out,
        "header_candidates": (tables_out[primary_idx]["header_candidates"] if primary_idx is not None else []),
        "column_role_candidates": (
            tables_out[primary_idx]["column_role_candidates"] if primary_idx is not None else []
        ),
        "merged_cell_count": merged_total,
        "empty_cell_ratio": round(empty_ratio, 4),
        "duplicate_identifier_counts": dup_counts,
        "analysis_status": status,
        "warnings": warnings,
        "primary_table_index": primary_idx,
    }
