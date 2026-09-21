from pathlib import Path

import pytest

from document_ai.platform.improvement.execution_feedback import ExecutionFeedback
from document_ai.platform.improvement.improvement_engine import ImprovementEngine
from document_ai.platform.improvement.improvement_rules import detect_failure_patterns
from document_ai.platform.improvement.strategy_selector import select_execution_strategy
from document_ai.platform.planning.planner import AdaptivePlanner, MemoryQueryContext
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


def _failed_memory_snapshot() -> dict:
    return {
        "knowledge": {"available": True, "payload": {"case_id": "case", "node_count": 3, "edge_count": 2}},
        "events": {
            "available": True,
            "events": [
                {
                    "event_type": "RuntimeFailed",
                    "event_id": "evt-1",
                    "task_id": "task-document-change-pipeline",
                    "workflow_id": "wf-1",
                    "harness": "document",
                    "correlation_id": "corr-failed",
                },
                {
                    "event_type": "RuntimeFailed",
                    "event_id": "evt-2",
                    "task_id": "task-document-change-pipeline",
                    "workflow_id": "wf-2",
                    "harness": "document",
                    "correlation_id": "corr-failed-2",
                },
            ],
        },
        "reasoning": {
            "available": True,
            "traces": [{"reasoning_id": "rsn-1", "status": "failed"}],
        },
        "tasks": {
            "available": True,
            "workflows": [
                {"workflow_id": "wf-1", "status": "FAILED", "metadata": {"hybrid": True}},
                {"workflow_id": "wf-2", "status": "FAILED"},
            ],
        },
        "evaluations": {
            "available": True,
            "evaluations": [
                {"evaluation_id": "eval-1", "status": "failed"},
                {"evaluation_id": "eval-2", "status": "failed"},
            ],
        },
    }


def test_failure_pattern_detection():
    patterns = detect_failure_patterns(_failed_memory_snapshot())
    pattern_ids = {pattern.pattern_id for pattern in patterns}

    assert "repeated_evaluation_failure" in pattern_ids
    assert "repeated_runtime_failure" in pattern_ids
    assert "workflow_failure" in pattern_ids
    assert "reasoning_failure" in pattern_ids
    assert "repeated_document_harness_failure" in pattern_ids


def test_retry_recommendation():
    engine = ImprovementEngine()
    feedback = engine.analyze_snapshot(
        _failed_memory_snapshot(),
        case_dir="case",
        correlation_id="corr-failed",
    )

    assert any(item.action == "retry_task" for item in feedback.retry_candidates)
    assert any(item.action == "retry_with_dry_run" for item in feedback.retry_candidates)


def test_workflow_recommendation():
    engine = ImprovementEngine()
    feedback = engine.analyze_snapshot(
        _failed_memory_snapshot(),
        case_dir="case",
    )

    assert any(item.action == "split_hybrid_workflow" for item in feedback.workflow_recommendations)
    assert any(item.action == "reduce_workflow_scope" for item in feedback.workflow_recommendations)


def test_planner_recommendation():
    engine = ImprovementEngine()
    feedback = engine.analyze_snapshot(
        _failed_memory_snapshot(),
        case_dir="case",
    )

    actions = {item.action for item in feedback.planner_recommendations}
    assert "include_failure_context" in actions
    assert "apply_improvement_feedback" in actions
    assert "plan_retry_first" in actions


def test_strategy_recommendation():
    engine = ImprovementEngine()
    feedback = engine.analyze_snapshot(
        _failed_memory_snapshot(),
        case_dir="case",
    )

    assert any(item.action == "prefer_sequential" for item in feedback.strategy_recommendations)
    assert select_execution_strategy(feedback) == "sequential"


def test_improvement_engine_from_runtime_failure(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    class BrokenHarnessManager:
        def run(self, name, request, task):
            raise RuntimeError("self-improvement harness failed")

    runtime = PlatformRuntime(harness_manager=BrokenHarnessManager())
    with pytest.raises(RuntimeError, match="self-improvement harness failed"):
        runtime.run(
            case_dir=case_copy,
            change=change_path,
            request_id="si-failed",
        )

    engine = ImprovementEngine(runtime.memory_manager)
    feedback = engine.analyze(case_copy, correlation_id="corr-si-failed")

    assert isinstance(feedback, ExecutionFeedback)
    assert feedback.has_actionable_feedback
    assert feedback.memory_summary["failed_evaluation_count"] >= 1
    assert feedback.memory_summary["runtime_failed_count"] >= 1
    assert any(item.category == "planner" for item in feedback.planner_recommendations)


def test_adaptive_planner_reads_execution_feedback(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime.run(
        case_dir=case_copy,
        change=change_path,
        request_id="si-success",
    )

    planner = AdaptivePlanner(
        memory_context=MemoryQueryContext(memory_manager=runtime.memory_manager)
    )
    feedback = planner.query_execution_feedback(case_copy)
    feedback_dict = planner.memory_context.query_execution_feedback(case_copy)

    assert isinstance(feedback, ExecutionFeedback)
    assert feedback_dict["case_id"] == case_copy.name
    assert "memory_summary" in feedback_dict
    assert feedback.memory_summary["evaluation_count"] >= 1
