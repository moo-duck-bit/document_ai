"""Tests for real project E2E validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from document_ai.eval.harness_benchmark import load_harness_benchmark_config, run_harness_benchmark
from document_ai.eval.project_manifest import load_project_manifest, resolve_gold_paths
from document_ai.eval.real_project_runner import run_project_e2e_validation

LAB_MANIFEST = Path("data/cases/lab_ec_sw/project_manifest.json")
JM_DIR = Path("data/cases/jm_collection")


@pytest.mark.skipif(not LAB_MANIFEST.exists(), reason="lab_ec_sw case not registered")
def test_lab_ec_sw_manifest_loads():
    manifest = load_project_manifest(Path("data/cases/lab_ec_sw"))
    assert manifest["case_id"] == "lab_ec_sw"
    assert manifest["project_type"] == "real_ec_sw_lab"


@pytest.mark.skipif(not JM_DIR.exists(), reason="jm_collection reference missing")
def test_resolve_gold_fallback_to_jm_collection():
    manifest = load_project_manifest(Path("data/cases/lab_ec_sw"))
    mdsr, mddr = resolve_gold_paths(Path("data/cases/lab_ec_sw"), manifest)
    assert mdsr is not None and mdsr.exists()
    assert mddr is not None and mddr.exists()


def test_project_e2e_skip_generate_with_existing_outputs(tmp_path: Path):
    if not (JM_DIR / "output_mdsr.docx").exists():
        pytest.skip("jm_collection outputs required")
    case_dir = tmp_path / "lab_test"
    case_dir.mkdir()
    shutil.copy(LAB_MANIFEST, case_dir / "project_manifest.json")
    shutil.copy(Path("data/cases/lab_ec_sw/input.json"), case_dir / "input.json")
    shutil.copy(JM_DIR / "output_mdsr.docx", case_dir / "output_mdsr.docx")
    shutil.copy(JM_DIR / "output_mddr.docx", case_dir / "output_mddr.docx")

    manifest = json.loads((case_dir / "project_manifest.json").read_text(encoding="utf-8"))
    manifest.setdefault("benchmark", {})["min_quality_overall"] = 0
    (case_dir / "project_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = run_project_e2e_validation(
        case_dir,
        skip_generate=True,
        gold_mdsr=JM_DIR / "output_mdsr.docx",
        gold_mddr=JM_DIR / "output_mddr.docx",
    )
    assert result["checks"]["validation_pass"] is True
    assert result["validation"]["scores"]["overall"] >= 85
    assert (case_dir / "quality_report.md").exists()
    assert (case_dir / "validation_report.md").exists()
    assert (case_dir / "e2e_validation_report.json").exists()


def test_harness_benchmark_config_has_lab_ec_sw():
    config = load_harness_benchmark_config()
    case_ids = [c["case_id"] for c in config["cases"]]
    assert "lab_ec_sw" in case_ids
    assert "inventory_mgmt" in case_ids


def test_harness_benchmark_single_case_skip_generate(tmp_path: Path):
    report = run_harness_benchmark(
        case_filter="inventory_mgmt",
        out_dir=tmp_path / "benchmark",
    )
    assert report["cases_run"] == 1
    assert report["case_results"][0]["case_id"] == "inventory_mgmt"
    assert Path(report["output_paths"]["json"]).exists()
