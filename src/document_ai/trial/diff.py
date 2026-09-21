"""Structural DOCX diff for generated vs human-revised documents."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from document_ai.learn.docx_io import load_document, paragraph_deep_text, table_matrix
from document_ai.trial.metrics import edit_burden_score
from document_ai.trial.models import empty_error_annotation
from document_ai.trial.paths import write_json
from document_ai.validation.docx_compare import extract_paragraphs


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def extract_table_cells(doc_path: Path) -> list[str]:
    doc = load_document(doc_path)
    cells: list[str] = []
    for table in doc.tables:
        for row in table_matrix(table):
            for cell in row:
                text = _normalize(cell)
                if text:
                    cells.append(text)
    return cells


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def compare_token_bags(generated: list[str], revised: list[str]) -> dict[str, Any]:
    gen_norm = [_normalize(x) for x in generated if _normalize(x)]
    rev_norm = [_normalize(x) for x in revised if _normalize(x)]
    gen_counts = Counter(gen_norm)
    rev_counts = Counter(rev_norm)
    shared = sum((gen_counts & rev_counts).values())
    only_gen = sum((gen_counts - rev_counts).values())
    only_rev = sum((rev_counts - gen_counts).values())
    # Approximate modified as min leftovers when both sides have extras
    modified = min(only_gen, only_rev)
    deleted = only_gen - modified
    added = only_rev - modified
    denom = max(len(gen_norm), 1)
    unchanged = shared
    return {
        "generated_count": len(gen_norm),
        "revised_count": len(rev_norm),
        "unchanged_count": unchanged,
        "modified_count": modified,
        "added_count": added,
        "deleted_count": deleted,
        "unchanged_ratio": _ratio(unchanged, denom),
        "modified_ratio": _ratio(modified, denom),
        "added_ratio": _ratio(added, denom),
        "deleted_ratio": _ratio(deleted, denom),
    }


def compare_docx_pair(generated: Path, revised: Path) -> dict[str, Any]:
    gen_paras = extract_paragraphs(generated)
    rev_paras = extract_paragraphs(revised)
    para = compare_token_bags(gen_paras, rev_paras)

    gen_cells = extract_table_cells(generated)
    rev_cells = extract_table_cells(revised)
    cells = compare_token_bags(gen_cells, rev_cells)

    metrics = {
        "generated": str(generated),
        "revised": str(revised),
        "unchanged_paragraph_ratio": para["unchanged_ratio"],
        "modified_paragraph_ratio": para["modified_ratio"],
        "added_paragraph_ratio": para["added_ratio"],
        "deleted_paragraph_ratio": para["deleted_ratio"],
        "unchanged_table_cell_ratio": cells["unchanged_ratio"],
        "modified_table_cell_ratio": cells["modified_ratio"],
        "paragraphs": para,
        "table_cells": cells,
    }
    metrics["document_level_edit_burden_score"] = edit_burden_score(metrics)
    return metrics


def suggest_error_candidates(diff: dict[str, Any], *, document_type: str) -> list[dict[str, Any]]:
    """Heuristic auto candidates — always unverified."""
    candidates: list[dict[str, Any]] = []
    para = diff.get("paragraphs") or {}
    if float(para.get("deleted_ratio") or 0) >= 0.05:
        item = empty_error_annotation(
            document_type=document_type,
            error_type="REDUNDANT_CONTENT",
            verified=False,
        )
        item["note"] = "Auto: substantial deleted content vs human revised"
        item["location"] = "paragraphs"
        candidates.append(item)
    if float(para.get("added_ratio") or 0) >= 0.05:
        item = empty_error_annotation(
            document_type=document_type,
            error_type="MISSING_CONTENT",
            verified=False,
        )
        item["note"] = "Auto: substantial added content in human revised"
        item["location"] = "paragraphs"
        candidates.append(item)
    if float(diff.get("modified_table_cell_ratio") or 0) >= 0.05:
        item = empty_error_annotation(
            document_type=document_type,
            error_type="FACT_ERROR",
            verified=False,
        )
        item["note"] = "Auto: many table cells changed"
        item["location"] = "tables"
        candidates.append(item)
    if not candidates:
        item = empty_error_annotation(
            document_type=document_type,
            error_type="NO_CHANGE_REQUIRED",
            verified=False,
        )
        item["note"] = "Auto: no large structural delta detected"
        item["severity"] = "style"
        candidates.append(item)
    return candidates


def diff_trial_documents(
    *,
    generated_dir: Path,
    revised_dir: Path,
    document_types: list[str],
    out_dir: Path | None = None,
) -> dict[str, Any]:
    mapping = {
        "MDSR": ("output_mdsr.docx", "revised_mdsr.docx", "generated_mdsr.docx"),
        "MDDR": ("output_mddr.docx", "revised_mddr.docx", "generated_mddr.docx"),
        "XXCS": ("output_xxcs.docx", "revised_xxcs.docx", "generated_xxcs.docx"),
    }
    results: dict[str, Any] = {"documents": {}, "error_candidates": []}
    for doc_type in document_types:
        names = mapping.get(doc_type)
        if not names:
            continue
        gen_path = None
        for name in (names[0], names[2], f"{doc_type.lower()}.docx"):
            candidate = generated_dir / name
            if candidate.exists():
                gen_path = candidate
                break
        rev_path = None
        for name in (names[1], names[0], names[2], f"{doc_type.lower()}.docx"):
            candidate = revised_dir / name
            if candidate.exists():
                rev_path = candidate
                break
        if not gen_path or not rev_path:
            results["documents"][doc_type] = {
                "status": "SKIPPED",
                "reason": "missing generated or human_revised DOCX",
                "generated": str(gen_path) if gen_path else "",
                "revised": str(rev_path) if rev_path else "",
            }
            continue
        pair = compare_docx_pair(gen_path, rev_path)
        pair["status"] = "ok"
        pair["document_type"] = doc_type
        results["documents"][doc_type] = pair
        results["error_candidates"].extend(suggest_error_candidates(pair, document_type=doc_type))

    if out_dir is not None:
        write_json(out_dir / "docx_diff.json", results)
    return results
