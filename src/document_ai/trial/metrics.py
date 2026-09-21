"""Trial metrics helpers (time savings, edit burden aggregation)."""

from __future__ import annotations

from typing import Any


def time_saving_rate(
    *,
    manual_baseline_minutes: float | int | None,
    generation_minutes: float | int | None,
    revision_minutes: float | int | None,
) -> dict[str, Any]:
    if manual_baseline_minutes is None:
        return {
            "time_saving_rate": None,
            "status": "N/A",
            "reason": "manual_baseline_minutes missing",
            "manual_baseline_minutes": None,
            "total_assisted_minutes": None,
        }
    try:
        baseline = float(manual_baseline_minutes)
    except (TypeError, ValueError):
        return {
            "time_saving_rate": None,
            "status": "N/A",
            "reason": "invalid manual_baseline_minutes",
            "manual_baseline_minutes": manual_baseline_minutes,
            "total_assisted_minutes": None,
        }
    if baseline <= 0:
        return {
            "time_saving_rate": None,
            "status": "N/A",
            "reason": "manual_baseline_minutes must be > 0",
            "manual_baseline_minutes": baseline,
            "total_assisted_minutes": None,
        }
    gen = float(generation_minutes or 0.0)
    rev = float(revision_minutes or 0.0)
    assisted = gen + rev
    rate = (baseline - assisted) / baseline
    return {
        "time_saving_rate": round(rate, 4),
        "status": "ok",
        "manual_baseline_minutes": baseline,
        "harness_generation_minutes": gen,
        "human_revision_minutes": rev,
        "total_assisted_minutes": round(assisted, 2),
        "time_saved_minutes": round(baseline - assisted, 2),
    }


def edit_burden_score(diff_metrics: dict[str, Any]) -> float:
    """Higher means more human edit burden (0–100)."""
    modified = float(diff_metrics.get("modified_paragraph_ratio") or 0.0)
    added = float(diff_metrics.get("added_paragraph_ratio") or 0.0)
    deleted = float(diff_metrics.get("deleted_paragraph_ratio") or 0.0)
    cell_mod = float(diff_metrics.get("modified_table_cell_ratio") or 0.0)
    score = 100.0 * (0.35 * modified + 0.25 * added + 0.20 * deleted + 0.20 * cell_mod)
    return round(min(100.0, max(0.0, score)), 1)


def aggregate_human_ratings(document_reviews: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "content_accuracy",
        "completeness",
        "format_compliance",
        "traceability",
        "language_quality",
        "practical_usability",
    )
    sums = {f: 0.0 for f in fields}
    counts = {f: 0 for f in fields}
    for review in document_reviews:
        rating = review.get("rating") or {}
        for field in fields:
            value = rating.get(field)
            if isinstance(value, (int, float)) and value > 0:
                sums[field] += float(value)
                counts[field] += 1
    averages = {
        field: (round(sums[field] / counts[field], 2) if counts[field] else None)
        for field in fields
    }
    present = [v for v in averages.values() if v is not None]
    return {
        "per_dimension": averages,
        "overall": round(sum(present) / len(present), 2) if present else None,
        "documents_rated": sum(1 for r in document_reviews if any(
            isinstance((r.get("rating") or {}).get(f), (int, float))
            and (r.get("rating") or {}).get(f) > 0
            for f in fields
        )),
    }
