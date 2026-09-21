"""Markdown quality report generator."""

from __future__ import annotations

from typing import Any

from document_ai.quality.scorer import score_status


def _group_findings(findings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {"fail": [], "warning": [], "info": []}
    for finding in findings:
        severity = finding.get("severity", "info")
        if severity == "fail":
            grouped["fail"].append(finding)
        elif severity == "warning":
            grouped["warning"].append(finding)
        else:
            grouped["info"].append(finding)
    return grouped


def _format_finding_list(findings: list[dict[str, Any]], limit: int = 15) -> list[str]:
    lines: list[str] = []
    for finding in findings[:limit]:
        loc = finding.get("location", "")
        msg = finding.get("message", "")
        excerpt = finding.get("excerpt", "")
        auto = "auto-fix" if finding.get("auto_fixable") else "human review"
        line = f"- [{finding.get('category')}] {loc}: {msg} ({auto})"
        if excerpt:
            line += f"\n  - excerpt: `{excerpt[:100]}`"
        lines.append(line)
    if len(findings) > limit:
        lines.append(f"- ... and {len(findings) - limit} more")
    return lines


def render_quality_report(result: dict[str, Any]) -> str:
    scores = result.get("scores", {})
    overall = scores.get("overall", 0)
    status = result.get("status", score_status(overall))
    findings = result.get("findings", [])
    grouped = _group_findings(findings)
    comparison = result.get("comparison", {})

    lines = [
        f"# Document Quality Report — {result.get('case', '')}",
        "",
        f"**Overall:** {status} ({overall}/100)",
        "",
        f"**Product:** {result.get('product_name', '')} | **Domain:** {result.get('domain', '')}",
        "",
        "## Scores",
        "",
        "| Dimension | Score | Status |",
        "|-----------|------:|--------|",
    ]

    for key, label in [
        ("structure", "Structure"),
        ("terminology", "Terminology"),
        ("completeness", "Completeness"),
        ("consistency", "Consistency"),
        ("traceability", "Traceability"),
        ("residual_text", "Residual Text"),
        ("overall", "Overall"),
    ]:
        value = scores.get(key, 0)
        lines.append(f"| {label} | {value} | {score_status(value)} |")

    lines.extend(["", "## Findings", ""])

    if grouped["fail"]:
        lines.append("### FAIL")
        lines.extend(_format_finding_list(grouped["fail"]))
        lines.append("")
    else:
        lines.extend(["### FAIL", "- None", ""])

    if grouped["warning"]:
        lines.append("### WARNING")
        lines.extend(_format_finding_list(grouped["warning"]))
        lines.append("")
    else:
        lines.extend(["### WARNING", "- None", ""])

    lines.extend(["### PASS", f"- Documents analyzed: {len(result.get('documents', {}))}", ""])

    if comparison.get("aggregate"):
        agg = comparison["aggregate"]
        lines.extend(
            [
                "## Gold Comparison",
                "",
                "| Metric | Score |",
                "|--------|------:|",
                f"| Field similarity | {agg.get('field_similarity', 0):.1%} |",
                f"| Paragraph similarity | {agg.get('paragraph_similarity', 0):.1%} |",
                f"| Requirement coverage | {agg.get('requirement_coverage', 0):.1%} |",
                f"| Traceability coverage | {agg.get('traceability_coverage', 0):.1%} |",
                "",
            ]
        )
        for label, comp in comparison.get("comparisons", {}).items():
            lines.append(
                f"- **{label}**: field={comp.get('field_similarity', 0):.1%}, "
                f"paragraph={comp.get('paragraph_similarity', 0):.1%}, "
                f"req={comp.get('requirement_coverage', 0):.1%}, "
                f"trace={comp.get('traceability_coverage', 0):.1%}"
            )
        lines.append("")

    auto_fix = [f for f in findings if f.get("auto_fixable")]
    human = [f for f in findings if not f.get("auto_fixable")]

    lines.extend(["## Auto-fixable Items", ""])
    if auto_fix:
        for finding in auto_fix[:20]:
            lines.append(f"- [{finding.get('category')}] {finding.get('message')} @ {finding.get('location')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Human Review Required", ""])
    if human:
        for finding in human[:20]:
            lines.append(f"- [{finding.get('category')}] {finding.get('message')} @ {finding.get('location')}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Human Review Checklist",
            "- [ ] 표지·승인자 이름/직함/날짜",
            "- [ ] 도메인 용어·비즈니스 시나리오 정확성",
            "- [ ] Req. 설명·목적·기준 문장 품질",
            "- [ ] 추적성 매트릭스 연결 정확성",
            "- [ ] MDDR Figure/Table 캡션",
            "",
        ]
    )
    return "\n".join(lines)
