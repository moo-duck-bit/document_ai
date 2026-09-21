from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def generate_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Platform Benchmark Report",
        "",
        f"- **Version:** {report.get('version', '1.0')}",
        f"- **Overall score:** {report.get('overall_score', 0.0)}",
        f"- **Scenarios run:** {', '.join(report.get('scenarios_run', []))}",
        "",
    ]

    regression = report.get("regression", {})
    if regression.get("baseline_available"):
        status = "PASSED" if regression.get("passed") else "FAILED"
        lines.extend(
            [
                "## Regression",
                "",
                f"- Status: **{status}**",
                f"- Regressions: {regression.get('regression_count', 0)}",
                "",
            ]
        )

    sections = [
        ("Planner", "planner_metrics"),
        ("Runtime", "runtime_metrics"),
        ("Document Harness", "document_metrics"),
        ("Operation Harness", "operation_metrics"),
        ("Memory", "memory_metrics"),
        ("Self Improvement", "improvement_metrics"),
        ("Collaboration", "collaboration_metrics"),
    ]

    for title, key in sections:
        metrics = report.get(key, {})
        lines.append(f"## {title}")
        lines.append("")
        if not metrics:
            lines.append("_No metrics collected._")
            lines.append("")
            continue
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for metric_name, value in metrics.items():
            if isinstance(value, (dict, list)):
                continue
            lines.append(f"| {metric_name} | {value} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reports(
    report: dict[str, Any],
    out_dir: str | Path,
) -> dict[str, str]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "benchmark_report.json"
    md_path = output_dir / "benchmark_report.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(generate_markdown_report(report), encoding="utf-8")

    return {
        "benchmark_report_json": str(json_path),
        "benchmark_report_md": str(md_path),
    }
