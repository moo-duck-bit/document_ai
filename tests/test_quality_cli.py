"""Integration test for document-quality CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_document_quality_cli_inventory_case():
    case = Path("data/cases/inventory_mgmt")
    if not (case / "output_mdsr.docx").exists():
        return
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_ai.cli",
            "document-quality",
            "--case",
            str(case),
            "--report",
            str(case / "quality_report_test.md"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode in (0, 1)
    payload = json.loads(proc.stdout)
    assert "scores" in payload
    assert "overall" in payload["scores"]
    report = case / "quality_report_test.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "Document Quality Report" in text
    report.unlink(missing_ok=True)
