from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix
from document_ai.learn.req_ids import normalize_requirement_id

REQ_HEADING = re.compile(r"^(IA|UC|SI)-(\d+)\.")


def _heading_req_id(text: str) -> str | None:
    match = REQ_HEADING.match(text.strip())
    if not match:
        return None
    return normalize_requirement_id(f"{match.group(1)}-{match.group(2)}")


def _parse_test_table(matrix: list[list[str]]) -> list[dict[str, str]]:
    if not matrix or "시험결과" not in " ".join(matrix[0]):
        return []

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

    rows: list[dict[str, str]] = []
    for row in matrix[1:]:
        if not any(cell.strip() for cell in row):
            continue
        entry: dict[str, str] = {}
        for key, ci in col_map.items():
            if ci < len(row):
                entry[key] = row[ci].strip()
        if entry:
            rows.append(entry)
    return rows


def extract_security_tests_docx(path: Path) -> dict[str, Any]:
    doc = load_document(path)
    tests: list[dict[str, Any]] = []
    current_req: str | None = None

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            current_req = _heading_req_id(block.text)
            continue

        if not isinstance(block, Table):
            continue

        matrix = table_matrix(block)
        parsed_rows = _parse_test_table(matrix)
        if not parsed_rows or not current_req:
            continue

        for row in parsed_rows:
            tests.append({"req_id": current_req, **row})

    return {"source": str(path), "tests": tests}


def save_security_tests(data: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_security_tests(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".csv":
        return load_security_tests_csv(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_security_tests_csv(path: Path) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            req_id = (row.get("req_id") or row.get("requirement_id") or "").strip()
            if not req_id:
                continue
            tests.append(
                {
                    "req_id": req_id,
                    "test_result": (row.get("test_result") or row.get("시험결과") or "").strip(),
                    "applied": (row.get("applied") or row.get("적용") or "").strip(),
                    "satisfaction": (row.get("satisfaction") or row.get("만족") or "").strip(),
                    "notes": (row.get("notes") or row.get("비고") or "").strip(),
                }
            )
    return {"source": str(path), "tests": tests}
