"""Traceability matrix comparison for MDSR documents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx.table import Table

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix

TRACE_ID_RE = re.compile(r"^[A-Z]{2}-\d+")


def extract_traceability_rows(doc_path: Path) -> dict[str, dict[str, str]]:
    doc = load_document(doc_path)
    rows: dict[str, dict[str, str]] = {}
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        matrix = table_matrix(block)
        if not matrix:
            continue
        if not any(row and row[0].startswith("IA-01") for row in matrix):
            continue
        for row in matrix:
            if not row or not TRACE_ID_RE.match(row[0].strip()):
                continue
            req_id = row[0].strip()
            rows[req_id] = {
                "requirement": req_id,
                "title": row[1].strip() if len(row) > 1 else "",
                "applicability": row[2].strip() if len(row) > 2 else "",
                "linked_reqs": row[3].strip() if len(row) > 3 else "",
            }
    return rows


def _normalize_linked(linked: str) -> set[str]:
    if not linked or linked.strip().upper() == "N/A":
        return set()
    parts = re.split(r"[,;/]", linked)
    return {p.strip() for p in parts if p.strip()}


def compare_traceability(
    generated_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    generated_path = generated_path.resolve()
    gold_path = gold_path.resolve()
    gen_rows = extract_traceability_rows(generated_path)
    gold_rows = extract_traceability_rows(gold_path)

    all_ids = sorted(set(gen_rows) | set(gold_rows))
    matched_links = 0
    comparable = 0
    missing_in_generated: list[str] = []
    extra_in_generated: list[str] = []
    linked_mismatches: list[dict[str, Any]] = []
    high_risk: list[dict[str, Any]] = []

    for req_id in all_ids:
        gold = gold_rows.get(req_id)
        generated = gen_rows.get(req_id)
        if gold is None:
            extra_in_generated.append(req_id)
            continue
        if generated is None:
            missing_in_generated.append(req_id)
            high_risk.append(
                {
                    "requirement": req_id,
                    "kind": "missing_trace_row",
                    "detail": "Traceability row present in gold but missing in generated",
                }
            )
            continue

        gold_linked = _normalize_linked(gold.get("linked_reqs", ""))
        gen_linked = _normalize_linked(generated.get("linked_reqs", ""))
        if gold_linked or gen_linked:
            comparable += 1
            if gold_linked == gen_linked:
                matched_links += 1
            else:
                linked_mismatches.append(
                    {
                        "requirement": req_id,
                        "gold_linked_reqs": gold.get("linked_reqs", ""),
                        "generated_linked_reqs": generated.get("linked_reqs", ""),
                    }
                )
                high_risk.append(
                    {
                        "requirement": req_id,
                        "kind": "linked_reqs_mismatch",
                        "detail": "Linked requirement IDs differ from gold",
                    }
                )

        if gold.get("linked_reqs", "").strip() and not generated.get("linked_reqs", "").strip():
            high_risk.append(
                {
                    "requirement": req_id,
                    "kind": "empty_linked_reqs",
                    "detail": "Gold has linked reqs but generated row is empty",
                }
            )

    gen_filled = sum(1 for row in gen_rows.values() if row.get("linked_reqs", "").strip())
    gen_total = len(gen_rows)
    gold_filled = sum(1 for row in gold_rows.values() if row.get("linked_reqs", "").strip())
    gold_total = len(gold_rows)

    return {
        "traceability_coverage": round(gen_filled / gen_total, 3) if gen_total else 1.0,
        "gold_traceability_coverage": round(gold_filled / gold_total, 3) if gold_total else 1.0,
        "traceability_row_match": round(matched_links / comparable, 3) if comparable else 1.0,
        "gold_traceability_count": gold_total,
        "generated_traceability_count": gen_total,
        "missing_in_generated": missing_in_generated,
        "extra_in_generated": extra_in_generated,
        "linked_req_mismatches": linked_mismatches[:20],
        "high_risk": high_risk[:20],
    }
