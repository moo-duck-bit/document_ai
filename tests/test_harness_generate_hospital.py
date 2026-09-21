"""Hospital reservation harness E2E and quality validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from document_ai.harness.document_harness import DocumentHarness
from document_ai.quality.runner import run_document_quality

FOREIGN_TERMS = re.compile(
    r"쇼핑몰|장바구니|PG\s*결제|전자상거래|패션·잡화|재고관리\s*시스템|입고·출고|품목\s*조회|ERP\s*정산",
    re.I,
)

CASE_DIR = Path("data/cases/hospital_reservation")


@pytest.fixture(scope="module")
def hospital_case(tmp_path_factory):
    """Generate hospital_reservation in isolated tmp dir for test repeatability."""
    case_dir = tmp_path_factory.mktemp("hospital_reservation")
    src = CASE_DIR / "input.json"
    (case_dir / "input.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    harness = DocumentHarness(force_form_fill=True)
    report = harness.generate(case_dir)
    assert report["steps"]["intake"]["case_id"] == "hospital_reservation"
    return case_dir


def test_hospital_generates_required_outputs(hospital_case: Path):
    for name in (
        "requirements.json",
        "mdsr_content.json",
        "design_items.json",
        "output_mdsr.docx",
        "output_mddr.docx",
    ):
        assert (hospital_case / name).exists(), f"missing {name}"


def test_hospital_no_foreign_domain_terms(hospital_case: Path):
    req_text = (hospital_case / "requirements.json").read_text(encoding="utf-8")
    mdsr_text = (hospital_case / "mdsr_content.json").read_text(encoding="utf-8")
    combined = req_text + mdsr_text
    assert not FOREIGN_TERMS.search(combined), f"foreign terms found: {FOREIGN_TERMS.findall(combined)[:5]}"


def test_hospital_quality_scores(hospital_case: Path):
    result = run_document_quality(hospital_case)
    assert result["scores"]["overall"] >= 85
    assert result["scores"]["terminology"] >= 80
    assert result["scores"]["traceability"] == 100


@pytest.mark.skipif(not (CASE_DIR / "output_mdsr.docx").exists(), reason="committed case not generated")
def test_committed_hospital_case_quality():
    """Validate checked-in hospital_reservation case when present."""
    result = run_document_quality(CASE_DIR)
    assert result["scores"]["overall"] >= 85
    assert result["scores"]["terminology"] >= 80
