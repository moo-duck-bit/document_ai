"""Compare generated documents against gold references."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_ai.learn.docx_io import load_document, paragraph_deep_text, table_matrix
from document_ai.retrieval.embedding import TfidfEmbedding
from document_ai.retrieval.similarity import cosine_similarity

REQ_ID_RE = re.compile(r"^Req\.\s*\d+", re.I)
TRACE_ID_RE = re.compile(r"^[A-Z]{2}-\d+")


def _paragraphs(doc_path: Path) -> list[str]:
    doc = load_document(doc_path)
    return [paragraph_deep_text(p) for p in doc.paragraphs if paragraph_deep_text(p).strip()]


def _product_fields(doc_path: Path) -> dict[str, str]:
    doc = load_document(doc_path)
    fields: dict[str, str] = {}
    for table in doc.tables:
        matrix = table_matrix(table)
        if not matrix or matrix[0][0] != "제품명":
            continue
        for row in matrix:
            if len(row) >= 2 and row[0].strip():
                fields[row[0].strip()] = row[1].strip()
    return fields


def _req_coverage(doc_path: Path) -> tuple[int, int]:
    doc = load_document(doc_path)
    total = 0
    filled = 0
    for table in doc.tables:
        matrix = table_matrix(table)
        if not matrix or not REQ_ID_RE.match(matrix[0][0]):
            continue
        total += 1
        has_body = any(
            cell.strip()
            for row in matrix[1:]
            for cell in row[1:]
            if len(row) > 1
        )
        if has_body:
            filled += 1
    return filled, total


def _trace_coverage(doc_path: Path) -> tuple[int, int]:
    doc = load_document(doc_path)
    total = 0
    filled = 0
    for table in doc.tables:
        matrix = table_matrix(table)
        if not matrix:
            continue
        if not any(row and row[0].startswith("IA-01") for row in matrix):
            continue
        for row in matrix:
            if row and TRACE_ID_RE.match(row[0]):
                total += 1
                if len(row) >= 4 and row[3].strip():
                    filled += 1
    return filled, total


def _field_similarity(generated: dict[str, str], gold: dict[str, str]) -> float:
    if not gold:
        return 1.0
    keys = set(gold) & set(generated)
    if not keys:
        return 0.0
    matches = sum(1 for key in keys if generated[key] and generated[key] == gold[key])
    return matches / len(keys)


def _paragraph_similarity(generated: list[str], gold: list[str]) -> float:
    if not generated or not gold:
        return 0.0
    tfidf = TfidfEmbedding()
    tfidf.fit(gold + generated)
    gold_vecs = tfidf.transform(gold)
    gen_vecs = tfidf.transform(generated)
    scores: list[float] = []
    for gen_vec in gen_vecs:
        best = max(cosine_similarity(gen_vec, gold_vec) for gold_vec in gold_vecs)
        scores.append(best)
    return sum(scores) / len(scores) if scores else 0.0


def compare_documents(
    generated_path: Path,
    gold_path: Path,
    *,
    label: str = "mdsr",
) -> dict[str, Any]:
    generated_path = generated_path.resolve()
    gold_path = gold_path.resolve()
    if not generated_path.exists() or not gold_path.exists():
        return {
            "label": label,
            "generated": str(generated_path),
            "gold": str(gold_path),
            "error": "missing document",
        }

    gen_fields = _product_fields(generated_path)
    gold_fields = _product_fields(gold_path)
    gen_paras = _paragraphs(generated_path)
    gold_paras = _paragraphs(gold_path)
    req_filled, req_total = _req_coverage(generated_path)
    trace_filled, trace_total = _trace_coverage(generated_path)

    return {
        "label": label,
        "generated": str(generated_path),
        "gold": str(gold_path),
        "field_similarity": round(_field_similarity(gen_fields, gold_fields), 3),
        "paragraph_similarity": round(_paragraph_similarity(gen_paras, gold_paras), 3),
        "requirement_coverage": round(req_filled / req_total, 3) if req_total else 1.0,
        "traceability_coverage": round(trace_filled / trace_total, 3) if trace_total else 1.0,
        "requirement_counts": {"filled": req_filled, "total": req_total},
        "traceability_counts": {"filled": trace_filled, "total": trace_total},
    }


def compare_case(
    case_dir: Path,
    *,
    gold_mdsr: Path | None = None,
    gold_mddr: Path | None = None,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    comparisons: dict[str, Any] = {}
    gen_mdsr = case_dir / "output_mdsr.docx"
    gen_mddr = case_dir / "output_mddr.docx"
    if gold_mdsr and gen_mdsr.exists():
        comparisons["mdsr"] = compare_documents(gen_mdsr, gold_mdsr, label="mdsr")
    if gold_mddr and gen_mddr.exists():
        comparisons["mddr"] = compare_documents(gen_mddr, gold_mddr, label="mddr")

    if not comparisons:
        return {"comparisons": {}, "aggregate": {}}

    keys = ("field_similarity", "paragraph_similarity", "requirement_coverage", "traceability_coverage")
    aggregate = {
        key: round(sum(comp.get(key, 0) for comp in comparisons.values()) / len(comparisons), 3)
        for key in keys
    }
    return {"comparisons": comparisons, "aggregate": aggregate}
