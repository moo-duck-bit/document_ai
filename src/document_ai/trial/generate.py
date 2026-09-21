"""trial-generate: run harness into isolated trial output (never overwrite case)."""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.paths import PROJECT_ROOT
from document_ai.quality.runner import run_document_quality
from document_ai.trial.git_info import collect_environment, collect_git_info
from document_ai.trial.paths import (
    load_manifest,
    rel_to_project,
    save_manifest,
    sha256_file,
    trial_dir,
    write_json,
)
from document_ai.validation.runner import run_document_validation


OUTPUT_NAMES = {
    "MDSR": "output_mdsr.docx",
    "MDDR": "output_mddr.docx",
    "XXCS": "output_xxcs.docx",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _copy_case_isolated(source: Path, target: Path) -> Path:
    """Full case copy for isolated generation (excludes large unrelated dirs)."""
    if target.exists():
        shutil.rmtree(target)
    ignore = shutil.ignore_patterns(
        "executions",
        "execution_reviews",
        "__pycache__",
        ".git",
        "platform",
        "memory",
    )
    shutil.copytree(source, target, ignore=ignore)
    return target


def _copy_outputs_to_generated(work_case: Path, generated_dir: Path, document_types: list[str]) -> dict[str, str]:
    generated_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for doc_type in document_types:
        name = OUTPUT_NAMES[doc_type]
        src = work_case / name
        if src.exists():
            dst = generated_dir / name
            shutil.copy2(src, dst)
            # Also friendly names
            friendly = generated_dir / f"generated_{doc_type.lower()}.docx"
            shutil.copy2(src, friendly)
            copied[doc_type] = rel_to_project(dst)
    for report_name in (
        "quality_report.md",
        "validation_report.md",
        "validation_report.json",
        "e2e_validation_report.json",
    ):
        src = work_case / report_name
        if src.exists():
            shutil.copy2(src, generated_dir / report_name)
    return copied


def generate_trial(
    trial: str | Path,
    *,
    force_generate: bool = False,
    skip_generate: bool | None = None,
) -> dict[str, Any]:
    path = trial_dir(trial)
    manifest = load_manifest(path)
    case_dir = PROJECT_ROOT / manifest["case_dir"]
    if not case_dir.exists():
        case_dir = Path(manifest["case_dir"])
    if not case_dir.exists():
        raise FileNotFoundError(f"case_dir not found: {manifest.get('case_dir')}")

    # Safety: never write into original case_dir
    case_resolved = case_dir.resolve()
    work_case = (path / "workdir" / "case").resolve()
    if work_case == case_resolved:
        raise RuntimeError("refusing to use source case_dir as trial workdir")
    try:
        work_case.relative_to(case_resolved)
        # workdir accidentally nested inside source case
        raise RuntimeError(f"trial workdir must not be inside source case: {work_case}")
    except ValueError:
        pass
    try:
        path.resolve().relative_to(case_resolved)
        raise RuntimeError(f"trial path must not be inside source case: {path}")
    except ValueError:
        pass

    document_types = list(manifest.get("document_types") or ["MDSR", "MDDR"])
    synthetic = bool(manifest.get("synthetic"))

    # Hash source outputs BEFORE any work so we can prove no overwrite
    source_hashes_before: dict[str, str] = {}
    for name in OUTPUT_NAMES.values():
        src = case_resolved / name
        if src.exists():
            source_hashes_before[name] = sha256_file(src)

    started = time.perf_counter()
    _copy_case_isolated(case_dir, work_case)

    # Prefer existing outputs for synthetic / default to avoid mutating originals
    # (copy already isolated). Optionally regenerate inside work_case only.
    should_skip = skip_generate if skip_generate is not None else (synthetic or not force_generate)
    harness_report: dict[str, Any] = {}
    if should_skip and (work_case / "output_mdsr.docx").exists():
        harness_report = {
            "ok": True,
            "skipped": True,
            "reason": "using isolated copy of existing outputs (no overwrite of source case)",
            "force_generate": False,
        }
    else:
        from document_ai.harness.document_harness import DocumentHarness

        harness = DocumentHarness(force_form_fill=False)
        harness_report = harness.generate(work_case, force_form_fill=False)
        harness_report["skipped"] = False

    # Quality / validation written only under work_case, then copied to generated/
    quality_report = run_document_quality(
        work_case,
        report_path=work_case / "quality_report.md",
    )

    gold_mdsr = PROJECT_ROOT / "data" / "gold" / "mdsr" / f"{case_dir.name}.docx"
    gold_mddr = PROJECT_ROOT / "data" / "gold" / "mddr" / f"{case_dir.name}.docx"
    validation_report: dict[str, Any]
    if gold_mdsr.exists() and gold_mddr.exists():
        validation_report = run_document_validation(
            work_case,
            gold_mdsr=gold_mdsr,
            gold_mddr=gold_mddr,
            report_md_path=work_case / "validation_report.md",
            report_json_path=work_case / "validation_report.json",
        )
    else:
        validation_report = {"status": "SKIPPED", "error": "gold not found for trial metrics"}

    generated_dir = path / "generated"
    copied = _copy_outputs_to_generated(work_case, generated_dir, document_types)

    elapsed_s = round(time.perf_counter() - started, 3)
    git_info = collect_git_info()
    env = collect_environment()

    # Prove source case outputs untouched by comparing hash if present
    source_hashes = {}
    for name, expected in source_hashes_before.items():
        actual = sha256_file(case_resolved / name)
        source_hashes[name] = actual
        if actual != expected:
            raise RuntimeError(f"source case output was modified unexpectedly: {name}")

    generation_manifest = {
        "trial_id": manifest.get("trial_id"),
        "generated_at": _utc_now(),
        "duration_seconds": elapsed_s,
        "duration_minutes": round(elapsed_s / 60.0, 4),
        "synthetic": synthetic,
        "source_case_dir": rel_to_project(case_resolved),
        "work_case_dir": rel_to_project(work_case),
        "source_case_output_hashes": source_hashes,
        "outputs": copied,
        "harness": harness_report,
        "quality": {
            "status": quality_report.get("status"),
            "scores": quality_report.get("scores"),
        },
        "validation": {
            "status": validation_report.get("status"),
            "scores": validation_report.get("scores"),
        },
        "git": git_info,
        "environment": env,
        "commands": [
            "trial-generate (isolated workdir copy; source case outputs not written)",
        ],
        "overwrite_source_case": False,
    }
    write_json(path / "generation_manifest.json", generation_manifest)
    write_json(path / "metrics" / "generation_metrics.json", {
        "quality": generation_manifest["quality"],
        "validation": generation_manifest["validation"],
        "duration_seconds": elapsed_s,
        "outputs": copied,
    })

    manifest["status"] = "generated"
    manifest["generated_at"] = generation_manifest["generated_at"]
    save_manifest(path, manifest)

    return {
        "ok": True,
        "trial_dir": rel_to_project(path),
        "generation_manifest": generation_manifest,
        "source_case_preserved": True,
    }
