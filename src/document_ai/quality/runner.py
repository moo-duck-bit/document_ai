"""Quality analysis orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.quality.analyzer import analyze_case
from document_ai.quality.comparison import compare_case
from document_ai.quality.report import render_quality_report
from document_ai.quality.scorer import score_analysis, score_status


def run_document_quality(
    case_dir: Path,
    *,
    gold_mdsr: Path | None = None,
    gold_mddr: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    analysis = analyze_case(case_dir)
    comparison = compare_case(case_dir, gold_mdsr=gold_mdsr, gold_mddr=gold_mddr)
    aggregate = comparison.get("aggregate") or {}
    scores = score_analysis(analysis, comparison=aggregate if aggregate else None)
    scores_dict = scores.to_dict()
    status = score_status(scores.overall)

    result: dict[str, Any] = {
        "case": analysis["case"],
        "domain": analysis.get("domain", ""),
        "product_name": analysis.get("product_name", ""),
        "status": status,
        "scores": scores_dict,
        "findings": analysis.get("findings", []),
        "documents": analysis.get("documents", {}),
        "comparison": comparison,
        "auto_fixable_count": sum(1 for f in analysis.get("findings", []) if f.get("auto_fixable")),
        "human_review_count": sum(1 for f in analysis.get("findings", []) if not f.get("auto_fixable")),
    }

    if report_path:
        report_path = report_path.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_quality_report(result), encoding="utf-8")
        result["report_path"] = str(report_path)

    return result
