"""Document Harness multi-case benchmark (quality + validation)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.eval.real_project_runner import run_project_e2e_validation

DEFAULT_CONFIG_PATH = Path("data/eval/document_harness_benchmark.json")


def load_harness_benchmark_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    return json.loads(config_path.read_text(encoding="utf-8"))


def _case_score(result: dict[str, Any]) -> float:
    quality = result.get("quality", {}).get("scores", {}).get("overall", 0.0)
    validation = result.get("validation", {}).get("scores", {}).get("overall")
    xxcs = result.get("validation", {}).get("scores", {}).get("xxcs")
    parts = [float(quality)]
    if validation is not None:
        parts.append(float(validation))
    if xxcs is not None:
        parts.append(float(xxcs))
    return round(sum(parts) / len(parts), 1)


def _filter_cases(
    cases_cfg: list[dict[str, Any]],
    *,
    case_filter: str | None = None,
    split: str | None = None,
    holdout_only: bool = False,
) -> list[dict[str, Any]]:
    filtered = list(cases_cfg)
    if case_filter:
        filtered = [c for c in filtered if c.get("case_id") == case_filter]
    if holdout_only:
        filtered = [c for c in filtered if c.get("split") == "holdout"]
    elif split:
        filtered = [c for c in filtered if c.get("split", "train") == split]
    return filtered


def run_harness_benchmark(
    *,
    config_path: str | Path | None = None,
    out_dir: str | Path = "data/eval/harness_benchmark",
    force_generate: bool = False,
    case_filter: str | None = None,
    split: str | None = None,
    holdout_only: bool = False,
) -> dict[str, Any]:
    config = load_harness_benchmark_config(config_path)
    cases_cfg = _filter_cases(
        config.get("cases", []),
        case_filter=case_filter,
        split=split,
        holdout_only=holdout_only,
    )

    case_results: list[dict[str, Any]] = []
    for entry in cases_cfg:
        case_dir = Path(entry["case_dir"])
        gold_mdsr = Path(entry["gold_mdsr"]) if entry.get("gold_mdsr") else None
        gold_mddr = Path(entry["gold_mddr"]) if entry.get("gold_mddr") else None
        result = run_project_e2e_validation(
            case_dir,
            force_generate=force_generate or bool(entry.get("force_generate")),
            gold_mdsr=gold_mdsr,
            gold_mddr=gold_mddr,
            skip_generate=bool(entry.get("skip_generate")),
        )
        result["benchmark_score"] = _case_score(result)
        result["benchmark_entry"] = entry.get("case_id", case_dir.name)
        result["split"] = entry.get("split", "train")
        case_results.append(result)

    def _subset_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "cases_run": 0,
                "passed": 0,
                "warning": 0,
                "failed": 0,
                "overall_score": 0.0,
            }
        scores = [r.get("benchmark_score", 0.0) for r in rows]
        return {
            "cases_run": len(rows),
            "passed": sum(1 for r in rows if r.get("status") == "PASS"),
            "warning": sum(1 for r in rows if r.get("status") == "WARNING"),
            "failed": sum(1 for r in rows if r.get("status") == "FAIL"),
            "overall_score": round(sum(scores) / len(scores), 1),
        }

    all_stats = _subset_stats(case_results)
    train_rows = [r for r in case_results if r.get("split") == "train"]
    holdout_rows = [r for r in case_results if r.get("split") == "holdout"]

    report: dict[str, Any] = {
        "version": config.get("version", "1.0"),
        "benchmark_type": "document_harness_e2e",
        "split_filter": "holdout" if holdout_only else (split or "all"),
        "cases_run": all_stats["cases_run"],
        "passed": all_stats["passed"],
        "warning": all_stats["warning"],
        "failed": all_stats["failed"],
        "overall_score": all_stats["overall_score"],
        "train": _subset_stats(train_rows),
        "holdout": _subset_stats(holdout_rows),
        "case_results": case_results,
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_holdout" if holdout_only else ""
    json_path = out_dir / f"harness_benchmark_report{suffix}.json"
    md_path = out_dir / f"harness_benchmark_report{suffix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    report["output_paths"] = {
        "json": str(json_path),
        "markdown": str(md_path),
    }
    return report


def merge_into_platform_benchmark(
    harness_report: dict[str, Any],
    platform_report_path: str | Path,
) -> dict[str, Any]:
    """Attach harness E2E results to an existing platform benchmark_report.json."""
    platform_path = Path(platform_report_path)
    platform_report = json.loads(platform_path.read_text(encoding="utf-8"))
    platform_report["harness_validation"] = {
        "overall_score": harness_report.get("overall_score"),
        "holdout_score": (harness_report.get("holdout") or {}).get("overall_score"),
        "train_score": (harness_report.get("train") or {}).get("overall_score"),
        "cases_run": harness_report.get("cases_run"),
        "passed": harness_report.get("passed"),
        "failed": harness_report.get("failed"),
        "case_results": [
            {
                "case_id": r.get("case_id"),
                "split": r.get("split"),
                "status": r.get("status"),
                "benchmark_score": r.get("benchmark_score"),
                "quality_overall": r.get("quality", {}).get("scores", {}).get("overall"),
                "validation_overall": r.get("validation", {}).get("scores", {}).get("overall"),
            }
            for r in harness_report.get("case_results", [])
        ],
    }
    platform_path.write_text(json.dumps(platform_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return platform_report


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Document Harness Benchmark Report",
        "",
        f"- **Overall score:** {report.get('overall_score', 0)}",
        f"- **Split filter:** {report.get('split_filter', 'all')}",
        f"- **Cases:** {report.get('cases_run', 0)} "
        f"(PASS {report.get('passed', 0)} / WARNING {report.get('warning', 0)} / FAIL {report.get('failed', 0)})",
        "",
    ]
    train = report.get("train") or {}
    holdout = report.get("holdout") or {}
    if train.get("cases_run") or holdout.get("cases_run"):
        lines.extend(
            [
                "## Split Summary",
                "",
                f"- **Train:** score={train.get('overall_score', 0)} "
                f"(n={train.get('cases_run', 0)}, pass={train.get('passed', 0)})",
                f"- **Holdout:** score={holdout.get('overall_score', 0)} "
                f"(n={holdout.get('cases_run', 0)}, pass={holdout.get('passed', 0)})",
                "",
            ]
        )
    lines.extend(
        [
            "## Case Results",
            "",
            "| Case | Split | Status | Benchmark | Quality | Validation |",
            "|------|-------|--------|----------:|--------:|-----------:|",
        ]
    )
    for row in report.get("case_results", []):
        quality = row.get("quality", {}).get("scores", {}).get("overall", "-")
        validation = row.get("validation", {}).get("scores", {}).get("overall", "-")
        if row.get("validation", {}).get("status") == "SKIPPED":
            validation = "SKIPPED"
        lines.append(
            f"| {row.get('case_id', '')} | {row.get('split', 'train')} | {row.get('status', '')} | "
            f"{row.get('benchmark_score', '-')} | {quality} | {validation} |"
        )
        xxcs = row.get("validation", {}).get("scores", {}).get("xxcs")
        if xxcs is not None:
            lines.append(f"  - XXCS validation score: {xxcs}")
    lines.append("")
    return "\n".join(lines)
