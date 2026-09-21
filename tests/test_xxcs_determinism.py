"""Regression tests for XXCS fill determinism and lab_ec_sw isolation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from document_ai.form_fill.security_execution_review import build_report_security_payload
from document_ai.learn.extract_security_tests import extract_security_tests_docx
from document_ai.render.xxcs import fill_xxcs_report
from document_ai.validation.validation_report import score_document
from document_ai.validation.xxcs_compare import compare_xxcs

LAB = Path("data/cases/lab_ec_sw")
TEMPLATE = Path("data/templates/ec_sw/template_xxcs_skeleton.docx")


def _canonical_tests(tests: list[dict]) -> list[tuple]:
    rows = []
    for test in tests:
        rows.append(
            (
                test.get("req_id"),
                str(test.get("test_method") or "").strip(),
                str(test.get("expected_result") or "").strip(),
                tuple(test.get("linked_req_ids") or []),
                tuple(test.get("linked_design_ids") or []),
            )
        )
    return sorted(rows)


@pytest.mark.skipif(not LAB.exists(), reason="lab_ec_sw required")
def test_xxcs_generation_is_deterministic(tmp_path: Path):
    requirements = json.loads((LAB / "requirements.json").read_text(encoding="utf-8"))
    design = json.loads((LAB / "design_items.json").read_text(encoding="utf-8"))
    security = build_report_security_payload(LAB, mode="plan")

    fingerprints = []
    scores = []
    for i in range(5):
        out = tmp_path / f"xxcs_{i}.docx"
        fill_xxcs_report(
            TEMPLATE,
            {"product_name": "JM COLLECTION"},
            copy.deepcopy(security),
            out,
        )
        extracted = extract_security_tests_docx(out)
        fingerprints.append(_canonical_tests(extracted.get("tests") or []))
        cmp = compare_xxcs(
            out,
            out,
            requirements_payload=requirements,
            design_payload=design,
        )
        scores.append(
            (
                score_document(cmp),
                cmp["plan_test_completeness"],
                cmp["linked_design_coverage"],
                cmp["generated_test_count"],
            )
        )

    assert all(fp == fingerprints[0] for fp in fingerprints), fingerprints
    assert all(score == scores[0] for score in scores), scores
    assert scores[0][0] >= 85.0
    assert scores[0][1] >= 0.85


@pytest.mark.skipif(not LAB.exists(), reason="lab_ec_sw required")
def test_xxcs_validation_is_deterministic(tmp_path: Path):
    requirements = json.loads((LAB / "requirements.json").read_text(encoding="utf-8"))
    design = json.loads((LAB / "design_items.json").read_text(encoding="utf-8"))
    security = build_report_security_payload(LAB, mode="plan")
    out = tmp_path / "once.docx"
    fill_xxcs_report(TEMPLATE, {"product_name": "JM COLLECTION"}, security, out)

    metrics = []
    for _ in range(5):
        cmp = compare_xxcs(
            out,
            out,
            requirements_payload=requirements,
            design_payload=design,
        )
        metrics.append(
            (
                score_document(cmp),
                cmp["plan_test_completeness"],
                cmp["linked_design_coverage"],
                cmp["security_coverage"],
            )
        )
    assert all(row == metrics[0] for row in metrics), metrics


@pytest.mark.skipif(not LAB.exists(), reason="lab_ec_sw required")
def test_synthetic_execution_is_never_selected_as_real():
    selected = json.loads((LAB / "selected_security_results.json").read_text(encoding="utf-8"))
    by_test = selected.get("results_by_test") or {}
    for key, row in by_test.items():
        if row.get("synthetic"):
            assert row.get("review_status") != "reviewer_verified"
            assert row.get("selected_for_report") in (False, None) or selected.get(
                "allow_synthetic_demo"
            )
    plan = build_report_security_payload(LAB, mode="plan")
    assert plan.get("report_mode") == "plan"
    for test in plan.get("tests") or []:
        assert not test.get("execution_synthetic")


@pytest.mark.skipif(not LAB.exists(), reason="lab_ec_sw required")
def test_lab_case_source_files_are_not_mutated_by_xxcs_fill(tmp_path: Path):
    watched = [
        "output_xxcs.docx",
        "security_tests.json",
        "requirements.json",
        "design_items.json",
        "selected_security_results.json",
    ]
    before = {
        name: hashlib.sha256((LAB / name).read_bytes()).hexdigest()
        for name in watched
        if (LAB / name).exists()
    }
    security = build_report_security_payload(LAB, mode="plan")
    fill_xxcs_report(
        TEMPLATE,
        {"product_name": "JM COLLECTION"},
        security,
        tmp_path / "isolated.docx",
    )
    after = {
        name: hashlib.sha256((LAB / name).read_bytes()).hexdigest()
        for name in before
    }
    assert after == before


@pytest.mark.skipif(not LAB.exists(), reason="lab_ec_sw required")
def test_security_result_selection_is_deterministic():
    a = build_report_security_payload(LAB, mode="auto")
    b = build_report_security_payload(LAB, mode="auto")
    assert [t.get("req_id") for t in a.get("tests") or []] == [
        t.get("req_id") for t in b.get("tests") or []
    ]
    assert (a.get("execution_overlay") or {}).get("selected_count") == (
        b.get("execution_overlay") or {}
    ).get("selected_count")


@pytest.mark.skipif(not LAB.exists(), reason="lab_ec_sw required")
def test_force_generate_then_xxcs_targets_still_pass(tmp_path: Path):
    """Former full-suite flake: force_generate pollution must not break XXCS targets."""
    import shutil

    from document_ai.eval.real_project_runner import run_project_e2e_validation

    src_hashes = {
        name: hashlib.sha256((LAB / name).read_bytes()).hexdigest()
        for name in ("output_xxcs.docx", "security_tests.json")
        if (LAB / name).exists()
    }

    isolated = tmp_path / "lab_copy"
    shutil.copytree(
        LAB,
        isolated,
        ignore=shutil.ignore_patterns("executions", "execution_reviews", "__pycache__"),
    )
    run_project_e2e_validation(isolated, force_generate=True)

    requirements = json.loads((LAB / "requirements.json").read_text(encoding="utf-8"))
    design = json.loads((LAB / "design_items.json").read_text(encoding="utf-8"))
    security = build_report_security_payload(LAB, mode="plan")
    out = tmp_path / "after_force.docx"
    fill_xxcs_report(TEMPLATE, {"product_name": "JM COLLECTION"}, security, out)
    cmp = compare_xxcs(
        out,
        out,
        requirements_payload=requirements,
        design_payload=design,
    )
    assert score_document(cmp) >= 85.0
    assert cmp["plan_test_completeness"] >= 0.85
    assert cmp["linked_design_coverage"] >= 0.70

    after = {
        name: hashlib.sha256((LAB / name).read_bytes()).hexdigest()
        for name in src_hashes
    }
    assert after == src_hashes
