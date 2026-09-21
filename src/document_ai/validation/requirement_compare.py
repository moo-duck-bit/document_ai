"""Requirement-level comparison for MDSR documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.learn.mdsr_diff import REQ_LABELS, extract_req_blocks
from document_ai.learn.docx_io import load_document
from document_ai.validation.docx_compare import text_similarity


def _block_text(block) -> str:
    labels = block.by_label()
    parts = [labels.get(label, "") for label in REQ_LABELS]
    parts.extend(block.unlabeled_values())
    return "\n".join(p for p in parts if p.strip())


def _completeness_ratio(block) -> float:
    labels = block.by_label()
    checks = 0
    passed = 0
    for label in ("설명", "목적", "기준"):
        checks += 1
        if labels.get(label, "").strip():
            passed += 1
    if block.unlabeled_values():
        checks += 1
        passed += 1
    return passed / checks if checks else 0.0


def compare_requirements(
    generated_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    generated_path = generated_path.resolve()
    gold_path = gold_path.resolve()
    gen_blocks = extract_req_blocks(load_document(generated_path))
    gold_blocks = extract_req_blocks(load_document(gold_path))

    all_ids = sorted(
        set(gen_blocks) | set(gold_blocks),
        key=lambda rid: gen_blocks.get(rid, gold_blocks[rid]).req_num,  # type: ignore[union-attr]
    )

    per_req: list[dict[str, Any]] = []
    similarities: list[float] = []
    completeness_scores: list[float] = []
    missing_in_generated: list[str] = []
    extra_in_generated: list[str] = []
    high_risk: list[dict[str, Any]] = []

    for req_id in all_ids:
        gold = gold_blocks.get(req_id)
        generated = gen_blocks.get(req_id)
        if gold is None:
            extra_in_generated.append(req_id)
            high_risk.append(
                {
                    "req_id": req_id,
                    "kind": "extra_in_generated",
                    "detail": "Generated document has requirement not present in gold",
                }
            )
            continue
        if generated is None:
            missing_in_generated.append(req_id)
            high_risk.append(
                {
                    "req_id": req_id,
                    "kind": "missing_in_generated",
                    "detail": "Gold requirement missing from generated document",
                }
            )
            continue

        sim = text_similarity(_block_text(generated), _block_text(gold))
        similarities.append(sim)
        completeness = _completeness_ratio(generated)
        completeness_scores.append(completeness)

        gold_labels = gold.by_label()
        gen_labels = generated.by_label()
        for label in REQ_LABELS:
            if gold_labels.get(label, "").strip() and not gen_labels.get(label, "").strip():
                high_risk.append(
                    {
                        "req_id": req_id,
                        "kind": f"missing_{label}",
                        "detail": f"Gold has {label} but generated is empty",
                    }
                )

        per_req.append(
            {
                "req_id": req_id,
                "text_similarity": round(sim, 3),
                "completeness": round(completeness, 3),
                "generated_len": generated.total_content_len(),
                "gold_len": gold.total_content_len(),
            }
        )

        if sim < 0.35 and gold.total_content_len() > 40:
            high_risk.append(
                {
                    "req_id": req_id,
                    "kind": "low_text_similarity",
                    "detail": f"Requirement text similarity {sim:.2f} vs gold",
                    "similarity": round(sim, 3),
                }
            )

    count_match = 0.0
    if gold_blocks or gen_blocks:
        count_match = min(len(gen_blocks), len(gold_blocks)) / max(len(gen_blocks), len(gold_blocks))

    return {
        "requirement_count_match": round(count_match, 3),
        "gold_requirement_count": len(gold_blocks),
        "generated_requirement_count": len(gen_blocks),
        "requirement_text_similarity": round(
            sum(similarities) / len(similarities) if similarities else 1.0,
            3,
        ),
        "requirement_completeness": round(
            sum(completeness_scores) / len(completeness_scores) if completeness_scores else 1.0,
            3,
        ),
        "missing_in_generated": missing_in_generated,
        "extra_in_generated": extra_in_generated,
        "per_requirement": per_req[:50],
        "high_risk": high_risk[:30],
    }
