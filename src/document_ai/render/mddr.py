from __future__ import annotations

import re
from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, table_matrix
from document_ai.render.mdsr import RESIDUAL_PATTERN, apply_mdsr_content, sanitize_document


def apply_mddr_overview(doc: Document, overview: dict[str, Any]) -> int:
    """Fill narrative sections after structural headings (목적, 사용자, 시스템 개요)."""
    if not overview:
        return 0

    paras = [b for b in iter_blocks(doc) if isinstance(b, Paragraph)]
    filled = 0
    skip_labels = {"목적", "범위", "사용자", "시스템 개요", "개요", "식별", "참조문서", "목차", "개정이력"}

    def _fill_after(label: str, text: str) -> None:
        nonlocal filled
        if not text:
            return
        for i, para in enumerate(paras):
            if para.text.strip() != label:
                continue
            for j in range(i + 1, min(i + 6, len(paras))):
                candidate = paras[j].text.strip()
                if candidate in skip_labels:
                    break
                if not candidate or candidate == "." or RESIDUAL_PATTERN.search(candidate):
                    paras[j].text = text
                    filled += 1
                    return

    _fill_after("목적", overview.get("purpose", ""))
    for line in overview.get("users") or []:
        for i, para in enumerate(paras):
            if para.text.strip() != "사용자":
                continue
            for j in range(i + 1, min(i + 8, len(paras))):
                candidate = paras[j].text.strip()
                if candidate in skip_labels:
                    break
                if not candidate or candidate == "." or RESIDUAL_PATTERN.search(candidate):
                    paras[j].text = line
                    filled += 1
                    break
            break

    _fill_after("시스템 개요", overview.get("system", ""))
    return filled


def apply_schema_fields(doc: Document, schema: dict[str, Any], facts: dict[str, Any]) -> tuple[list[str], list[str]]:
    from document_ai.render.fill import apply_paragraph_field, apply_table_field

    applied: list[str] = []
    skipped: list[str] = []
    for fld in schema.get("fields", []):
        fid = fld["field_id"]
        loc = fld["location"]
        value = facts.get(fid)
        if value is None and fld.get("label"):
            value = facts.get(fld["label"])
        if value is None:
            skipped.append(fid)
            continue
        ok = False
        if loc["type"] == "table_cell":
            ok = apply_table_field(doc, loc, str(value))
        elif loc["type"] == "paragraph":
            ok = apply_paragraph_field(doc, loc, str(value))
        if ok:
            applied.append(fid)
        else:
            skipped.append(fid)
    return applied, skipped


def verify_mddr_completeness(doc: Document, design_items: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    residual: list[str] = []
    expected = {item.get("req_id", "") for item in design_items if item.get("req_id")}

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            t = block.text or ""
            if RESIDUAL_PATTERN.search(t):
                residual.append(f"paragraph: {t[:80]}")
        elif isinstance(block, Table):
            m = table_matrix(block)
            if not m or not re.match(r"^Req\.\s*\d+", m[0][0]):
                continue
            rid = m[0][0].strip()
            has_content = any(c.strip() for ri, row in enumerate(m) for ci, c in enumerate(row) if ri > 0 and ci > 0)
            if not has_content:
                issues.append(f"{rid}: design not filled")

    patched_ids: set[str] = set()
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        m = table_matrix(block)
        if m and re.match(r"^Req\.\s*\d+", m[0][0]):
            rid = m[0][0].strip()
            if any(c.strip() for ri, row in enumerate(m) for ci, c in enumerate(row) if ri > 0 and ci > 0):
                patched_ids.add(rid)

    return {
        "issue_count": len(issues),
        "residual_count": len(residual),
        "issues": issues[:50],
        "residual": residual[:20],
        "design_items_expected": len(expected),
        "req_tables_filled": len(patched_ids),
    }


def apply_mddr_full(
    doc: Document,
    content: dict[str, Any],
    design_items_payload: dict[str, Any] | None,
    schema: dict[str, Any],
    merged_facts: dict[str, Any],
) -> dict[str, Any]:
    """Sanitize Mindrium template, fill MDDR cover/overview, schema fields, and design blocks."""
    from document_ai.render.design_items import patch_mddr_design_items

    stats: dict[str, Any] = {}
    stats["mdsr_content"] = apply_mdsr_content(doc, content)

    if content.get("overview"):
        stats["overview"] = apply_mddr_overview(doc, content["overview"])

    applied, skipped = apply_schema_fields(doc, schema, merged_facts)
    stats["schema_applied"] = applied
    stats["schema_skipped"] = skipped

    items = (design_items_payload or {}).get("items", [])
    if items:
        patched = patch_mddr_design_items(doc, items)
        stats["design_items"] = {
            "req_ids_filled": patched,
            "total_items": len(items),
        }

    for _pass in range(1, 4):
        review = verify_mddr_completeness(doc, items)
        stats[f"review_pass_{_pass}"] = review
        if review["issue_count"] == 0 and review["residual_count"] == 0:
            stats["review_passes_completed"] = _pass
            break
        sanitize_document(doc)
        apply_mdsr_content(doc, content)
        if content.get("overview"):
            apply_mddr_overview(doc, content["overview"])
        apply_schema_fields(doc, schema, merged_facts)
        if items:
            patch_mddr_design_items(doc, items)
    else:
        stats["review_passes_completed"] = 3

    return stats
