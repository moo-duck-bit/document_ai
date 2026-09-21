from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix
from document_ai.learn.req_ids import normalize_requirement_id, parse_linked_ids

REQ_HEADING = re.compile(r"\b(IA|UC|SI|DC|RA)[\s-]?(\d{1,3})\b", re.IGNORECASE)
LABEL_ONLY = {"시험방법", "확인결과", "시험결과", "적용", "만족", "비고"}


def _heading_req_id(text: str) -> str | None:
    match = REQ_HEADING.search(text.strip())
    if not match:
        return None
    return normalize_requirement_id(f"{match.group(1)}-{match.group(2)}")


def _split_ids(value: str) -> list[str]:
    ids: list[str] = []
    for part in re.split(r"[,;/\n]+", value or ""):
        normalized = normalize_requirement_id(part.strip())
        if normalized and normalized not in ids:
            ids.append(normalized)
    return ids


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str:
    if not text:
        return ""
    label_alt = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(
        rf"(?:^|\n)\s*(?:{label_alt})\s*[:：]\s*(.*?)(?=\n\s*[\w가-힣 _-]+\s*[:：]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _is_label_only_row(entry: dict[str, str]) -> bool:
    values = [v.strip() for v in entry.values() if v and v.strip()]
    return bool(values) and all(value in LABEL_ONLY for value in values)


def _enrich_entry(entry: dict[str, str]) -> dict[str, str | list[str]]:
    test_result = entry.get("test_result", "")
    notes = entry.get("notes", "")
    combined = "\n".join(v for v in (test_result, notes) if v)
    enriched: dict[str, str | list[str]] = dict(entry)

    field_specs = {
        "test_method": ("시험방법", "test_method", "method"),
        "test_procedure": ("절차", "test_procedure", "procedure"),
        "expected_result": ("예상결과", "expected_result", "expected"),
        "actual_result": ("실제결과", "actual_result", "actual"),
        "evidence": ("증적", "evidence"),
        "reviewer_note": ("reviewer_note", "reviewer note", "검토의견"),
    }
    for key, labels in field_specs.items():
        value = _extract_labeled_value(combined, labels)
        if value:
            enriched[key] = value

    linked_req_text = _extract_labeled_value(combined, ("linked_reqs", "linked_req_ids", "linked requirements"))
    if linked_req_text:
        enriched["linked_req_ids"] = _split_ids(linked_req_text)
        enriched["linked_reqs"] = ", ".join(enriched["linked_req_ids"])  # type: ignore[arg-type]
    linked_design_text = _extract_labeled_value(
        combined,
        ("linked_design_ids", "linked designs", "linked_design"),
    )
    if linked_design_text:
        enriched["linked_design_ids"] = _split_ids(linked_design_text)

    satisfaction = (entry.get("satisfaction") or "").strip()
    if not satisfaction:
        actual = str(enriched.get("actual_result", ""))
        if "NOT_EXECUTED" in actual:
            enriched["satisfaction"] = "NOT_EXECUTED"
        elif "NOT_APPLICABLE" in actual:
            enriched["satisfaction"] = "NOT_APPLICABLE"
    return enriched


def _parse_test_table(matrix: list[list[str]]) -> list[dict[str, str]]:
    if not matrix:
        return []
    header_line = " ".join(matrix[0])
    if "시험결과" not in header_line and "Test Result" not in header_line:
        return []

    header = matrix[0]
    col_map: dict[str, int] = {}
    for ci, cell in enumerate(header):
        text = cell.strip()
        if text in {"시험결과", "Test Result"}:
            col_map["test_result"] = ci
        elif text in {"적용", "Applied"}:
            col_map["applied"] = ci
        elif text in {"만족", "Satisfaction"}:
            col_map["satisfaction"] = ci
        elif text in {"비고", "Notes"}:
            col_map["notes"] = ci

    rows: list[dict[str, str]] = []
    for row in matrix[1:]:
        if not any(cell.strip() for cell in row):
            continue
        entry: dict[str, str] = {}
        for key, ci in col_map.items():
            if ci < len(row):
                entry[key] = row[ci].strip()
        if entry and not _is_label_only_row(entry):
            rows.append(_enrich_entry(entry))  # type: ignore[arg-type]
    return rows


def extract_security_tests_docx(path: Path) -> dict[str, Any]:
    doc = load_document(path)
    tests: list[dict[str, Any]] = []
    current_req: str | None = None
    seen_keys: set[tuple[str, str, str]] = set()

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            rid = _heading_req_id(block.text)
            if rid:
                current_req = rid
            continue

        if not isinstance(block, Table):
            continue

        matrix = table_matrix(block)
        # Table-first-cell may itself be a security id
        if matrix and matrix[0] and not current_req:
            maybe = _heading_req_id(matrix[0][0])
            if maybe:
                current_req = maybe

        parsed_rows = _parse_test_table(matrix)
        if not parsed_rows or not current_req:
            continue

        for row in parsed_rows:
            key = (current_req, row.get("test_result", "")[:80], row.get("applied", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            tests.append({"req_id": current_req, **row})

    return {
        "source": str(path),
        "tests": tests,
        "security_req_ids": sorted({t["req_id"] for t in tests}),
    }


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
