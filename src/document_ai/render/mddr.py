from __future__ import annotations

import re
from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, paragraph_deep_text, table_matrix
from document_ai.learn.req_ids import normalize_requirement_id
from document_ai.render.mdsr import (
    RESIDUAL_PATTERN,
    apply_mdsr_content,
    apply_mddr_residual_sections,
    apply_paragraph_overrides,
    is_template_residual,
    sanitize_document,
)


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


def apply_schema_fields(
    doc: Document,
    schema: dict[str, Any],
    facts: dict[str, Any],
    *,
    skip_paragraph_fields: bool = False,
    skip_field_ids: frozenset[str] | None = None,
) -> tuple[list[str], list[str]]:
    from document_ai.render.fill import apply_paragraph_field, apply_table_field

    skip_ids = skip_field_ids or frozenset()
    applied: list[str] = []
    skipped: list[str] = []
    for fld in schema.get("fields", []):
        fid = fld["field_id"]
        loc = fld["location"]
        if fid in skip_ids or fid.startswith("table1_"):
            skipped.append(fid)
            continue
        if skip_paragraph_fields and loc["type"] == "paragraph":
            skipped.append(fid)
            continue
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


def _req_paragraph_body(text: str) -> tuple[str | None, str]:
    from document_ai.learn.extract_design_items import _parse_req_heading

    lines = text.split("\n", 1)
    heading = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else ""
    rid, _, suffix = _parse_req_heading(heading)
    if not rid:
        return None, body
    if not body and suffix:
        body = suffix
    return rid, body


def verify_mddr_completeness(
    doc: Document,
    design_items: list[dict[str, Any]],
    *,
    domain: str = "",
) -> dict[str, Any]:
    from document_ai.learn.extract_design_items import _parse_req_heading

    issues: list[str] = []
    residual: list[str] = []
    expected = {
        rid
        for item in design_items
        if (rid := normalize_requirement_id(item.get("req_id", "") or ""))
    }
    patched_ids: set[str] = set()

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            text = paragraph_deep_text(block)
            if is_template_residual(text, domain=domain):
                residual.append(f"paragraph: {text[:80]}")
            rid, body = _req_paragraph_body(text)
            if rid:
                if len(body) < 20:
                    issues.append(f"{rid}: design paragraph too short")
                else:
                    patched_ids.add(rid)
            continue

        m = table_matrix(block)
        if not m:
            continue
        rid, _, _ = _parse_req_heading(m[0][0])
        if not rid and re.match(r"^Req\.\s*\d+", m[0][0]):
            rid = normalize_requirement_id(m[0][0].strip())
        if not rid:
            continue
        has_content = any(c.strip() for ri, row in enumerate(m) for ci, c in enumerate(row) if ri > 0 and ci > 0)
        if not has_content:
            issues.append(f"{rid}: design table not filled")
        else:
            patched_ids.add(rid)

    def _sort_key(r: str) -> int:
        match = re.search(r"(\d+)", r)
        return int(match.group(1)) if match else 0

    missing = sorted(expected - patched_ids, key=_sort_key)
    for rid in missing:
        issues.append(f"{rid}: design block missing")

    return {
        "issue_count": len(issues),
        "residual_count": len(residual),
        "issues": issues[:50],
        "residual": residual[:20],
        "design_items_expected": len(expected),
        "design_blocks_filled": len(patched_ids),
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
    from document_ai.render.design_items import (
        consolidate_mddr_design_paragraphs,
        fill_thin_mddr_design_headings,
        patch_mddr_design_items,
    )

    stats: dict[str, Any] = {}
    domain = str(content.get("domain", ""))
    stats["mdsr_content"] = apply_mdsr_content(doc, content)
    stats["residual_sections"] = apply_mddr_residual_sections(doc, content)

    applied, skipped = apply_schema_fields(
        doc,
        schema,
        merged_facts,
        skip_paragraph_fields=True,
        skip_field_ids=frozenset({"0", "0_1_2", "0_1_3", "개정번호", "개정번호_0_2", "개정번호_0_3"}),
    )
    stats["schema_applied"] = applied
    stats["schema_skipped"] = skipped

    items = (design_items_payload or {}).get("items", [])
    if items:
        patched = patch_mddr_design_items(doc, items)
        stats["design_items"] = {
            "req_ids_filled": patched,
            "total_items": len(items),
        }
    stats["design_consolidated"] = consolidate_mddr_design_paragraphs(doc)
    stats["design_thin_filled"] = fill_thin_mddr_design_headings(doc, items)
    stats["paragraph_overrides"] = apply_paragraph_overrides(doc, content)

    for _pass in range(1, 4):
        review = verify_mddr_completeness(doc, items, domain=domain)
        stats[f"review_pass_{_pass}"] = review
        if review["issue_count"] == 0 and review["residual_count"] == 0:
            stats["review_passes_completed"] = _pass
            break
        sanitize_document(doc, domain=domain)
        apply_mdsr_content(doc, content)
        apply_mddr_residual_sections(doc, content)
        apply_schema_fields(
            doc,
            schema,
            merged_facts,
            skip_paragraph_fields=True,
            skip_field_ids=frozenset({"0", "0_1_2", "0_1_3", "개정번호", "개정번호_0_2", "개정번호_0_3"}),
        )
        if items:
            patch_mddr_design_items(doc, items)
        consolidate_mddr_design_paragraphs(doc)
        fill_thin_mddr_design_headings(doc, items)
        apply_paragraph_overrides(doc, content)
    else:
        stats["review_passes_completed"] = 3

    return stats
