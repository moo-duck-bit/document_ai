"""Freeze v0.5 Document Harness baseline artifacts under reports/baselines/."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from document_ai.paths import PROJECT_ROOT
from document_ai.trial.git_info import collect_environment, collect_git_info
from document_ai.trial.models import BASELINE_COMMIT, BASELINE_SYSTEM_VERSION
from document_ai.trial.paths import DEFAULT_BASELINE_ROOT, rel_to_project, write_json, write_text


def freeze_baseline(
    *,
    system_version: str = BASELINE_SYSTEM_VERSION,
    system_commit: str = BASELINE_COMMIT,
    out_root: str | Path | None = None,
    run_pytest: bool = False,
) -> dict[str, Any]:
    """Copy existing benchmark/validation artifacts; do not regenerate case outputs."""
    root = Path(out_root) if out_root else DEFAULT_BASELINE_ROOT / system_version
    root.mkdir(parents=True, exist_ok=True)
    case_results = root / "case_results"
    case_results.mkdir(parents=True, exist_ok=True)

    git_info = collect_git_info()
    env = collect_environment()
    write_json(root / "git_info.json", git_info)
    write_json(root / "environment.json", env)

    copied: list[str] = []

    def _copy(src: Path, dst: Path) -> None:
        if not src.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel_to_project(dst))

    bench_json = PROJECT_ROOT / "data" / "eval" / "harness_benchmark" / "harness_benchmark_report.json"
    bench_md = PROJECT_ROOT / "data" / "eval" / "harness_benchmark" / "harness_benchmark_report.md"
    _copy(bench_json, root / "benchmark.json")
    _copy(bench_md, root / "benchmark.md")

    # Aggregate validation/quality summaries without mutating cases
    validation_summary: dict[str, Any] = {"cases": {}}
    quality_summary: dict[str, Any] = {"cases": {}}
    for case_id in ("lab_ec_sw", "inventory_mgmt", "hospital_reservation", "jm_collection"):
        case_dir = PROJECT_ROOT / "data" / "cases" / case_id
        for name in (
            "validation_report.json",
            "validation_report.md",
            "quality_report.md",
            "e2e_validation_report.json",
        ):
            src = case_dir / name
            if src.exists():
                _copy(src, case_results / case_id / name)
        vjson = case_dir / "validation_report.json"
        if vjson.exists():
            data = json.loads(vjson.read_text(encoding="utf-8"))
            validation_summary["cases"][case_id] = {
                "status": data.get("status"),
                "scores": data.get("scores"),
            }
        qmd = case_dir / "quality_report.md"
        e2e = case_dir / "e2e_validation_report.json"
        if e2e.exists():
            data = json.loads(e2e.read_text(encoding="utf-8"))
            quality_summary["cases"][case_id] = {
                "status": data.get("status"),
                "quality": (data.get("quality") or {}).get("scores"),
            }
        elif qmd.exists():
            quality_summary["cases"][case_id] = {"quality_report": rel_to_project(qmd)}

    write_json(root / "validation_summary.json", validation_summary)
    write_json(root / "quality_summary.json", quality_summary)

    pytest_note = "not_run"
    if run_pytest:
        completed = subprocess.run(
            ["python", "-m", "pytest", "-q", "--tb=no"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        text = (completed.stdout or "") + "\n" + (completed.stderr or "")
        write_text(root / "pytest_result.txt", text)
        pytest_note = f"exit={completed.returncode}"
    else:
        write_text(
            root / "pytest_result.txt",
            "Pytest not re-executed during baseline freeze to avoid long runs.\n"
            "v0.5 release note: 297 passed at tag v0.5-document-harness (d73fc18).\n"
            "Re-run with: python -m document_ai.cli baseline-freeze --run-pytest\n",
        )
        pytest_note = "deferred (v0.5 claimed 297 passed)"

    warnings: list[str] = []
    commit = str(git_info.get("commit_short") or "")
    if system_commit and commit and not str(git_info.get("commit", "")).startswith(system_commit):
        if not commit.startswith(system_commit[:7]):
            warnings.append(
                f"HEAD commit {commit} does not match freeze target {system_commit}"
            )

    report = f"""# Baseline Report — {system_version}

## Freeze identity

- system_version: `{system_version}`
- expected_commit: `{system_commit}`
- head_commit: `{git_info.get('commit_short')}`
- branch: `{git_info.get('branch')}`
- tags_at_head: `{git_info.get('tags_at_head')}`
- dirty: `{git_info.get('dirty')}`

## Policy

- This directory is a **read-only snapshot** of v0.5 evaluation artifacts.
- Do not overwrite case outputs to refresh this baseline.
- Do not mutate tag `{system_version}`.
- New experiments must write to `data/trials/` or a new baseline folder.

## Copied artifacts

{chr(10).join(f'- `{p}`' for p in copied) or '- (none found)'}

## Pytest

- {pytest_note}

## Warnings

{chr(10).join(f'- {w}' for w in warnings) or '- none'}
"""
    write_text(root / "baseline_report.md", report)
    meta = {
        "ok": True,
        "baseline_dir": rel_to_project(root),
        "system_version": system_version,
        "system_commit": system_commit,
        "copied": copied,
        "warnings": warnings,
        "pytest": pytest_note,
        "git": git_info,
    }
    write_json(root / "freeze_manifest.json", meta)
    return meta
