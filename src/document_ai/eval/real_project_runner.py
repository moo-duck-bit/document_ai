"""End-to-end validation for real EC-SW project cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.eval.project_manifest import (
    benchmark_expectations,
    load_project_manifest,
    resolve_gold_paths,
)
from document_ai.harness.document_harness import DocumentHarness
from document_ai.quality.runner import run_document_quality
from document_ai.validation.runner import run_document_validation


def _has_generated_outputs(case_dir: Path) -> bool:
    return (case_dir / "output_mdsr.docx").exists() and (case_dir / "output_mddr.docx").exists()


def run_project_e2e_validation(
    case_dir: Path,
    *,
    force_generate: bool = False,
    gold_mdsr: Path | None = None,
    gold_mddr: Path | None = None,
    skip_generate: bool = False,
) -> dict[str, Any]:
    """Run harness → quality → validation for a registered project case."""
    case_dir = case_dir.resolve()
    manifest = load_project_manifest(case_dir)
    case_id = manifest.get("case_id", case_dir.name)
    expectations = benchmark_expectations(manifest)

    input_path = case_dir / "input.json"
    if not input_path.exists():
        return {
            "case_id": case_id,
            "case_dir": str(case_dir),
            "status": "FAIL",
            "error": f"missing input.json: {input_path}",
        }

    harness_report: dict[str, Any] = {}
    if not skip_generate and (force_generate or not _has_generated_outputs(case_dir)):
        harness = DocumentHarness(force_form_fill=force_generate)
        harness_report = harness.generate(case_dir, force_form_fill=force_generate)
    elif _has_generated_outputs(case_dir):
        harness_report = {"ok": True, "skipped": True, "reason": "outputs already present"}

    quality_report = run_document_quality(
        case_dir,
        report_path=case_dir / "quality_report.md",
    )

    resolved_gold_mdsr, resolved_gold_mddr = resolve_gold_paths(
        case_dir,
        manifest,
        gold_mdsr=gold_mdsr,
        gold_mddr=gold_mddr,
    )

    validation_report: dict[str, Any] = {}
    if resolved_gold_mdsr and resolved_gold_mddr:
        validation_report = run_document_validation(
            case_dir,
            gold_mdsr=resolved_gold_mdsr,
            gold_mddr=resolved_gold_mddr,
            report_md_path=case_dir / "validation_report.md",
            report_json_path=case_dir / "validation_report.json",
        )
    else:
        validation_report = {
            "case": str(case_dir),
            "status": "SKIPPED",
            "error": "gold documents not found",
            "gold_paths": {
                "mdsr": str(resolved_gold_mdsr) if resolved_gold_mdsr else "",
                "mddr": str(resolved_gold_mddr) if resolved_gold_mddr else "",
            },
        }

    quality_overall = quality_report.get("scores", {}).get("overall", 0.0)
    validation_overall = validation_report.get("scores", {}).get("overall", 0.0)
    min_quality = float(expectations.get("min_quality_overall", 85))
    min_validation = float(expectations.get("min_validation_overall", 70))

    harness_ok = harness_report.get("ok", False) or harness_report.get("skipped")
    quality_pass = quality_overall >= min_quality
    validation_pass = (
        validation_report.get("status") == "SKIPPED"
        or validation_overall >= min_validation
    )
    if validation_report.get("status") not in ("SKIPPED",) and validation_report.get("scores"):
        validation_pass = validation_overall >= min_validation

    status = "PASS"
    if not harness_ok or not quality_pass:
        status = "FAIL"
    elif validation_report.get("status") not in ("SKIPPED", "PASS", "WARNING") and validation_report.get("scores"):
        if validation_overall < min_validation:
            status = "FAIL"
    elif validation_report.get("status") == "FAIL":
        status = "FAIL"
    elif validation_report.get("status") == "WARNING" or quality_report.get("status") == "WARNING":
        status = "WARNING"

    result: dict[str, Any] = {
        "case_id": case_id,
        "case_dir": str(case_dir),
        "project_type": manifest.get("project_type", "ec_sw"),
        "display_name": manifest.get("display_name", case_id),
        "status": status,
        "harness": {
            "ok": bool(harness_ok),
            "report": harness_report,
        },
        "quality": {
            "status": quality_report.get("status"),
            "scores": quality_report.get("scores", {}),
            "report_path": quality_report.get("report_path"),
        },
        "validation": {
            "status": validation_report.get("status"),
            "scores": validation_report.get("scores", {}),
            "report_paths": validation_report.get("report_paths", {}),
            "gold_paths": {
                "mdsr": str(resolved_gold_mdsr) if resolved_gold_mdsr else None,
                "mddr": str(resolved_gold_mddr) if resolved_gold_mddr else None,
            },
        },
        "expectations": expectations,
        "checks": {
            "harness_ok": bool(harness_ok),
            "quality_pass": quality_pass,
            "validation_pass": validation_pass,
        },
    }

    report_path = case_dir / "e2e_validation_report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["e2e_report_path"] = str(report_path)
    return result
