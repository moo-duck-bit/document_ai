"""Quality score calculator (0–100 per dimension)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QualityScores:
    structure: float
    terminology: float
    completeness: float
    consistency: float
    traceability: float
    residual_text: float
    overall: float

    def to_dict(self) -> dict[str, float]:
        return {
            "structure": round(self.structure, 1),
            "terminology": round(self.terminology, 1),
            "completeness": round(self.completeness, 1),
            "consistency": round(self.consistency, 1),
            "traceability": round(self.traceability, 1),
            "residual_text": round(self.residual_text, 1),
            "overall": round(self.overall, 1),
        }


def _clamp(score: float) -> float:
    return max(0.0, min(100.0, score))


def _count_findings(findings: list[dict[str, Any]], category: str, severity: str | None = None) -> int:
    total = 0
    for finding in findings:
        if finding.get("category") != category:
            continue
        if severity and finding.get("severity") != severity:
            continue
        total += 1
    return total


def score_analysis(analysis: dict[str, Any], *, comparison: dict[str, Any] | None = None) -> QualityScores:
    findings = analysis.get("findings", [])
    documents = analysis.get("documents", {})
    product_name = analysis.get("product_name", "")

    structure_penalty = 0
    completeness_ratio_sum = 0.0
    completeness_parts = 0
    traceability_ratio_sum = 0.0
    traceability_parts = 0

    for doc in documents.values():
        review = doc.get("structure_review") or {}
        issue_count = review.get("issue_count", 0)
        residual_count = review.get("residual_count", 0)
        structure_penalty += issue_count * 4 + residual_count * 3

        expected = review.get("requirements_expected") or review.get("design_items_expected")
        filled = review.get("design_blocks_filled")
        if expected:
            if filled is not None:
                completeness_ratio_sum += filled / max(expected, 1)
            else:
                req_issues = len(review.get("issues", []))
                completeness_ratio_sum += max(0.0, 1.0 - req_issues / max(expected, 1))
            completeness_parts += 1

        trace_issues = [
            issue for issue in review.get("issues", []) if str(issue).startswith("traceability")
        ]
        if trace_issues:
            traceability_ratio_sum += max(0.0, 1.0 - len(trace_issues) / 10)
            traceability_parts += 1
        elif review.get("requirements_expected"):
            traceability_ratio_sum += 1.0
            traceability_parts += 1

    structure = _clamp(100.0 - structure_penalty)

    domain_mismatch = _count_findings(findings, "domain_mismatch")
    terminology = _clamp(100.0 - domain_mismatch * 5)

    if completeness_parts:
        completeness = _clamp(100.0 * (completeness_ratio_sum / completeness_parts))
    else:
        completeness = 100.0 if not _count_findings(findings, "structure", "fail") else 70.0

    consistency_hits = 0
    if product_name:
        for doc in documents.values():
            for finding in doc.get("findings", []):
                excerpt = finding.get("excerpt", "")
                if finding.get("category") == "mindrium" and product_name not in excerpt:
                    consistency_hits += 1
    consistency = _clamp(100.0 - consistency_hits * 8)

    if traceability_parts:
        traceability = _clamp(100.0 * (traceability_ratio_sum / traceability_parts))
    elif comparison and comparison.get("traceability_coverage") is not None:
        traceability = _clamp(100.0 * comparison["traceability_coverage"])
    else:
        traceability = 95.0

    placeholder = _count_findings(findings, "placeholder")
    mindrium = _count_findings(findings, "mindrium")
    duplicate = _count_findings(findings, "duplicate_paragraph")
    residual_text = _clamp(100.0 - placeholder * 8 - mindrium * 6 - duplicate * 2)

    if comparison:
        comp_boost = (
            comparison.get("field_similarity", 0) * 0.15
            + comparison.get("paragraph_similarity", 0) * 0.15
            + comparison.get("requirement_coverage", 0) * 0.2
            + comparison.get("traceability_coverage", 0) * 0.2
        ) * 100
        completeness = _clamp((completeness + comp_boost) / 2)

    overall = _clamp(
        structure * 0.2
        + terminology * 0.15
        + completeness * 0.2
        + consistency * 0.1
        + traceability * 0.15
        + residual_text * 0.2
    )

    return QualityScores(
        structure=structure,
        terminology=terminology,
        completeness=completeness,
        consistency=consistency,
        traceability=traceability,
        residual_text=residual_text,
        overall=overall,
    )


def score_status(score: float) -> str:
    if score >= 85:
        return "PASS"
    if score >= 70:
        return "WARNING"
    return "FAIL"
