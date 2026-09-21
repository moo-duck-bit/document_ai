"""Smoke tests for demo scripts."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = PROJECT_ROOT / "scripts" / "demo"


def test_demo_script_files_exist():
    assert (DEMO_DIR / "run_document_harness_demo.ps1").is_file()
    assert (DEMO_DIR / "README.md").is_file()
    assert (DEMO_DIR / "demo_hospital_intake.txt").is_file()


def test_demo_intake_text_file_exists():
    text = (DEMO_DIR / "demo_hospital_intake.txt").read_text(encoding="utf-8")
    assert "병원 예약" in text


def test_demo_script_references_pipeline_commands():
    script = (DEMO_DIR / "run_document_harness_demo.ps1").read_text(encoding="utf-8")
    assert "demo_hospital" in script
    assert "case-intake" in script
    assert "harness-generate" in script
    assert "document-quality" in script
    assert "text-file" in script
