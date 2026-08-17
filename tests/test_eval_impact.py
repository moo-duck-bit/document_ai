import json
from argparse import Namespace
from pathlib import Path

import pytest

from document_ai.cli import cmd_eval_impact
from document_ai.eval.metrics import compute_metrics, score_prediction
from document_ai.eval.report import write_evaluation_report
from document_ai.eval.runner import (
    PREDICTION_SCHEMA_KEYS,
    assert_no_duplicate_case_ids,
    finalize_prediction,
    index_by_case_id,
    load_jsonl,
    make_error_prediction,
    resolve_case_path,
    run_eval_case,
    run_evaluation,
)


def test_recall_empty_expected_no_division_by_zero():
    predicted = {
        "case_id": "empty_expected",
        "predicted_linked_security_ids": [],
        "predicted_linked_test_ids": [],
        "predicted_changed_req_ids": [],
        "predicted_design_ids": [],
        "predicted_linked_documents": [],
        "clarification_needed": False,
        "patch_success": True,
    }
    expected = {
        "case_id": "empty_expected",
        "expected_linked_security_ids": [],
        "expected_linked_test_ids": [],
        "expected_changed_req_ids": [],
        "expected_design_ids": [],
        "expected_linked_documents": [],
        "clarification_needed": False,
    }
    score = score_prediction(predicted, expected)
    assert score["linked_security_id_recall"] == 1.0
    assert score["linked_test_id_recall"] == 1.0
    assert score["linked_document_recall"] == 1.0


def test_clarification_needed_accuracy():
    predicted = {"case_id": "c1", "clarification_needed": True, "patch_success": False}
    expected = {"case_id": "c1", "clarification_needed": True}
    assert score_prediction(predicted, expected)["clarification_needed_accuracy"] == 1.0

    predicted["clarification_needed"] = False
    assert score_prediction(predicted, expected)["clarification_needed_accuracy"] == 0.0


def test_compute_metrics_summary_average():
    predictions = [
        {
            "case_id": "a",
            "predicted_changed_req_ids": ["Req. 6"],
            "predicted_linked_security_ids": ["IA-04"],
            "predicted_linked_test_ids": [],
            "predicted_design_ids": [],
            "predicted_linked_documents": ["spec_requirements"],
            "clarification_needed": False,
            "patch_success": True,
        }
    ]
    expected = {
        "a": {
            "expected_changed_req_ids": ["Req. 6"],
            "expected_linked_security_ids": ["IA-04", "IA-06"],
            "expected_linked_test_ids": [],
            "expected_design_ids": [],
            "expected_linked_documents": ["spec_requirements"],
            "clarification_needed": False,
        }
    }
    metrics = compute_metrics(predictions, expected)
    assert metrics["case_count"] == 1
    assert metrics["summary"]["changed_req_id_detection_accuracy"] == 1.0
    assert metrics["summary"]["linked_security_id_recall"] == 0.5


def test_missing_expected_excluded_from_summary():
    predictions = [
        {
            "case_id": "scored",
            "predicted_changed_req_ids": ["Req. 6"],
            "predicted_linked_security_ids": [],
            "predicted_linked_test_ids": [],
            "predicted_design_ids": [],
            "predicted_linked_documents": [],
            "clarification_needed": False,
            "patch_success": True,
        },
        {
            "case_id": "no_expected_row",
            "predicted_changed_req_ids": [],
            "predicted_linked_security_ids": [],
            "predicted_linked_test_ids": [],
            "predicted_design_ids": [],
            "predicted_linked_documents": [],
            "clarification_needed": False,
            "patch_success": True,
        },
    ]
    expected = {
        "scored": {
            "expected_changed_req_ids": ["Req. 6"],
            "expected_linked_security_ids": [],
            "expected_linked_test_ids": [],
            "expected_design_ids": [],
            "expected_linked_documents": [],
            "clarification_needed": False,
        }
    }
    metrics = compute_metrics(predictions, expected)

    assert metrics["case_count"] == 1
    assert metrics["skipped_count"] == 1
    assert metrics["skipped_cases"] == [
        {
            "case_id": "no_expected_row",
            "eval_skipped": True,
            "reason": "missing_expected",
        }
    ]
    assert metrics["summary"]["changed_req_id_detection_accuracy"] == 1.0


def test_duplicate_case_id_raises():
    rows = [{"case_id": "a"}, {"case_id": "a"}]
    with pytest.raises(ValueError, match="duplicate case_id"):
        assert_no_duplicate_case_ids(rows, source="test dataset")
    with pytest.raises(ValueError, match="duplicate case_id"):
        index_by_case_id(rows)


def test_resolve_case_path_from_project_root():
    resolved = resolve_case_path("data/cases/mindrium_xa")
    assert resolved.is_absolute()
    assert resolved.name == "mindrium_xa"
    assert (resolved / "requirements.json").exists()


def test_run_eval_case_works_from_any_cwd(tmp_path, monkeypatch):
    cases = load_jsonl(Path("data/eval/change_cases.jsonl"))
    case = next(c for c in cases if c["case_id"] == "fr02_stt_tc_link")
    monkeypatch.chdir(tmp_path)
    prediction = run_eval_case(case, tmp_path / "cwd_eval")
    assert prediction["predicted_changed_req_ids"] == ["FR-02"]


def test_run_evaluation_reports_skipped_cases(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    expected_path = tmp_path / "expected.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "only_case",
                "case_path": "data/cases/stt_srs",
                "change": {"requirement_changes": []},
                "input_type": "structured",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    expected_path.write_text("", encoding="utf-8")

    result = run_evaluation(cases_path, expected_path, tmp_path / "out")

    assert result["case_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_cases"][0]["case_id"] == "only_case"
    assert result["warning"]
    md = (tmp_path / "out" / "metrics.md").read_text(encoding="utf-8")
    assert "## Skipped Cases" in md
    assert "No scorable cases" in md


def test_error_case_excluded_from_summary():
    predictions = [
        {
            "case_id": "ok",
            "status": "ok",
            "predicted_changed_req_ids": ["Req. 6"],
            "predicted_linked_security_ids": [],
            "predicted_linked_test_ids": [],
            "predicted_design_ids": [],
            "predicted_linked_documents": [],
            "clarification_needed": False,
            "patch_success": True,
            "error_message": "",
        },
        make_error_prediction("failed", "case directory missing"),
    ]
    expected = {
        "ok": {
            "expected_changed_req_ids": ["Req. 6"],
            "expected_linked_security_ids": [],
            "expected_linked_test_ids": [],
            "expected_design_ids": [],
            "expected_linked_documents": [],
            "clarification_needed": False,
        },
        "failed": {
            "expected_changed_req_ids": [],
            "expected_linked_security_ids": [],
            "expected_linked_test_ids": [],
            "expected_design_ids": [],
            "expected_linked_documents": [],
            "clarification_needed": False,
        },
    }
    metrics = compute_metrics(predictions, expected)

    assert metrics["case_count"] == 1
    assert metrics["error_count"] == 1
    assert metrics["error_cases"][0]["case_id"] == "failed"
    assert metrics["summary"]["changed_req_id_detection_accuracy"] == 1.0


def test_orphan_expected_cases_reported(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    expected_path = tmp_path / "expected.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "present_case",
                "case_path": "data/cases/stt_srs",
                "change": {"requirement_changes": []},
                "input_type": "structured",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    expected_path.write_text(
        json.dumps({"case_id": "present_case", "expected_changed_req_ids": []})
        + "\n"
        + json.dumps({"case_id": "orphan_only", "expected_changed_req_ids": ["FR-01"]})
        + "\n",
        encoding="utf-8",
    )

    result = run_evaluation(cases_path, expected_path, tmp_path / "out")

    assert result["orphan_expected_cases"] == ["orphan_only"]
    assert result["orphan_expected_count"] == 1
    md = (tmp_path / "out" / "metrics.md").read_text(encoding="utf-8")
    assert "## Orphan Expected Cases" in md
    assert "`orphan_only`" in md


def test_empty_dataset_warning_in_compute_metrics():
    metrics = compute_metrics([], {})
    assert metrics["case_count"] == 0
    assert metrics["warning"]
    assert "No scorable cases" in metrics["warning"]


def test_prediction_schema_fields(tmp_path):
    cases = load_jsonl(Path("data/eval/change_cases.jsonl"))
    case = next(c for c in cases if c["case_id"] == "req6_login_policy_change")
    prediction = run_eval_case(case, tmp_path / "schema")
    for key in PREDICTION_SCHEMA_KEYS:
        assert key in prediction

    error_prediction = make_error_prediction("broken", "boom")
    for key in PREDICTION_SCHEMA_KEYS:
        assert key in error_prediction
    assert error_prediction["status"] == "error"
    assert error_prediction["error_message"] == "boom"


def test_run_evaluation_predictions_jsonl_schema(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    expected_path = tmp_path / "expected.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "bad_case",
                "case_path": "data/cases/does_not_exist",
                "change": {"requirement_changes": [{"req_id": "FR-01", "description": "x"}]},
                "input_type": "structured",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    expected_path.write_text(
        json.dumps({"case_id": "bad_case", "expected_changed_req_ids": ["FR-01"]}) + "\n",
        encoding="utf-8",
    )

    run_evaluation(cases_path, expected_path, tmp_path / "out")
    rows = [json.loads(line) for line in (tmp_path / "out" / "predictions.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    for key in PREDICTION_SCHEMA_KEYS:
        assert key in rows[0]
    assert rows[0]["status"] == "error"
    assert rows[0]["error_message"]


def test_req6_eval_case(tmp_path):
    cases = load_jsonl(Path("data/eval/change_cases.jsonl"))
    case = next(c for c in cases if c["case_id"] == "req6_login_policy_change")
    out = tmp_path / "results"
    prediction = run_eval_case(case, out)

    assert prediction["predicted_changed_req_ids"] == ["Req. 6"]
    assert "IA-04" in prediction["predicted_linked_security_ids"]
    assert prediction["clarification_needed"] is False
    assert (out / "reports" / "req6_login_policy_change_impact_report.json").exists()


def test_fr02_tc_recall_eval(tmp_path):
    cases = load_jsonl(Path("data/eval/change_cases.jsonl"))
    expected = {row["case_id"]: row for row in load_jsonl(Path("data/eval/expected_impacts.jsonl"))}
    case = next(c for c in cases if c["case_id"] == "fr02_stt_tc_link")
    prediction = run_eval_case(case, tmp_path / "fr02")

    score = score_prediction(prediction, expected["fr02_stt_tc_link"])
    assert prediction["predicted_changed_req_ids"] == ["FR-02"]
    assert prediction["predicted_linked_test_ids"] == ["TC-02"]
    assert score["linked_test_id_recall"] == 1.0


def test_nl_missing_description_clarification(tmp_path):
    cases = load_jsonl(Path("data/eval/change_cases.jsonl"))
    expected = {row["case_id"]: row for row in load_jsonl(Path("data/eval/expected_impacts.jsonl"))}
    case = next(c for c in cases if c["case_id"] == "req6_nl_missing_description")
    prediction = run_eval_case(case, tmp_path / "nl")

    score = score_prediction(prediction, expected["req6_nl_missing_description"])
    assert prediction["clarification_needed"] is True
    assert prediction["predicted_changed_req_ids"] == []
    assert score["clarification_needed_accuracy"] == 1.0


def test_run_evaluation_writes_outputs(tmp_path):
    cases_src = Path("data/eval/change_cases.jsonl")
    expected_src = Path("data/eval/expected_impacts.jsonl")
    out = tmp_path / "eval_out"
    result = run_evaluation(cases_src, expected_src, out)

    assert (out / "metrics.json").exists()
    assert (out / "metrics.md").exists()
    assert (out / "predictions.jsonl").exists()
    assert "summary" in result
    assert result["case_count"] == 4


def test_write_evaluation_report_sections(tmp_path):
    metrics = {
        "summary": {"linked_test_id_recall": 1.0},
        "case_count": 1,
        "cases": [{"case_id": "x", "linked_test_id_recall": 1.0, "details": {}}],
        "errors": [],
    }
    json_path, md_path = write_evaluation_report(metrics, [], [], tmp_path)
    md = md_path.read_text(encoding="utf-8")
    assert "# Evaluation Report" in md
    assert "## Summary Metrics" in md
    assert "## Case Details" in md
    assert "## Error Analysis" in md or "## Runtime Error Analysis" in md
    assert "## Interpretation" in md
    assert json_path.exists()


def test_cli_eval_impact_smoke(tmp_path, capsys):
    out = tmp_path / "cli_eval"
    code = cmd_eval_impact(
        Namespace(
            cases="data/eval/change_cases.jsonl",
            expected="data/eval/expected_impacts.jsonl",
            out=str(out),
        )
    )
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["case_count"] == 4
    assert (out / "metrics.json").exists()
