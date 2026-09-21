from pathlib import Path

import pytest

from document_ai.platform.memory.evaluation_memory import EVALUATION_FIELDS, EvaluationMemory
from document_ai.platform.runtime import PlatformRuntime


def _copy_mindrium_case(tmp_path: Path) -> Path:
    source_case = Path("data/cases/mindrium_xa")
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    (case_copy / "requirements.json").write_text(
        (source_case / "requirements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    changes_dir = case_copy / "changes"
    changes_dir.mkdir()
    change_path = changes_dir / "req6_update.json"
    change_path.write_text(
        (source_case / "changes" / "req6_update.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return case_copy


def test_evaluation_memory_creates_directory_and_index(tmp_path):
    evaluations = EvaluationMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    evaluation = evaluations.create_evaluation(
        correlation_id="corr-test",
        case_id="case",
        workflow_id="wf-1",
        reasoning_id="rsn-1",
    )
    finalized = evaluations.finalize_evaluation(
        evaluation["evaluation_id"],
        status="completed",
        metrics={"workflow_completed": True},
        review_summary={"status": "ok"},
        issue_count=0,
        task_summary={"success_rate": 1.0},
    )

    assert evaluations.evaluations_dir is not None
    assert evaluations.evaluations_dir.exists()
    assert evaluations.index_path is not None
    assert evaluations.index_path.exists()
    assert (evaluations.evaluations_dir / f"{evaluation['evaluation_id']}.json").exists()
    assert finalized["status"] == "completed"


def test_evaluation_schema_fields_present(tmp_path):
    evaluations = EvaluationMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    evaluation = evaluations.create_evaluation(
        correlation_id="corr-schema",
        case_id="case",
        workflow_id="wf-1",
        reasoning_id="rsn-1",
        event_refs=["evt-1"],
        knowledge_refs=["req:Req.6"],
        metadata={"dry_run": True},
    )
    finalized = evaluations.finalize_evaluation(
        evaluation["evaluation_id"],
        status="completed",
        metrics={"issue_count": 0},
        review_summary={"status": "ok", "issues": []},
        issue_count=0,
        task_summary={"tasks": {}, "success_rate": 1.0},
    )

    for field_name in EVALUATION_FIELDS:
        assert field_name in finalized


def test_runtime_creates_evaluation_on_success(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="eval-success",
    )

    assert runtime_result.evaluation_id.startswith("eval-")
    assert (case_copy / "evaluations" / "index.jsonl").exists()
    assert (case_copy / "evaluations" / f"{runtime_result.evaluation_id}.json").exists()

    evaluation = runtime.memory_manager.evaluations.load_evaluation(runtime_result.evaluation_id)
    assert evaluation["status"] == "completed"


def test_runtime_creates_failed_evaluation(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    class BrokenHarnessManager:
        def run(self, name, request, task):
            raise RuntimeError("evaluation harness failed")

    runtime = PlatformRuntime(harness_manager=BrokenHarnessManager())

    with pytest.raises(RuntimeError, match="evaluation harness failed"):
        runtime.run(
            case_dir=case_copy,
            change=change_path,
            dry_run=True,
            apply=False,
            request_id="eval-failed",
        )

    evaluations = runtime.memory_manager.evaluations.list_evaluations(
        correlation_id="corr-eval-failed"
    )
    assert evaluations
    evaluation = runtime.memory_manager.evaluations.load_evaluation(evaluations[0]["evaluation_id"])
    assert evaluation["status"] == "failed"
    assert evaluation["metrics"]["has_runtime_error"] is True
    assert evaluation["review_summary"]["error_message"] == "evaluation harness failed"


def test_runtime_evaluation_metrics(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="eval-metrics",
    )

    evaluation = runtime.memory_manager.evaluations.load_evaluation(runtime_result.evaluation_id)
    metrics = evaluation["metrics"]

    assert metrics["workflow_completed"] is True
    assert metrics["task_success_rate"] == 1.0
    assert "issue_count" in metrics
    assert "has_review_issues" in metrics
    assert metrics["has_runtime_error"] is False
    assert metrics["event_count"] > 0
    assert metrics["reasoning_step_count"] == len(runtime_result.result["pipeline"])


def test_runtime_evaluation_reflects_review_issue_count(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="eval-review",
    )

    evaluation = runtime.memory_manager.evaluations.load_evaluation(runtime_result.evaluation_id)
    review_issues = runtime_result.result["review"]["issues"]
    assert evaluation["issue_count"] == len(review_issues)
    assert evaluation["metrics"]["issue_count"] == len(review_issues)
    assert evaluation["metrics"]["has_review_issues"] == (len(review_issues) > 0)


def test_runtime_evaluation_links_workflow_reasoning_and_events(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="eval-links",
    )

    evaluation = runtime.memory_manager.evaluations.load_evaluation(runtime_result.evaluation_id)
    assert evaluation["workflow_id"] == runtime_result.workflow_id
    assert evaluation["reasoning_id"] == runtime_result.reasoning_id
    assert evaluation["correlation_id"] == runtime_result.correlation_id
    assert set(runtime_result.event_refs).issubset(set(evaluation["event_refs"]))


def test_evaluation_memory_list_and_clear(tmp_path):
    evaluations = EvaluationMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    evaluation = evaluations.create_evaluation(
        correlation_id="corr-list",
        case_id="case",
        workflow_id="wf-1",
    )
    evaluations.finalize_evaluation(
        evaluation["evaluation_id"],
        status="completed",
        metrics={},
        review_summary={},
        issue_count=0,
        task_summary={},
    )

    listed = evaluations.list_evaluations(correlation_id="corr-list")
    assert len(listed) == 1
    assert listed[0]["evaluation_id"] == evaluation["evaluation_id"]

    evaluations.clear_evaluations()
    assert evaluations.list_evaluations() == []
