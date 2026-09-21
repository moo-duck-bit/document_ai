"""trial-init: create isolated trial workspace."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.paths import PROJECT_ROOT
from document_ai.trial.dataset import ensure_dataset_manifest, load_dataset_manifest
from document_ai.trial.git_info import assert_system_version_match, collect_environment, collect_git_info
from document_ai.trial.models import (
    BASELINE_COMMIT,
    BASELINE_SYSTEM_VERSION,
    DOCUMENT_TYPES,
    TRIAL_TYPES,
    human_revision_template,
)
from document_ai.trial.paths import (
    ensure_trial_layout,
    rel_to_project,
    save_manifest,
    trial_dir,
    write_json,
    write_text,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_baseline_metrics() -> dict[str, Any]:
    bench = PROJECT_ROOT / "data" / "eval" / "harness_benchmark" / "harness_benchmark_report.json"
    e2e = PROJECT_ROOT / "data" / "cases" / "lab_ec_sw" / "e2e_validation_report.json"
    payload: dict[str, Any] = {"sources": []}
    if bench.exists():
        data = __import__("json").loads(bench.read_text(encoding="utf-8"))
        payload["harness_benchmark"] = {
            "overall_score": data.get("overall_score"),
            "cases_run": data.get("cases_run"),
            "passed": data.get("passed"),
            "train": data.get("train"),
            "holdout": data.get("holdout"),
            "path": rel_to_project(bench),
        }
        payload["sources"].append(rel_to_project(bench))
    if e2e.exists():
        data = __import__("json").loads(e2e.read_text(encoding="utf-8"))
        payload["lab_ec_sw_e2e"] = {
            "status": data.get("status"),
            "quality_overall": (data.get("quality") or {}).get("scores", {}).get("overall"),
            "validation_overall": (data.get("validation") or {}).get("scores", {}).get("overall"),
            "path": rel_to_project(e2e),
        }
        payload["sources"].append(rel_to_project(e2e))
    return payload


def _seed_synthetic_inputs(trial_path: Path, case_dir: Path) -> list[str]:
    """Copy safe reference inputs only — never gold or human_revised finals."""
    input_dir = trial_path / "input"
    reference_dir = trial_path / "reference"
    copied: list[str] = []
    for name in ("input.json", "requirements.json", "design_items.json", "security_tests.json"):
        src = case_dir / name
        if src.exists():
            dst = input_dir / name
            shutil.copy2(src, dst)
            copied.append(rel_to_project(dst))
    # Change request sample if present
    changes = case_dir / "changes"
    if changes.exists():
        for change_file in sorted(changes.glob("*.json"))[:1]:
            dst = input_dir / "change_request.json"
            shutil.copy2(change_file, dst)
            copied.append(rel_to_project(dst))
    # Optional meeting note placeholder
    note = input_dir / "README_INPUTS.md"
    write_text(
        note,
        "# Synthetic Trial Inputs\n\n"
        "This folder was seeded for framework validation only.\n"
        "Do not treat as a completed real-world Trial 1.\n",
    )
    copied.append(rel_to_project(note))
    # Reference: templates pointers only (no gold DOCX)
    write_text(
        reference_dir / "REFERENCE.md",
        "Reference materials for this trial should be prior version documents "
        "and templates only. Do not place gold or human-revised finals here.\n",
    )
    return copied


def init_trial(
    *,
    trial_id: str,
    case: str | Path,
    trial_type: str = "change_update",
    system_version: str = BASELINE_SYSTEM_VERSION,
    system_commit: str = BASELINE_COMMIT,
    synthetic: bool = False,
    trials_root: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if trial_type not in TRIAL_TYPES:
        raise ValueError(f"invalid trial_type: {trial_type}; expected one of {TRIAL_TYPES}")

    case_dir = Path(case)
    if not case_dir.is_absolute():
        case_dir = (PROJECT_ROOT / case_dir).resolve()
    if not case_dir.exists():
        raise FileNotFoundError(f"case directory not found: {case_dir}")

    path = trial_dir(trial_id, root=trials_root)
    if path.exists() and (path / "trial_manifest.json").exists() and not force:
        raise FileExistsError(f"trial already exists: {path} (use force=True to rebuild layout)")

    dirs = ensure_trial_layout(path)
    git_info = collect_git_info()
    env = collect_environment()
    version_warnings = assert_system_version_match(
        system_version=system_version,
        system_commit=system_commit,
        git_info=git_info,
    )
    ensure_dataset_manifest()
    baseline_metrics = _snapshot_baseline_metrics()

    document_types = list(DOCUMENT_TYPES)
    if not (case_dir / "output_xxcs.docx").exists() and not (case_dir / "security_tests.json").exists():
        document_types = ["MDSR", "MDDR"]

    manifest: dict[str, Any] = {
        "trial_id": path.name,
        "case_id": case_dir.name,
        "case_dir": rel_to_project(case_dir),
        "trial_type": trial_type,
        "system_version": system_version,
        "system_commit": system_commit,
        "document_types": document_types,
        "domain": "",
        "started_at": _utc_now(),
        "input_cutoff": "",
        "human_baseline_available": False,
        "reviewer_count": 1,
        "status": "prepared",
        "data_leakage_checked": False,
        "synthetic": bool(synthetic),
        "frozen": {
            "baseline_system_version": BASELINE_SYSTEM_VERSION,
            "baseline_commit": BASELINE_COMMIT,
            "git": git_info,
            "environment": env,
            "version_warnings": version_warnings,
        },
        "baseline_metrics_snapshot": baseline_metrics,
        "paths": {name: rel_to_project(p) for name, p in dirs.items()},
    }

    # Domain from project_manifest if present
    pm = case_dir / "project_manifest.json"
    if pm.exists():
        import json

        pdata = json.loads(pm.read_text(encoding="utf-8"))
        manifest["domain"] = pdata.get("domain") or pdata.get("project_type") or ""

    save_manifest(path, manifest)
    write_json(path / "input_manifest.json", {
        "trial_id": path.name,
        "status": "awaiting_inputs",
        "files": [],
        "synthetic": bool(synthetic),
    })
    write_json(path / "metrics" / "baseline_snapshot.json", baseline_metrics)
    write_json(
        path / "review" / "human_revision_record.template.json",
        human_revision_template(path.name, document_types),
    )
    write_text(
        path / "human_revised" / ".gitkeep",
        "",
    )

    seeded: list[str] = []
    if synthetic:
        seeded = _seed_synthetic_inputs(path, case_dir)
        write_json(
            path / "input_manifest.json",
            {
                "trial_id": path.name,
                "status": "seeded_synthetic",
                "files": seeded,
                "synthetic": True,
                "note": "Synthetic fixture only — not a completed real-world Trial 1.",
            },
        )

    write_json(path / "metrics" / "git_info.json", git_info)
    write_json(path / "metrics" / "environment.json", env)

    return {
        "ok": True,
        "trial_dir": rel_to_project(path),
        "manifest": manifest,
        "seeded_inputs": seeded,
        "version_warnings": version_warnings,
        "dataset_manifest": rel_to_project(ensure_dataset_manifest()),
    }
