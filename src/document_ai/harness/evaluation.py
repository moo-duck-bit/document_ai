"""Evaluation step — audit metrics for harness pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.harness.review import review_case


def evaluate_case(case_dir: Path) -> dict[str, Any]:
    review = review_case(case_dir)
    return {
        "case": review["case"],
        "passed": review.get("ok", False),
        "metrics": {
            "mdsr_issues": (review.get("mdsr") or {}).get("review", {}).get("issue_count"),
            "mdsr_residual": (review.get("mdsr") or {}).get("review", {}).get("residual_count"),
            "mddr_issues": (review.get("mddr") or {}).get("review", {}).get("issue_count"),
            "design_blocks_filled": (review.get("mddr") or {}).get("review", {}).get("design_blocks_filled"),
        },
        "review": review,
    }
