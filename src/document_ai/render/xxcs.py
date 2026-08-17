from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix
from document_ai.learn.req_ids import normalize_requirement_id
from document_ai.render.fill import apply_labelled_rows

REQ_HEADING = re.compile(r"^(IA|UC|SI)-(\d+)\.")


def _heading_req_id(text: str) -> str | None:
    match = REQ_HEADING.match(text.strip())
    if not match:
        return None
    return normalize_requirement_id(f"{match.group(1)}-{match.group(2)}")


def _tests_by_req(tests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for test in tests:
        req_id = normalize_requirement_id(test.get("req_id", "")) or test.get("req_id", "")
        if req_id:
            grouped[req_id] = test
    return grouped


def _fill_test_table(table: Table, test: dict[str, Any]) -> int:
    matrix = table_matrix(table)
    if not matrix or "시험결과" not in " ".join(matrix[0]):
        return 0

    header = matrix[0]
    col_map: dict[str, int] = {}
    for ci, cell in enumerate(header):
        text = cell.strip()
        if text == "시험결과":
            col_map["test_result"] = ci
        elif text == "적용":
            col_map["applied"] = ci
        elif text == "만족":
            col_map["satisfaction"] = ci
        elif text == "비고":
            col_map["notes"] = ci

    filled = 0
    for ri in range(1, len(table.rows)):
        row = table.rows[ri]
        row_filled = 0
        for key, ci in col_map.items():
            value = test.get(key, "")
            if value and ci < len(row.cells) and not row.cells[ci].text.strip():
                row.cells[ci].text = value
                row_filled += 1
        if row_filled:
            filled += row_filled
            break
    return filled


def apply_security_tests(doc: Document, tests: list[dict[str, Any]]) -> dict[str, Any]:
    by_req = _tests_by_req(tests)
    current_req: str | None = None
    tables_filled = 0
    cells_filled = 0
    missing: list[str] = []

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            current_req = _heading_req_id(block.text)
            continue

        if not isinstance(block, Table) or not current_req:
            continue

        test = by_req.get(current_req)
        if not test:
            continue

        matrix = table_matrix(block)
        if not matrix or "시험결과" not in " ".join(matrix[0]):
            continue

        count = _fill_test_table(block, test)
        if count:
            tables_filled += 1
            cells_filled += count
        else:
            missing.append(current_req)

    return {
        "tables_filled": tables_filled,
        "cells_filled": cells_filled,
        "req_ids_in_payload": len(by_req),
        "missing_tables": missing,
    }


def fill_xxcs_report(
    template_path: Path,
    facts: dict[str, Any],
    security_payload: dict[str, Any],
    out_path: Path,
) -> dict[str, Any]:
    doc = load_document(template_path)
    applied = apply_labelled_rows(doc, facts)
    test_stats = apply_security_tests(doc, security_payload.get("tests", []))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return {
        "applied": applied,
        "security_tests": test_stats,
        "output": str(out_path),
    }
