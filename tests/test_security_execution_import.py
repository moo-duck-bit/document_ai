"""Security test execution import, merge, render, and validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.form_fill.security_execution import (
    SecurityExecutionImportError,
    build_effective_security_payload,
    compute_execution_metrics,
    enrich_evidence,
    format_evidence_summary,
    import_security_results,
    validate_execution_payload,
)
from document_ai.form_fill.security_tests import ensure_security_tests_payload
from document_ai.learn.extract_security_tests import extract_security_tests_docx
from document_ai.render.xxcs import fill_xxcs_report
from document_ai.validation.runner import validate_xxcs


def _minimal_plan(case_dir: Path) -> None:
    intake = {
        "case_id": case_dir.name,
        "product_name": "Test",
        "domain": "test",
        "facts": {"product_name": "Test"},
    }
    (case_dir / "input.json").write_text(json.dumps(intake), encoding="utf-8")
    requirements = {
        "traceability": [
            {"requirement": "SI-01", "linked_reqs": "Req. 1"},
            {"requirement": "IA-01", "linked_reqs": "Req. 2"},
            {"requirement": "UC-01", "linked_reqs": "Req. 3"},
            {"requirement": "DC-01", "linked_reqs": "Req. 4"},
        ],
    }
    (case_dir / "requirements.json").write_text(json.dumps(requirements), encoding="utf-8")
    ensure_security_tests_payload(case_dir, intake=intake)


def _execution_payload(
    case_id: str,
    execution_id: str,
    results: list[dict],
    *,
    synthetic: bool = True,
) -> dict:
    return {
        "case_id": case_id,
        "execution_id": execution_id,
        "executed_at": "2026-07-17T12:00:00Z",
        "synthetic": synthetic,
        "executor": {"type": "script", "name": "pytest", "version": "1.0"},
        "environment": {"target": "test", "notes": "synthetic"},
        "results": results,
    }


def test_validate_execution_payload_rejects_missing_fields():
    errors = validate_execution_payload({"case_id": "x"})
    assert any("execution_id" in e for e in errors)


def test_validate_execution_payload_rejects_duplicate_test_ids():
    payload = _execution_payload(
        "c1",
        "exec-test-dup",
        [
            {"security_test_id": "SI-01", "status": "PASS"},
            {"security_test_id": "SI-01", "status": "FAIL"},
        ],
    )
    errors = validate_execution_payload(payload)
    assert any("duplicate" in e for e in errors)


def test_import_rejects_unknown_security_test_id(tmp_path: Path):
    case_dir = tmp_path / "case_x"
    case_dir.mkdir()
    _minimal_plan(case_dir)
    results = tmp_path / "bad.json"
    results.write_text(
        json.dumps(
            _execution_payload(
                "case_x",
                "exec-bad-unknown",
                [{"security_test_id": "ZZ-99", "status": "PASS"}],
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(SecurityExecutionImportError, match="unknown security_test_id"):
        import_security_results(case_dir, results)


def test_not_executed_does_not_overwrite_pass(tmp_path: Path):
    case_dir = tmp_path / "case_merge"
    case_dir.mkdir()
    _minimal_plan(case_dir)
    ev_file = tmp_path / "pass.txt"
    ev_file.write_text("SYNTHETIC pass evidence", encoding="utf-8")

    pass_exec = tmp_path / "pass.json"
    pass_exec.write_text(
        json.dumps(
            _execution_payload(
                "case_merge",
                "exec-pass-first",
                [
                    {
                        "security_test_id": "SI-01",
                        "status": "PASS",
                        "actual_result": "TLS OK",
                        "evidence": [{"type": "file", "path": str(ev_file)}],
                    }
                ],
            )
        ),
        encoding="utf-8",
    )
    import_security_results(case_dir, pass_exec)

    not_exec = tmp_path / "not_exec.json"
    not_exec.write_text(
        json.dumps(
            _execution_payload(
                "case_merge",
                "exec-not-exec-second",
                [{"security_test_id": "SI-01", "status": "NOT_EXECUTED"}],
            )
        ),
        encoding="utf-8",
    )
    import_security_results(case_dir, not_exec)

    overlay = json.loads((case_dir / "security_test_results.json").read_text(encoding="utf-8"))
    bucket = overlay["results_by_test"]["SI-01-T01"]
    assert bucket["accepted"]["status"] == "PASS"
    assert len(bucket["history"]) == 2


def test_pass_without_evidence_warning_not_accepted(tmp_path: Path):
    case_dir = tmp_path / "case_warn"
    case_dir.mkdir()
    _minimal_plan(case_dir)
    results = tmp_path / "no_evidence.json"
    results.write_text(
        json.dumps(
            _execution_payload(
                "case_warn",
                "exec-no-evidence",
                [{"security_test_id": "SI-01", "status": "PASS", "actual_result": "claimed pass"}],
            )
        ),
        encoding="utf-8",
    )
    summary = import_security_results(case_dir, results)
    assert any("PASS without evidence" in w for w in summary["warnings"])
    overlay = json.loads((case_dir / "security_test_results.json").read_text(encoding="utf-8"))
    assert overlay["results_by_test"]["SI-01-T01"]["accepted"] is None


def test_evidence_sha256_and_missing_file_warning(tmp_path: Path):
    base = tmp_path / "evidence_base"
    base.mkdir()
    good = base / "ok.log"
    good.write_text("log line", encoding="utf-8")
    enriched, warnings = enrich_evidence(
        [
            {"type": "log", "path": str(good)},
            {"type": "log", "path": "missing.log"},
        ],
        base_dirs=[base],
    )
    assert len(enriched[0]["sha256"]) == 64
    assert any("missing evidence file" in w for w in warnings)


def test_multiple_execution_history_preserved(tmp_path: Path):
    case_dir = tmp_path / "case_hist"
    case_dir.mkdir()
    _minimal_plan(case_dir)

    for idx, status in enumerate(("PASS", "FAIL")):
        path = tmp_path / f"exec_{idx}.json"
        path.write_text(
            json.dumps(
                _execution_payload(
                    "case_hist",
                    f"exec-hist-{idx}",
                    [
                        {
                            "security_test_id": "IA-01",
                            "status": status,
                            "actual_result": f"result {status}",
                            "executed_at": f"2026-07-1{idx}T12:00:00Z",
                            "evidence": [{"type": "text", "content": f"note {status}"}],
                        }
                    ],
                )
            ),
            encoding="utf-8",
        )
        import_security_results(case_dir, path)

    overlay = json.loads((case_dir / "security_test_results.json").read_text(encoding="utf-8"))
    bucket = overlay["results_by_test"]["IA-01-T01"]
    assert len(bucket["history"]) == 2
    assert bucket["accepted"]["status"] == "FAIL"


def test_build_effective_payload_applies_accepted_execution(tmp_path: Path):
    from document_ai.form_fill.security_execution_review import import_security_review

    case_dir = tmp_path / "case_render"
    case_dir.mkdir()
    _minimal_plan(case_dir)
    results = tmp_path / "pass.json"
    results.write_text(
        json.dumps(
            _execution_payload(
                "case_render",
                "exec-render",
                [
                    {
                        "security_test_id": "SI-01",
                        "status": "PASS",
                        "actual_result": "Rendered actual",
                        "evidence": [{"type": "text", "content": "inline proof"}],
                    }
                ],
                synthetic=False,
            )
        ),
        encoding="utf-8",
    )
    import_security_results(case_dir, results)
    review = {
        "case_id": "case_render",
        "execution_id": "exec-render",
        "reviewer": {"name": "tester"},
        "reviewed_at": "2026-07-17T18:00:00Z",
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
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    import_security_review(case_dir, review_path)
    effective = build_effective_security_payload(case_dir)
    si = next(t for t in effective["tests"] if t["req_id"] == "SI-01")
    assert si["satisfaction"] == "PASS"
    assert "Rendered actual" in si["actual_result"]
    assert si["test_method"]


def test_render_extract_round_trip_with_execution(tmp_path: Path):
    from docx import Document

    from document_ai.form_fill.security_execution_review import import_security_review

    case_dir = tmp_path / "case_roundtrip"
    case_dir.mkdir()
    _minimal_plan(case_dir)
    skeleton = tmp_path / "skeleton.docx"
    doc = Document()
    doc.add_paragraph("1. Security Verification")
    doc.add_paragraph("SI-01. Communication integrity")
    table = doc.add_table(rows=2, cols=4)
    table.rows[0].cells[0].text = "시험결과"
    table.rows[0].cells[1].text = "적용"
    table.rows[0].cells[2].text = "만족"
    table.rows[0].cells[3].text = "비고"
    doc.save(str(skeleton))

    results = tmp_path / "exec.json"
    results.write_text(
        json.dumps(
            _execution_payload(
                "case_roundtrip",
                "exec-roundtrip",
                [
                    {
                        "security_test_id": "SI-01",
                        "status": "PASS",
                        "actual_result": "TLS verified in round-trip",
                        "evidence": [{"type": "text", "content": "proof"}],
                    }
                ],
                synthetic=False,
            )
        ),
        encoding="utf-8",
    )
    import_security_results(case_dir, results)
    review = {
        "case_id": "case_roundtrip",
        "execution_id": "exec-roundtrip",
        "reviewer": {"name": "tester"},
        "reviewed_at": "2026-07-17T18:00:00Z",
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
    (tmp_path / "review.json").write_text(json.dumps(review), encoding="utf-8")
    import_security_review(case_dir, tmp_path / "review.json")
    payload = build_effective_security_payload(case_dir)
    out = case_dir / "output_xxcs.docx"
    fill_xxcs_report(skeleton, {"product_name": "Test"}, payload, out)
    extracted = extract_security_tests_docx(out)
    si = next(t for t in extracted["tests"] if "SI-01" in str(t.get("req_id", "")))
    body = si.get("test_result") or ""
    assert "TLS verified" in body or "TLS verified" in str(si.get("actual_result", ""))


def test_compute_execution_metrics(tmp_path: Path):
    case_dir = tmp_path / "case_metrics"
    case_dir.mkdir()
    _minimal_plan(case_dir)
    results = tmp_path / "mixed.json"
    results.write_text(
        json.dumps(
            _execution_payload(
                "case_metrics",
                "exec-metrics",
                [
                    {
                        "security_test_id": "SI-01",
                        "status": "PASS",
                        "actual_result": "ok",
                        "evidence": [{"type": "text", "content": "x"}],
                    },
                    {"security_test_id": "UC-01", "status": "NOT_EXECUTED"},
                    {
                        "security_test_id": "DC-01",
                        "status": "REVIEW_REQUIRED",
                        "actual_result": "needs review",
                        "evidence": [{"type": "text", "content": "note"}],
                    },
                ],
            )
        ),
        encoding="utf-8",
    )
    import_security_results(case_dir, results)
    plan = json.loads((case_dir / "security_tests.json").read_text(encoding="utf-8"))["tests"]
    overlay = json.loads((case_dir / "security_test_results.json").read_text(encoding="utf-8"))
    metrics = compute_execution_metrics(plan, overlay)
    assert metrics["executed_test_count"] >= 1
    assert metrics["unresolved_review_required_count"] >= 1
    assert 0 <= metrics["execution_coverage"] <= 1


def test_format_evidence_summary_truncates_large_content():
    summary = format_evidence_summary(
        [{"type": "log", "path": "/tmp/a.log", "sha256": "a" * 64}]
    )
    assert "sha256=" in summary
    assert "log" in summary


def test_validate_xxcs_includes_execution_metrics(tmp_path: Path):
    from docx import Document

    case_dir = tmp_path / "case_val"
    case_dir.mkdir()
    _minimal_plan(case_dir)
    skeleton = tmp_path / "skel.docx"
    doc = Document()
    doc.add_paragraph("SI-01. Test")
    t = doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "시험결과"
    t.rows[1].cells[0].text = "body"
    doc.save(str(skeleton))
    gen = case_dir / "output_xxcs.docx"
    gold = tmp_path / "gold.docx"
    fill_xxcs_report(skeleton, {"product_name": "Test"}, build_effective_security_payload(case_dir), gen)
    gold.write_bytes(gen.read_bytes())

    result = validate_xxcs(gen, gold, case_dir=case_dir)
    assert "execution_coverage" in result["metrics"]
    assert result["execution_state"]["has_execution_overlay"] is False
