from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def write_evaluation_report(
    metrics: dict[str, Any],
    predictions: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "metrics.json"
    md_path = out_dir / "metrics.md"

    json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = metrics.get("summary", {})
    cases = metrics.get("cases", [])

    lines = [
        "# Evaluation Report",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Score |",
        "|--------|-------|",
    ]
    for key, value in summary.items():
        lines.append(f"| `{key}` | {_format_pct(value)} |")

    lines.extend(["", f"**Cases evaluated:** {metrics.get('case_count', 0)}", ""])

    warning = metrics.get("warning")
    if warning:
        lines.extend(["", f"**Warning:** {warning}", ""])
    if metrics.get("case_count", 0) == 0:
        lines.extend(["**No scorable cases.**", ""])

    skipped_cases = metrics.get("skipped_cases") or []
    if skipped_cases:
        lines.extend(["## Skipped Cases", ""])
        lines.append(
            "These cases were not scored because they have no matching row in "
            "`expected_impacts.jsonl`."
        )
        lines.append("")
        for skipped in skipped_cases:
            case_id = skipped.get("case_id", "unknown")
            reason = skipped.get("reason", "unknown")
            lines.append(f"- **{case_id}**: {reason}")
        lines.append("")

    error_cases = metrics.get("error_cases") or []
    if error_cases:
        lines.extend(["## Error Cases", ""])
        lines.append("These cases failed during evaluation and were excluded from summary metrics.")
        lines.append("")
        for err in error_cases:
            case_id = err.get("case_id", "unknown")
            message = err.get("error_message") or err.get("reason", "unknown")
            lines.append(f"- **{case_id}**: {message}")
        lines.append("")

    orphan_expected_cases = metrics.get("orphan_expected_cases") or []
    if orphan_expected_cases:
        lines.extend(["## Orphan Expected Cases", ""])
        lines.append(
            "These `case_id` values appear in `expected_impacts.jsonl` but not in "
            "`change_cases.jsonl`. They were not scored."
        )
        lines.append("")
        for case_id in orphan_expected_cases:
            lines.append(f"- `{case_id}`")
        lines.append("")

    lines.extend(["## Case Details", ""])
    for case in cases:
        case_id = case.get("case_id", "unknown")
        lines.append(f"### {case_id}")
        lines.append("")
        for metric_key in summary:
            if metric_key in case:
                lines.append(f"- **{metric_key}**: {_format_pct(case[metric_key])}")
        details = case.get("details", {})
        if details:
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(details, ensure_ascii=False, indent=2))
            lines.append("```")
        lines.append("")

    lines.extend(["## Runtime Error Analysis", ""])
    if errors:
        for err in errors:
            lines.append(f"- **{err.get('case_id')}**: {err.get('error')}")
    else:
        lines.append("- No runtime errors during evaluation.")

    failed_cases = [
        c
        for c in cases
        if c.get("changed_req_id_detection_accuracy", 1.0) < 1.0
        or c.get("clarification_needed_accuracy", 1.0) < 1.0
        or c.get("linked_security_id_recall", 1.0) < 1.0
        or c.get("linked_test_id_recall", 1.0) < 1.0
    ]
    if failed_cases:
        lines.append("")
        lines.append("Cases below perfect score on key metrics:")
        for case in failed_cases:
            lines.append(f"- `{case.get('case_id')}`")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This evaluation compares Multi-Agent Harness predictions against expected impact "
            "labels defined in `expected_impacts.jsonl`. Recall metrics treat an empty expected "
            "set as fully satisfied (1.0) to avoid division-by-zero. `false_positive_rate` aggregates "
            "extra predicted IDs across requirement, security, test, design, and document targets.",
            "",
            "Use this report to compare harness vs single-LLM baselines by running the same "
            "`change_cases.jsonl` with different `method` values as baselines are added.",
            "",
        ]
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path
