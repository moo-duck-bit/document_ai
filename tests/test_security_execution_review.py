"""Security execution review, selection, and gold-promotion tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.form_fill.security_execution import import_security_results
from document_ai.form_fill.security_execution_review import (
    SecurityReviewError,
    compute_final_report_readiness,
    compute_review_metrics,
    ensure_plan_gold_layout,
    import_security_review,
    prepare_security_review_package,
    promote_execution_gold,
    select_results_for_report,
    validate_review_payload,
)
from document_ai.form_fill.security_tests import ensure_security_tests_payload
from document_ai.validation.validation_report import score_plan_xxcs


def _minimal_case(case_dir: Path) -> None:
    intake = {
        "case_id": case_dir.name,
        "product_name": "Test",
        "domain": "test",
        "facts": {"product_name": "Test"},
    }
    (case_dir / "input.json").write_text(json.dumps(intake), encoding="utf-8")
    (case_dir / "requirements.json").write_text(
        json.dumps(
            {
                "traceability": [
                    {"requirement": "SI-01", "linked_reqs": "Req. 1"},
                    {"requirement": "IA-01", "linked_reqs": "Req. 2"},
                    {"requirement": "UC-01", "linked_reqs": "Req. 3"},
                    {"requirement": "DC-01", "linked_reqs": "Req. 4"},
                ]
            }
        ),
        encoding="utf-8",
    )
    ensure_security_tests_payload(case_dir, intake=intake)


def _exec_payload(case_id: str, execution_id: str, results: list[dict], *, synthetic: bool = False) -> dict:
    return {
        "case_id": case_id,
        "execution_id": execution_id,
        "executed_at": "2026-07-17T12:00:00Z",
        "synthetic": synthetic,
        "executor": {"type": "human", "name": "tester", "version": "1"},
        "environment": {"target": "lab"},
        "results": results,
    }


def _import_exec(case_dir: Path, tmp_path: Path, execution_id: str, results: list[dict], *, synthetic: bool = False):
    path = tmp_path / f"{execution_id}.json"
    path.write_text(
        json.dumps(_exec_payload(case_dir.name, execution_id, results, synthetic=synthetic)),
        encoding="utf-8",
    )
    return import_security_results(case_dir, path)


def test_validate_review_payload_requires_reviewer():
    errors = validate_review_payload(
        {
            "case_id": "c",
            "execution_id": "exec-1",
            "reviewed_at": "2026-07-17T12:00:00Z",
            "overall_status": "review_pending",
            "test_reviews": [{"security_test_id": "SI-01", "status": "review_pending"}],
            "reviewer": {"name": ""},
        }
    )
    assert any("reviewer" in e for e in errors)


def test_unknown_execution_id_rejected(tmp_path: Path):
    case_dir = tmp_path / "case_unknown"
    case_dir.mkdir()
    _minimal_case(case_dir)
    with pytest.raises(SecurityReviewError, match="unknown execution_id"):
        prepare_security_review_package(case_dir, "exec-missing-xxx")


def test_synthetic_gold_promotion_blocked(tmp_path: Path):
    case_dir = tmp_path / "case_syn_gold"
    case_dir.mkdir()
    _minimal_case(case_dir)
    ev = tmp_path / "e.txt"
    ev.write_text("proof", encoding="utf-8")
    _import_exec(
        case_dir,
        tmp_path,
        "exec-syn-gold",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "ok",
                "evidence": [{"type": "file", "path": str(ev)}],
            }
        ],
        synthetic=True,
    )
    prep = prepare_security_review_package(case_dir, "exec-syn-gold", out_dir=tmp_path / "pkg")
    review = json.loads(Path(prep["template_path"]).read_text(encoding="utf-8"))
    review["reviewer"] = {"name": "Alice", "role": "QA"}
    review["overall_status"] = "test_fixture_verified"
    review["synthetic_acknowledged"] = True
    for row in review["test_reviews"]:
        row["status"] = "test_fixture_verified"
        row["selected_for_report"] = False
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    import_security_review(case_dir, review_path)
    with pytest.raises(SecurityReviewError, match="synthetic"):
        promote_execution_gold(case_dir, execution_id="exec-syn-gold")


def test_synthetic_cannot_be_reviewer_verified(tmp_path: Path):
    case_dir = tmp_path / "case_syn_rv"
    case_dir.mkdir()
    _minimal_case(case_dir)
    ev = tmp_path / "e.txt"
    ev.write_text("proof", encoding="utf-8")
    _import_exec(
        case_dir,
        tmp_path,
        "exec-syn-rv",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "ok",
                "evidence": [{"type": "text", "content": "x"}],
            }
        ],
        synthetic=True,
    )
    review = {
        "case_id": case_dir.name,
        "execution_id": "exec-syn-rv",
        "reviewer": {"name": "Bob"},
        "reviewed_at": "2026-07-17T13:00:00Z",
        "overall_status": "reviewer_verified",
        "synthetic_acknowledged": True,
        "test_reviews": [
            {
                "security_test_id": "SI-01",
                "status": "reviewer_verified",
                "selected_for_report": True,
            }
        ],
    }
    path = tmp_path / "bad_review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(SecurityReviewError, match="synthetic"):
        import_security_review(case_dir, path)


def test_reviewer_verified_selected_rejected_not_selected(tmp_path: Path):
    case_dir = tmp_path / "case_select"
    case_dir.mkdir()
    _minimal_case(case_dir)
    _import_exec(
        case_dir,
        tmp_path,
        "exec-real-1",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "pass ok",
                "evidence": [{"type": "text", "content": "evidence"}],
            },
            {
                "security_test_id": "IA-01",
                "status": "FAIL",
                "actual_result": "fail ok",
                "evidence": [{"type": "text", "content": "evidence"}],
            },
        ],
        synthetic=False,
    )
    review = {
        "case_id": case_dir.name,
        "execution_id": "exec-real-1",
        "reviewer": {"name": "Carol", "role": "reviewer"},
        "reviewed_at": "2026-07-17T14:00:00Z",
        "overall_status": "reviewer_verified",
        "synthetic_acknowledged": False,
        "test_reviews": [
            {
                "security_test_id": "SI-01",
                "status": "reviewer_verified",
                "selected_for_report": True,
                "result_status_confirmed": True,
                "evidence_confirmed": True,
            },
            {
                "security_test_id": "IA-01",
                "status": "rejected",
                "selected_for_report": False,
                "note": "insufficient evidence chain",
            },
        ],
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    summary = import_security_review(case_dir, path)
    selected = json.loads((case_dir / "selected_security_results.json").read_text(encoding="utf-8"))
    assert "SI-01-T01" in selected["results_by_test"]
    assert "IA-01-T01" not in selected["results_by_test"]
    assert summary["real_selected_count"] == 1


def test_fail_then_pass_history_preserved_latest_selected(tmp_path: Path):
    case_dir = tmp_path / "case_retest"
    case_dir.mkdir()
    _minimal_case(case_dir)
    _import_exec(
        case_dir,
        tmp_path,
        "exec-fail",
        [
            {
                "security_test_id": "SI-01",
                "status": "FAIL",
                "actual_result": "first fail",
                "executed_at": "2026-07-10T12:00:00Z",
                "evidence": [{"type": "text", "content": "f"}],
            }
        ],
    )
    _import_exec(
        case_dir,
        tmp_path,
        "exec-pass",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "retest pass",
                "executed_at": "2026-07-12T12:00:00Z",
                "evidence": [{"type": "text", "content": "p"}],
            }
        ],
    )
    for exec_id, status, selected in (
        ("exec-fail", "rejected", False),
        ("exec-pass", "reviewer_verified", True),
    ):
        review = {
            "case_id": case_dir.name,
            "execution_id": exec_id,
            "reviewer": {"name": "Dan"},
            "reviewed_at": "2026-07-17T15:00:00Z" if exec_id == "exec-pass" else "2026-07-11T15:00:00Z",
            "overall_status": status if status != "rejected" else "rejected",
            "synthetic_acknowledged": False,
            "test_reviews": [
                {
                    "security_test_id": "SI-01",
                    "status": status,
                    "selected_for_report": selected,
                    "result_status_confirmed": True,
                    "evidence_confirmed": True,
                }
            ],
        }
        path = tmp_path / f"review_{exec_id}.json"
        path.write_text(json.dumps(review), encoding="utf-8")
        import_security_review(case_dir, path)

    overlay = json.loads((case_dir / "security_test_results.json").read_text(encoding="utf-8"))
    hist = overlay["results_by_test"]["SI-01-T01"]["history"]
    assert len(hist) == 2
    selected = json.loads((case_dir / "selected_security_results.json").read_text(encoding="utf-8"))
    assert selected["results_by_test"]["SI-01-T01"]["status"] == "PASS"


def test_pass_then_fail_regression_selects_latest_verified(tmp_path: Path):
    case_dir = tmp_path / "case_regress"
    case_dir.mkdir()
    _minimal_case(case_dir)
    _import_exec(
        case_dir,
        tmp_path,
        "exec-pass-old",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "old pass",
                "executed_at": "2026-07-01T12:00:00Z",
                "evidence": [{"type": "text", "content": "p"}],
            }
        ],
    )
    _import_exec(
        case_dir,
        tmp_path,
        "exec-fail-new",
        [
            {
                "security_test_id": "SI-01",
                "status": "FAIL",
                "actual_result": "regression fail",
                "executed_at": "2026-07-15T12:00:00Z",
                "evidence": [{"type": "text", "content": "f"}],
            }
        ],
    )
    for exec_id, reviewed_at in (
        ("exec-pass-old", "2026-07-02T12:00:00Z"),
        ("exec-fail-new", "2026-07-16T12:00:00Z"),
    ):
        review = {
            "case_id": case_dir.name,
            "execution_id": exec_id,
            "reviewer": {"name": "Eve"},
            "reviewed_at": reviewed_at,
            "overall_status": "reviewer_verified",
            "synthetic_acknowledged": False,
            "test_reviews": [
                {
                    "security_test_id": "SI-01",
                    "status": "reviewer_verified",
                    "selected_for_report": True,
                    "result_status_confirmed": True,
                    "evidence_confirmed": True,
                }
            ],
        }
        path = tmp_path / f"{exec_id}.review.json"
        path.write_text(json.dumps(review), encoding="utf-8")
        import_security_review(case_dir, path)

    selected = json.loads((case_dir / "selected_security_results.json").read_text(encoding="utf-8"))
    assert selected["results_by_test"]["SI-01-T01"]["status"] == "FAIL"
    assert selected["results_by_test"]["SI-01-T01"]["execution_id"] == "exec-fail-new"


def test_evidence_hash_mismatch_blocks_verified_claim(tmp_path: Path):
    case_dir = tmp_path / "case_hash"
    case_dir.mkdir()
    _minimal_case(case_dir)
    ev = tmp_path / "ok.txt"
    ev.write_text("original", encoding="utf-8")
    _import_exec(
        case_dir,
        tmp_path,
        "exec-hash",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "ok",
                "evidence": [{"type": "file", "path": str(ev)}],
            }
        ],
    )
    # Tamper evidence after import
    ev.write_text("tampered", encoding="utf-8")
    review = {
        "case_id": case_dir.name,
        "execution_id": "exec-hash",
        "reviewer": {"name": "Frank"},
        "reviewed_at": "2026-07-17T16:00:00Z",
        "overall_status": "reviewer_verified",
        "synthetic_acknowledged": False,
        "test_reviews": [
            {
                "security_test_id": "SI-01",
                "status": "reviewer_verified",
                "selected_for_report": True,
                "evidence_hash_verified": True,
            }
        ],
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(SecurityReviewError, match="hash"):
        import_security_review(case_dir, path)


def test_plan_and_execution_gold_dirs_separated():
    layout = ensure_plan_gold_layout("lab_ec_sw")
    assert Path(layout["plan_dir"]).exists()
    assert Path(layout["execution_dir"]).exists()
    assert "plan" in layout["plan_dir"]
    assert "execution" in layout["execution_dir"]


def test_score_plan_xxcs_ignores_text_similarity_when_execution_present():
    metrics = {
        "security_coverage": 1.0,
        "linked_requirement_coverage": 1.0,
        "linked_design_coverage": 0.9,
        "test_item_completeness": 0.6,
        "plan_test_completeness": 1.0,
        "test_text_similarity": 0.2,
        "security_id_count_match": 1.0,
        "executed_test_count": 2,
    }
    score = score_plan_xxcs(metrics)
    assert score >= 90.0


def test_final_report_readiness_and_synthetic_metrics_excluded(tmp_path: Path):
    case_dir = tmp_path / "case_ready"
    case_dir.mkdir()
    _minimal_case(case_dir)
    _import_exec(
        case_dir,
        tmp_path,
        "exec-syn-metrics",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "syn",
                "evidence": [{"type": "text", "content": "x"}],
            }
        ],
        synthetic=True,
    )
    prep = prepare_security_review_package(case_dir, "exec-syn-metrics", out_dir=tmp_path / "pkg2")
    review = json.loads(Path(prep["template_path"]).read_text(encoding="utf-8"))
    review["reviewer"] = {"name": "Gina"}
    review["overall_status"] = "test_fixture_verified"
    review["synthetic_acknowledged"] = True
    for row in review["test_reviews"]:
        row["status"] = "test_fixture_verified"
        row["selected_for_report"] = False
    path = tmp_path / "fixture_review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    import_security_review(case_dir, path)

    overlay = json.loads((case_dir / "security_test_results.json").read_text(encoding="utf-8"))
    selected = json.loads((case_dir / "selected_security_results.json").read_text(encoding="utf-8"))
    plan = json.loads((case_dir / "security_tests.json").read_text(encoding="utf-8"))["tests"]
    metrics = compute_review_metrics(plan, overlay, selected)
    assert metrics["reviewer_verified_execution_coverage"] == 0.0
    assert metrics["synthetic_result_count"] >= 1
    readiness = compute_final_report_readiness(overlay, selected)
    assert readiness["mode"] == "plan_only"


def test_partial_test_selection(tmp_path: Path):
    case_dir = tmp_path / "case_partial"
    case_dir.mkdir()
    _minimal_case(case_dir)
    _import_exec(
        case_dir,
        tmp_path,
        "exec-partial",
        [
            {
                "security_test_id": "SI-01",
                "status": "PASS",
                "actual_result": "a",
                "evidence": [{"type": "text", "content": "a"}],
            },
            {
                "security_test_id": "UC-01",
                "status": "PASS",
                "actual_result": "b",
                "evidence": [{"type": "text", "content": "b"}],
            },
        ],
    )
    review = {
        "case_id": case_dir.name,
        "execution_id": "exec-partial",
        "reviewer": {"name": "Hank"},
        "reviewed_at": "2026-07-17T17:00:00Z",
        "overall_status": "reviewer_verified",
        "verification_scope": "partial_tests",
        "synthetic_acknowledged": False,
        "test_reviews": [
            {
                "security_test_id": "SI-01",
                "status": "reviewer_verified",
                "selected_for_report": True,
                "result_status_confirmed": True,
                "evidence_confirmed": True,
            },
            {
                "security_test_id": "UC-01",
                "status": "review_pending",
                "selected_for_report": False,
            },
        ],
    }
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    import_security_review(case_dir, path)
    selected = json.loads((case_dir / "selected_security_results.json").read_text(encoding="utf-8"))
    assert set(selected["results_by_test"]) == {"SI-01-T01"}
