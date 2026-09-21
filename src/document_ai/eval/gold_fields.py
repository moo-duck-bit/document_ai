"""Structured gold_fields build and semantic validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from document_ai.learn.extract_design_items import (
    _design_text_from_item,
    extract_design_items_docx,
)
from document_ai.learn.extract_requirements import extract_requirements_docx
from document_ai.learn.req_ids import normalize_requirement_id
from document_ai.validation.docx_compare import text_similarity
from document_ai.validation.section_compare import extract_section_headings

PRODUCT_PATTERNS = (
    re.compile(r"제품명[:\s]+(.+)", re.IGNORECASE),
    re.compile(r"Product\s*Name[:\s]+(.+)", re.IGNORECASE),
)


def _product_name_from_docx(path: Path) -> str:
    from document_ai.learn.docx_io import load_document, paragraph_deep_text, table_matrix

    doc = load_document(path)
    for table in doc.tables:
        matrix = table_matrix(table)
        for row in matrix:
            if len(row) >= 2 and "제품명" in row[0]:
                value = row[1].strip()
                if value:
                    return value
    for paragraph in doc.paragraphs[:40]:
        text = paragraph_deep_text(paragraph)
        for pattern in PRODUCT_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
    return ""


def build_gold_fields(
    *,
    case_id: str,
    mdsr_path: Path | None = None,
    mddr_path: Path | None = None,
    product_name: str = "",
    domain: str = "",
    source: str = "bootstrap",
    approval_status: str = "provisional",
) -> dict[str, Any]:
    """Extract structured gold fields from gold DOCX files."""
    requirements: list[dict[str, Any]] = []
    traceability_rows: list[dict[str, Any]] = []
    section_titles: list[str] = []
    design_items: list[dict[str, Any]] = []
    resolved_product = product_name

    if mdsr_path and mdsr_path.exists():
        req_payload = extract_requirements_docx(mdsr_path)
        for item in req_payload.get("requirements", []):
            req_id = normalize_requirement_id(item.get("req_id", "")) or item.get("req_id", "")
            requirements.append(
                {
                    "req_id": req_id,
                    "requirement_text": item.get("description", ""),
                }
            )
        for row in req_payload.get("traceability", []):
            traceability_rows.append(
                {
                    "requirement": row.get("requirement", ""),
                    "linked_reqs": row.get("linked_reqs", ""),
                }
            )
        section_titles = [h["text"] for h in extract_section_headings(mdsr_path)]
        if not resolved_product:
            resolved_product = _product_name_from_docx(mdsr_path)

    if mddr_path and mddr_path.exists():
        design_payload = extract_design_items_docx(mddr_path)
        for item in design_payload.get("items", []):
            req_id = normalize_requirement_id(item.get("req_id", "")) or item.get("req_id", "")
            design_items.append(
                {
                    "design_id": req_id,
                    "req_id": req_id,
                    "design_text": _design_text_from_item(item),
                    "block_kind": item.get("block_kind", ""),
                }
            )
        if not section_titles:
            section_titles = [h["text"] for h in extract_section_headings(mddr_path)]
        if not resolved_product:
            resolved_product = _product_name_from_docx(mddr_path)

    return {
        "version": "1.0",
        "case_id": case_id,
        "product_name": resolved_product,
        "domain": domain,
        "source": source,
        "approval_status": approval_status,
        "section_titles": section_titles,
        "requirement_ids": [r["req_id"] for r in requirements if r.get("req_id")],
        "requirements": requirements,
        "design_ids": [d["design_id"] for d in design_items if d.get("design_id")],
        "design_items": design_items,
        "linked_reqs": [
            {
                "requirement": row.get("requirement", ""),
                "linked_reqs": row.get("linked_reqs", ""),
            }
            for row in traceability_rows
        ],
        "traceability_rows": traceability_rows,
    }


def save_gold_fields(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_gold_fields(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _id_set(values: list[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        normalized = normalize_requirement_id(value) or value.strip()
        if normalized:
            result.add(normalized)
    return result


def _coverage(matched: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(matched / total, 3)


def compare_against_gold_fields(
    *,
    generated_mdsr: Path | None,
    generated_mddr: Path | None,
    gold_fields: dict[str, Any],
) -> dict[str, Any]:
    """Semantic validation of generated docs against structured gold_fields."""
    gen_req_ids: set[str] = set()
    gen_req_text: dict[str, str] = {}
    gen_trace: list[dict[str, str]] = []
    gen_sections: list[str] = []
    gen_design_ids: set[str] = set()
    gen_design_text: dict[str, str] = {}
    gen_product = ""

    if generated_mdsr and generated_mdsr.exists():
        payload = extract_requirements_docx(generated_mdsr)
        for item in payload.get("requirements", []):
            rid = normalize_requirement_id(item.get("req_id", "")) or item.get("req_id", "")
            if rid:
                gen_req_ids.add(rid)
                gen_req_text[rid] = item.get("description", "")
        gen_trace = payload.get("traceability", [])
        gen_sections = [h["text"] for h in extract_section_headings(generated_mdsr)]
        gen_product = _product_name_from_docx(generated_mdsr)

    if generated_mddr and generated_mddr.exists():
        payload = extract_design_items_docx(generated_mddr)
        for item in payload.get("items", []):
            rid = normalize_requirement_id(item.get("req_id", "")) or item.get("req_id", "")
            if rid:
                gen_design_ids.add(rid)
                gen_design_text[rid] = _design_text_from_item(item)
        if not gen_product:
            gen_product = _product_name_from_docx(generated_mddr)

    gold_req_ids = _id_set(list(gold_fields.get("requirement_ids") or []))
    if not gold_req_ids:
        gold_req_ids = _id_set([r.get("req_id", "") for r in gold_fields.get("requirements", [])])
    gold_design_ids = _id_set(list(gold_fields.get("design_ids") or []))
    if not gold_design_ids:
        gold_design_ids = _id_set([d.get("design_id", "") for d in gold_fields.get("design_items", [])])

    req_matched = len(gold_req_ids & gen_req_ids)
    design_matched = len(gold_design_ids & gen_design_ids)

    gold_req_map = {
        (normalize_requirement_id(r.get("req_id", "")) or r.get("req_id", "")): r.get("requirement_text", "")
        for r in gold_fields.get("requirements", [])
        if r.get("req_id")
    }
    text_sims: list[float] = []
    for rid, gold_text in gold_req_map.items():
        if rid in gen_req_text and gold_text.strip():
            text_sims.append(text_similarity(gen_req_text[rid], gold_text))

    gold_design_map = {
        (normalize_requirement_id(d.get("design_id", "")) or d.get("design_id", "")): d.get("design_text", "")
        for d in gold_fields.get("design_items", [])
        if d.get("design_id")
    }
    design_sims: list[float] = []
    for rid, gold_text in gold_design_map.items():
        if rid in gen_design_text and gold_text.strip():
            design_sims.append(text_similarity(gen_design_text[rid], gold_text))

    gold_sections = set(gold_fields.get("section_titles") or [])
    section_matched = len(gold_sections & set(gen_sections)) if gold_sections else len(gen_sections)

    gold_trace = gold_fields.get("traceability_rows") or gold_fields.get("linked_reqs") or []
    gold_trace_keys = {row.get("requirement", "").strip() for row in gold_trace if row.get("requirement")}
    gen_trace_keys = {row.get("requirement", "").strip() for row in gen_trace if row.get("requirement")}
    trace_matched = len(gold_trace_keys & gen_trace_keys)

    gold_product = (gold_fields.get("product_name") or "").strip()
    product_match = 1.0
    if gold_product and gen_product:
        product_match = 1.0 if gold_product.lower() in gen_product.lower() or gen_product.lower() in gold_product.lower() else 0.0
    elif gold_product and not gen_product:
        product_match = 0.0

    metrics = {
        "semantic_requirement_id_coverage": _coverage(req_matched, len(gold_req_ids)),
        "semantic_design_id_coverage": _coverage(design_matched, len(gold_design_ids)),
        "semantic_requirement_text_similarity": round(
            sum(text_sims) / len(text_sims) if text_sims else 1.0,
            3,
        ),
        "semantic_design_text_similarity": round(
            sum(design_sims) / len(design_sims) if design_sims else 1.0,
            3,
        ),
        "semantic_section_coverage": _coverage(section_matched, len(gold_sections) or 1),
        "semantic_traceability_coverage": _coverage(trace_matched, len(gold_trace_keys) or 1),
        "semantic_product_name_match": product_match,
        "gold_requirement_count": len(gold_req_ids),
        "generated_requirement_count": len(gen_req_ids),
        "gold_design_count": len(gold_design_ids),
        "generated_design_count": len(gen_design_ids),
        "missing_requirement_ids": sorted(gold_req_ids - gen_req_ids),
        "missing_design_ids": sorted(gold_design_ids - gen_design_ids),
    }

    # Aggregate semantic score 0–100
    weighted = (
        metrics["semantic_requirement_id_coverage"] * 0.25
        + metrics["semantic_design_id_coverage"] * 0.25
        + metrics["semantic_requirement_text_similarity"] * 0.15
        + metrics["semantic_design_text_similarity"] * 0.15
        + metrics["semantic_traceability_coverage"] * 0.10
        + metrics["semantic_section_coverage"] * 0.05
        + metrics["semantic_product_name_match"] * 0.05
    )
    metrics["semantic_overall"] = round(weighted * 100.0, 1)
    return metrics
