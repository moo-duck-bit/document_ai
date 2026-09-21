"""Low-level DOCX extraction and similarity helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_ai.learn.docx_io import load_document, paragraph_deep_text, table_matrix
from document_ai.quality.patterns import DOMAIN_FOREIGN_TERMS, PLACEHOLDER_PATTERNS
from document_ai.retrieval.embedding import TfidfEmbedding
from document_ai.retrieval.similarity import cosine_similarity

REQ_ID_RE = re.compile(r"^Req\.\s*\d+", re.I)
TRACE_ID_RE = re.compile(r"^[A-Z]{2}-\d+")


def extract_paragraphs(doc_path: Path) -> list[str]:
    doc = load_document(doc_path)
    return [paragraph_deep_text(p) for p in doc.paragraphs if paragraph_deep_text(p).strip()]


def extract_product_fields(doc_path: Path) -> dict[str, str]:
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


def requirement_table_counts(doc_path: Path) -> tuple[int, int]:
    """Return (filled_tables, total_req_tables)."""
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


def traceability_table_counts(doc_path: Path) -> tuple[int, int]:
    """Return (filled_rows, total_trace_rows)."""
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


def count_placeholders(doc_path: Path) -> int:
    doc = load_document(doc_path)
    count = 0
    texts: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph_deep_text(paragraph)
        if text.strip():
            texts.append(text)
    for table in doc.tables:
        for row in table_matrix(table):
            for cell in row:
                if cell.strip():
                    texts.append(cell)
    for text in texts:
        for _, pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(text):
                count += 1
                break
    return count


def count_domain_mismatches(doc_path: Path, *, domain: str) -> int:
    if not domain:
        return 0
    patterns = DOMAIN_FOREIGN_TERMS.get(domain, [])
    if not patterns:
        return 0
    doc = load_document(doc_path)
    count = 0
    texts: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph_deep_text(paragraph)
        if text.strip():
            texts.append(text)
    for table in doc.tables:
        for row in table_matrix(table):
            for cell in row:
                if cell.strip():
                    texts.append(cell)
    for text in texts:
        for _, pattern in patterns:
            if pattern.search(text):
                count += 1
                break
    return count


def field_similarity(generated: dict[str, str], gold: dict[str, str]) -> float:
    if not gold:
        return 1.0
    keys = set(gold) & set(generated)
    if not keys:
        return 0.0
    matches = sum(1 for key in keys if generated[key] and generated[key] == gold[key])
    return matches / len(keys)


def paragraph_similarity(generated: list[str], gold: list[str]) -> float:
    if not generated and not gold:
        return 1.0
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


def text_similarity(left: str, right: str) -> float:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    tfidf = TfidfEmbedding()
    tfidf.fit([left, right])
    vecs = tfidf.transform([left, right])
    return cosine_similarity(vecs[0], vecs[1])


def count_match_ratio(generated: int, gold: int) -> float:
    if gold == 0 and generated == 0:
        return 1.0
    if gold == 0 or generated == 0:
        return 0.0
    return min(generated, gold) / max(generated, gold)


def summarize_docx_pair(
    generated_path: Path,
    gold_path: Path,
    *,
    domain: str = "",
) -> dict[str, Any]:
    generated_path = generated_path.resolve()
    gold_path = gold_path.resolve()
    gen_paras = extract_paragraphs(generated_path)
    gold_paras = extract_paragraphs(gold_path)
    gen_fields = extract_product_fields(generated_path)
    gold_fields = extract_product_fields(gold_path)
    req_filled, req_total = requirement_table_counts(generated_path)
    gold_req_filled, gold_req_total = requirement_table_counts(gold_path)
    trace_filled, trace_total = traceability_table_counts(generated_path)
    gold_trace_filled, gold_trace_total = traceability_table_counts(gold_path)

    return {
        "generated": str(generated_path),
        "gold": str(gold_path),
        "field_similarity": round(field_similarity(gen_fields, gold_fields), 3),
        "paragraph_similarity": round(paragraph_similarity(gen_paras, gold_paras), 3),
        "requirement_counts": {
            "generated": {"filled": req_filled, "total": req_total},
            "gold": {"filled": gold_req_filled, "total": gold_req_total},
        },
        "requirement_count_match": round(count_match_ratio(req_total, gold_req_total), 3),
        "requirement_coverage": round(req_filled / req_total, 3) if req_total else 1.0,
        "traceability_counts": {
            "generated": {"filled": trace_filled, "total": trace_total},
            "gold": {"filled": gold_trace_filled, "total": gold_trace_total},
        },
        "traceability_coverage": round(trace_filled / trace_total, 3) if trace_total else 1.0,
        "residual_placeholder_count": count_placeholders(generated_path),
        "domain_mismatch_count": count_domain_mismatches(generated_path, domain=domain),
    }
