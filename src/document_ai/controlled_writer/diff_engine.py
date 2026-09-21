# -*- coding: utf-8 -*-
"""PR-25: Diff engine."""

from __future__ import annotations

import difflib
from typing import Any

from document_ai.controlled_writer.schema import DiffResult


def build_diff(
    *,
    diff_id: str,
    patch_contract_id: str,
    before_text: str,
    after_text: str,
    operation: str,
) -> DiffResult:
    before_lines = (before_text or "").splitlines()
    after_lines = (after_text or "").splitlines()
    sm = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    changed_blocks: list[str] = []
    changed_paragraphs: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        block = {
            "op": tag,
            "before_lines": before_lines[i1:i2],
            "after_lines": after_lines[j1:j2],
            "before_range": [i1, i2],
            "after_range": [j1, j2],
        }
        changed_blocks.append(f"{tag}:{i1}-{i2}->{j1}-{j2}")
        for line in block["before_lines"] + block["after_lines"]:
            if line.strip():
                changed_paragraphs.append(line.strip()[:200])

    # Tables heuristic: markdown pipe rows
    before_tables = [ln for ln in before_lines if "|" in ln]
    after_tables = [ln for ln in after_lines if "|" in ln]
    changed_tables: list[str] = []
    if before_tables != after_tables:
        changed_tables.append("markdown_table_rows_changed")

    op_count = 1 if before_text != after_text else 0
    return DiffResult(
        diff_id=diff_id,
        patch_contract_id=patch_contract_id,
        before_text=before_text or "",
        after_text=after_text or "",
        changed_blocks=changed_blocks,
        changed_paragraphs=changed_paragraphs[:50],
        changed_tables=changed_tables,
        operation_count=op_count,
        evidence={
            "operation": operation,
            "unified_diff_preview": list(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile="before",
                    tofile="after",
                    lineterm="",
                )
            )[:80],
        },
    )
