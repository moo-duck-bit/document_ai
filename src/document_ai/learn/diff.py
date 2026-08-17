from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_ai.learn.docx_io import block_snapshot, load_document, table_matrix


def _slug(text: str) -> str:
    t = re.sub(r"\s+", "_", text.strip())
    t = re.sub(r"[^\w가-힣]+", "", t)
    return t[:60] or "field"


def _is_empty(val: str) -> bool:
    if not val or val in {".", "-", "…"}:
        return True
    if re.fullmatch(r"XX[-–]XX[-–]XX\(0\)", val):
        return True
    if re.fullmatch(r"XX[-–]XX[-–]XXXX\)?", val):
        return True
    return False


def diff_table_pair(
    table_index: int,
    blank: list[list[str]],
    filled: list[list[str]],
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    rows = max(len(blank), len(filled))
    cols = max(
        max((len(r) for r in blank), default=0),
        max((len(r) for r in filled), default=0),
    )
    row_labels: dict[int, str] = {}
    for ri in range(rows):
        brow = blank[ri] if ri < len(blank) else []
        frow = filled[ri] if ri < len(filled) else []
        for ci in range(cols):
            bv = brow[ci] if ci < len(brow) else ""
            fv = frow[ci] if ci < len(frow) else ""
            if bv == fv:
                continue
            if _is_empty(bv) and fv and not _is_empty(fv):
                label = row_labels.get(ri) or (brow[0] if brow else frow[0] if frow else "")
                if ci == 0 and fv:
                    row_labels[ri] = fv
                    continue
                field_id = _slug(label) if label else f"table{table_index}_r{ri}_c{ci}"
                fields.append(
                    {
                        "field_id": field_id,
                        "label": label or None,
                        "type": "string",
                        "location": {
                            "type": "table_cell",
                            "table_index": table_index,
                            "row": ri,
                            "col": ci,
                        },
                        "blank_value": bv,
                        "example_value": fv,
                    }
                )
            elif bv and fv and bv != fv and not _is_empty(fv):
                # label column or overwritten guidance text
                if ci == 0:
                    row_labels[ri] = bv
                else:
                    label = row_labels.get(ri) or brow[0] if brow else ""
                    field_id = _slug(label or f"t{table_index}_r{ri}_c{ci}")
                    fields.append(
                        {
                            "field_id": field_id,
                            "label": label or None,
                            "type": "string",
                            "location": {
                                "type": "table_cell",
                                "table_index": table_index,
                                "row": ri,
                                "col": ci,
                            },
                            "blank_value": bv,
                            "example_value": fv,
                        }
                    )
    return fields


def diff_paragraph_pair(
    para_index: int,
    blank: str,
    filled: str,
) -> dict[str, Any] | None:
    if blank == filled:
        return None
    if _is_empty(blank) and filled:
        return {
            "field_id": f"paragraph_{para_index}",
            "label": f"paragraph_{para_index}",
            "type": "free_text",
            "location": {"type": "paragraph", "paragraph_index": para_index},
            "blank_value": blank,
            "example_value": filled[:500],
        }
    if blank and filled and len(filled) > len(blank) + 10:
        return {
            "field_id": f"paragraph_{para_index}",
            "label": f"paragraph_{para_index}",
            "type": "free_text",
            "location": {"type": "paragraph", "paragraph_index": para_index},
            "blank_value": blank[:200],
            "example_value": filled[:500],
        }
    return None


def diff_documents(blank_path: Path, filled_path: Path) -> dict[str, Any]:
    blank_items = block_snapshot(load_document(blank_path))
    filled_items = block_snapshot(load_document(filled_path))

    fields: list[dict[str, Any]] = []
    repeating: list[dict[str, Any]] = []

    table_index = -1
    para_index = -1
    max_len = max(len(blank_items), len(filled_items))

    for i in range(max_len):
        b = blank_items[i] if i < len(blank_items) else None
        f = filled_items[i] if i < len(filled_items) else None

        if b and f and b["kind"] == "table" and f["kind"] == "table":
            table_index += 1
            fields.extend(diff_table_pair(table_index, b["matrix"], f["matrix"]))
        elif b and f and b["kind"] == "paragraph" and f["kind"] == "paragraph":
            para_index += 1
            pf = diff_paragraph_pair(para_index, b["text"], f["text"])
            if pf:
                fields.append(pf)
        elif (b is None or b["kind"] == "table") and f and f["kind"] == "table":
            table_index += 1
            matrix = f["matrix"]
            req_ids = [r[0] for r in matrix if r and re.match(r"^Req\.\s*\d+", r[0])]
            if req_ids:
                repeating.append(
                    {
                        "entity": "requirement",
                        "table_index": table_index,
                        "example_ids": req_ids[:5],
                        "rows": len(matrix),
                        "cols": len(matrix[0]) if matrix else 0,
                        "sample_header": matrix[0] if matrix else [],
                    }
                )
            else:
                repeating.append(
                    {
                        "entity": "extra_table",
                        "table_index": table_index,
                        "rows": len(matrix),
                        "sample_first_row": matrix[0] if matrix else [],
                    }
                )

    # dedupe field_id
    seen: set[str] = set()
    unique_fields: list[dict[str, Any]] = []
    for fld in fields:
        fid = fld["field_id"]
        if fid in seen:
            fid = f"{fid}_{fld['location'].get('row', 0)}_{fld['location'].get('col', 0)}"
            fld["field_id"] = fid
        seen.add(fid)
        unique_fields.append(fld)

    return {
        "blank_blocks": len(blank_items),
        "filled_blocks": len(filled_items),
        "fields": unique_fields,
        "repeating_entities": repeating,
    }


def extract_req_tables(filled_path: Path) -> list[dict[str, Any]]:
    """Extract Req. N rows from filled MDSR."""
    items = block_snapshot(load_document(filled_path))
    reqs: list[dict[str, Any]] = []
    table_index = -1
    for item in items:
        if item["kind"] != "table":
            continue
        table_index += 1
        matrix = item["matrix"]
        for ri, row in enumerate(matrix):
            if not row:
                continue
            m = re.match(r"^(Req\.\s*\d+)", row[0])
            if not m:
                continue
            reqs.append(
                {
                    "req_id": m.group(1).replace(" ", " "),
                    "table_index": table_index,
                    "row": ri,
                    "cells": row,
                }
            )
    return reqs
