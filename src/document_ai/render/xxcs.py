from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, load_document, paragraph_deep_text, table_matrix
from document_ai.learn.req_ids import normalize_requirement_id
from document_ai.render.fill import apply_labelled_rows

REQ_HEADING = re.compile(r"\b(IA|UC|SI|DC|RA)[\s-]?(\d{1,3})\b", re.IGNORECASE)
PLACEHOLDER_MARKERS = ("XX-XX-XXXX", "□□", "{{", "TBD", "TODO")


def _heading_req_id(text: str) -> str | None:
    match = REQ_HEADING.search(text.strip())
    if match:
        return normalize_requirement_id(f"{match.group(1)}-{match.group(2)}")
    return None


def _tests_by_req(tests: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for test in tests:
        req_id = normalize_requirement_id(test.get("req_id", "")) or test.get("req_id", "")
        if not req_id:
            continue
        grouped.setdefault(req_id, []).append(test)
    return grouped


def _join_ids(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if str(v).strip())
    return str(value or "")


def _display_test_result(test: dict[str, Any]) -> str:
    linked_reqs = _join_ids(test.get("linked_req_ids") or test.get("linked_reqs"))
    linked_designs = _join_ids(test.get("linked_design_ids"))
    if any(test.get(key) for key in ("test_method", "test_procedure", "expected_result", "actual_result")):
        return "\n".join(
            part
            for part in (
                f"시험방법: {test.get('test_method', '')}".strip(),
                f"절차: {test.get('test_procedure', '')}".strip(),
                f"예상결과: {test.get('expected_result', '')}".strip(),
                f"실제결과: {test.get('actual_result', '')}".strip(),
                f"linked_reqs: {linked_reqs or 'N/A'}",
                f"linked_design_ids: {linked_designs or 'N/A'}",
            )
            if not part.endswith(":")
        )
    return str(test.get("test_result", "") or "")


def _display_notes(test: dict[str, Any]) -> str:
    linked_reqs = _join_ids(test.get("linked_req_ids") or test.get("linked_reqs"))
    linked_designs = _join_ids(test.get("linked_design_ids"))
    evidence = str(test.get("evidence") or "").strip()
    reviewer_note = str(test.get("reviewer_note") or "").strip()
    provenance = test.get("provenance") or {}
    source = provenance.get("source") or test.get("source") or ""
    executor = test.get("executor") or {}
    executor_name = ""
    if isinstance(executor, dict):
        executor_name = str(executor.get("name") or "")
    return "\n".join(
        part
        for part in (
            f"시험방법: {test.get('test_method', '')}".strip() if test.get("test_method") else "",
            f"절차: {test.get('test_procedure', '')}".strip() if test.get("test_procedure") else "",
            f"예상결과: {test.get('expected_result', '')}".strip() if test.get("expected_result") else "",
            f"실제결과: {test.get('actual_result', '')}".strip() if test.get("actual_result") else "",
            f"linked_reqs: {linked_reqs or 'N/A'}",
            f"linked_design_ids: {linked_designs or 'N/A'}",
            f"evidence: {evidence or 'N/A'}",
            f"executed_at: {test.get('executed_at')}" if test.get("executed_at") else "",
            f"executor: {executor_name}" if executor_name else "",
            f"execution_id: {test.get('execution_id')}" if test.get("execution_id") else "",
            f"review_status: {test.get('review_status')}" if test.get("review_status") else "",
            f"reviewer_note: {reviewer_note}" if reviewer_note else "",
            f"source: {source}" if source else "",
        )
        if part
    )


def _cell_value(test: dict[str, Any], key: str) -> str:
    if key == "test_result":
        return _display_test_result(test)
    if key == "applied":
        return str(test.get("applied") or test.get("execution_status") or "")
    if key == "satisfaction":
        return str(test.get("satisfaction") or "")
    if key == "notes":
        return _display_notes(test) or str(test.get("notes") or "")
    return str(test.get(key, "") or "")


def _fill_test_table(table: Table, tests: list[dict[str, Any]], *, overwrite: bool = False) -> int:
    matrix = table_matrix(table)
    if not matrix:
        return 0
    header_line = " ".join(matrix[0])
    if "시험결과" not in header_line and "Test Result" not in header_line:
        return 0

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

    filled = 0
    data_rows = list(range(1, len(table.rows)))
    for idx, test in enumerate(tests):
        if idx >= len(data_rows):
            break
        ri = data_rows[idx]
        row = table.rows[ri]

        mapped_cis = sorted({ci for ci in col_map.values() if ci < len(row.cells)})
        pre_texts = [row.cells[ci].text for ci in mapped_cis]
        # Horizontally merged result rows usually share identical cell text (often empty).
        # Distinct seeded values mean real separate columns (mini templates / round-trip tests).
        merged_like = len(mapped_cis) > 1 and len(set(pre_texts)) <= 1

        if "test_result" in col_map and merged_like:
            ci = col_map["test_result"]
            value = _cell_value(test, "test_result") or _cell_value(test, "notes")
            satisfaction = _cell_value(test, "satisfaction")
            if value and satisfaction and satisfaction not in value:
                value = f"{value}\n만족: {satisfaction}"
            if not value:
                continue
            existing = row.cells[ci].text.strip()
            if (
                not overwrite
                and existing
                and existing not in {"", ".", "-"}
                and not any(m in existing for m in PLACEHOLDER_MARKERS)
            ):
                continue
            row.cells[ci].text = value
            filled += 1
            continue

        # Separate columns: write each unique tc once, richest key first.
        key_priority = {"test_result": 0, "notes": 1, "satisfaction": 2, "applied": 3}
        groups: dict[int, list[tuple[str, int]]] = {}
        for key, ci in col_map.items():
            if ci >= len(row.cells):
                continue
            groups.setdefault(id(row.cells[ci]._tc), []).append((key, ci))

        def _group_rank(item: tuple[int, list[tuple[str, int]]]) -> int:
            return min(key_priority.get(key, 99) for key, _ci in item[1])

        for _tc_id, key_cis in sorted(groups.items(), key=_group_rank):
            key_cis_sorted = sorted(key_cis, key=lambda item: key_priority.get(item[0], 99))
            chosen: tuple[int, str] | None = None
            for key, ci in key_cis_sorted:
                value = _cell_value(test, key)
                if value:
                    chosen = (ci, value)
                    break
            if chosen is None:
                continue
            ci, value = chosen
            existing = row.cells[ci].text.strip()
            if (
                not overwrite
                and existing
                and existing not in {"", ".", "-"}
                and not any(m in existing for m in PLACEHOLDER_MARKERS)
            ):
                continue
            row.cells[ci].text = value
            filled += 1
    return filled


def apply_security_tests(
    doc: Document,
    tests: list[dict[str, Any]],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    by_req = _tests_by_req(tests)
    current_req: str | None = None
    tables_filled = 0
    cells_filled = 0
    filled_ids: set[str] = set()
    missing: list[str] = []

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            rid = _heading_req_id(paragraph_deep_text(block) or block.text)
            if rid:
                current_req = rid
            continue

        if not isinstance(block, Table) or not current_req:
            continue

        test_rows = by_req.get(current_req)
        if not test_rows:
            continue

        matrix = table_matrix(block)
        if not matrix:
            continue
        header_line = " ".join(matrix[0])
        if "시험결과" not in header_line and "Test Result" not in header_line:
            continue

        count = _fill_test_table(block, test_rows, overwrite=overwrite)
        if count:
            tables_filled += 1
            cells_filled += count
            filled_ids.add(current_req)
        else:
            missing.append(current_req)

    return {
        "tables_filled": tables_filled,
        "cells_filled": cells_filled,
        "req_ids_in_payload": len(by_req),
        "req_ids_filled": sorted(filled_ids),
        "missing_tables": missing,
    }


def verify_xxcs_completeness(
    doc: Document,
    tests: list[dict[str, Any]],
) -> dict[str, Any]:
    """Lightweight structural review for XXCS output."""
    expected = {
        normalize_requirement_id(t.get("req_id", "")) or t.get("req_id", "")
        for t in tests
        if t.get("req_id")
    }
    expected.discard("")
    found_headings: set[str] = set()
    filled_tables = 0
    residual: list[str] = []
    missing_sections: list[str] = []

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            text = paragraph_deep_text(block) or block.text
            rid = _heading_req_id(text)
            if rid:
                found_headings.add(rid)
            if any(m in text for m in PLACEHOLDER_MARKERS):
                residual.append(f"paragraph: {text[:80]}")
            continue
        if isinstance(block, Table):
            matrix = table_matrix(block)
            flat = " | ".join(" ".join(row) for row in matrix)
            if any(m in flat for m in PLACEHOLDER_MARKERS):
                residual.append(f"table: {flat[:80]}")
            if matrix and ("시험결과" in " ".join(matrix[0]) or "Test Result" in " ".join(matrix[0])):
                # any non-header content?
                has_body = any(
                    cell.strip()
                    for ri, row in enumerate(matrix)
                    for cell in row
                    if ri > 0
                )
                if has_body:
                    filled_tables += 1

    missing_ids = sorted(expected - found_headings)
    if not found_headings and expected:
        missing_sections.append("security requirement headings")
    if filled_tables == 0:
        missing_sections.append("security test result tables")

    return {
        "issue_count": len(missing_ids) + len(missing_sections),
        "residual_count": len(residual),
        "issues": [f"missing heading: {rid}" for rid in missing_ids[:30]]
        + [f"missing section: {s}" for s in missing_sections],
        "residual": residual[:20],
        "security_ids_expected": len(expected),
        "security_ids_found": len(found_headings),
        "tables_with_content": filled_tables,
        "missing_security_ids": missing_ids,
    }


def fill_xxcs_report(
    template_path: Path,
    facts: dict[str, Any],
    security_payload: dict[str, Any],
    out_path: Path,
) -> dict[str, Any]:
    doc = load_document(template_path)
    applied = apply_labelled_rows(doc, facts)
    tests = security_payload.get("tests", [])
    test_stats = apply_security_tests(doc, tests, overwrite=True)
    review = verify_xxcs_completeness(doc, tests)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    doc.save(str(out_path))
    return {
        "applied": applied,
        "security_tests": test_stats,
        "review": review,
        "output": str(out_path),
    }
