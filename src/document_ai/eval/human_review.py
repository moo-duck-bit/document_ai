"""Human review checklist generation for document validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_CHECKS = [
    ("figure", "Figure / diagram placeholders — replace or confirm intentional captions"),
    ("table", "Tables — verify Req / design / traceability tables are complete"),
    ("terminology", "Domain terminology — no foreign-domain product or brand leakage"),
    ("regulation", "Regulation / standards references — PCI, OWASP, PIPA, etc. match case facts"),
    ("traceability", "Traceability rows — IA/UC/SI linked_reqs align with MDSR requirements"),
    ("product_name", "Product name / model consistency across cover, overview, and tables"),
    ("placeholders", "Residual placeholders — XX-XX-XXXX, empty cells, template leftovers"),
]


def build_human_review_items(result: dict[str, Any]) -> list[dict[str, str]]:
    """Structured checklist items derived from validation result + standard categories."""
    items: list[dict[str, str]] = []
    for category, prompt in DEFAULT_CHECKS:
        items.append({"category": category, "prompt": prompt, "status": "pending"})

    scores = result.get("scores", {})
    metrics = result.get("metrics", {})
    semantic = result.get("semantic") or {}

    if scores.get("mdsr", 100) < 85:
        items.append(
            {
                "category": "mdsr_score",
                "prompt": f"MDSR score {scores.get('mdsr')} < 85 — review section/requirement gaps vs gold",
                "status": "attention",
            }
        )
    if scores.get("mddr", 100) < 85:
        items.append(
            {
                "category": "mddr_score",
                "prompt": f"MDDR score {scores.get('mddr')} < 85 — review design blocks vs gold",
                "status": "attention",
            }
        )
    if metrics.get("residual_placeholder_count", 0):
        items.append(
            {
                "category": "placeholders",
                "prompt": f"Residual placeholder count = {metrics.get('residual_placeholder_count')}",
                "status": "attention",
            }
        )
    if metrics.get("domain_mismatch_count", 0):
        items.append(
            {
                "category": "terminology",
                "prompt": f"Domain mismatch count = {metrics.get('domain_mismatch_count')}",
                "status": "attention",
            }
        )
    if semantic.get("missing_requirement_ids"):
        missing = ", ".join(semantic["missing_requirement_ids"][:8])
        items.append(
            {
                "category": "requirements",
                "prompt": f"Missing requirement IDs vs gold_fields: {missing}",
                "status": "attention",
            }
        )
    if semantic.get("missing_design_ids"):
        missing = ", ".join(semantic["missing_design_ids"][:8])
        items.append(
            {
                "category": "design",
                "prompt": f"Missing design IDs vs gold_fields: {missing}",
                "status": "attention",
            }
        )
    for risk in result.get("high_risk_differences", [])[:8]:
        req = risk.get("req_id") or risk.get("requirement", "")
        detail = risk.get("detail") or risk.get("kind", "")
        items.append(
            {
                "category": "high_risk",
                "prompt": f"{req}: {detail}" if req else str(detail),
                "status": "attention",
            }
        )
    return items


def render_human_review_checklist_md(result: dict[str, Any]) -> str:
    case = result.get("case", "")
    product = result.get("product_name", "")
    domain = result.get("domain", "")
    scores = result.get("scores", {})
    semantic = result.get("semantic") or {}
    items = build_human_review_items(result)

    lines = [
        f"# Human Review Checklist — {case}",
        "",
        f"**Product:** {product}  ",
        f"**Domain:** {domain}  ",
        f"**Validation overall:** {scores.get('overall', '-')}  "
        f"(MDSR {scores.get('mdsr', '-')}, MDDR {scores.get('mddr', '-')})",
        "",
    ]
    if semantic:
        lines.extend(
            [
                "## Semantic (gold_fields)",
                "",
                f"- Semantic overall: {semantic.get('semantic_overall', '-')}",
                f"- Requirement ID coverage: {semantic.get('semantic_requirement_id_coverage', '-')}",
                f"- Design ID coverage: {semantic.get('semantic_design_id_coverage', '-')}",
                f"- Traceability coverage: {semantic.get('semantic_traceability_coverage', '-')}",
                "",
            ]
        )

    lines.extend(
        [
            "## Review Items",
            "",
            "| Category | Status | Check |",
            "|----------|--------|-------|",
        ]
    )
    for item in items:
        lines.append(
            f"| {item['category']} | {item['status']} | [ ] {item['prompt']} |"
        )

    lines.extend(
        [
            "",
            "## Sign-off",
            "",
            "- Reviewer: ____________________",
            "- Date: ____________________",
            "- Decision: [ ] Approve as gold  [ ] Revise generation  [ ] Revise gold_fields",
            "",
        ]
    )
    return "\n".join(lines)


def write_human_review_checklist(result: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_human_review_checklist_md(result), encoding="utf-8")
    return path
