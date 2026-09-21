from pathlib import Path

import pytest

from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.platform.document_harness import DocumentHarness
from document_ai.platform.harness_manager import HarnessManager
from document_ai.platform.operation.operation_harness import OperationHarness
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.runtime import PlatformRuntime

SAMPLES = Path("data/ops/samples")


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


def test_single_document_workflow_unchanged(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="mt-document",
    )
    legacy = run_change_pipeline(
        case_copy,
        change_path,
        dry_run=True,
        apply=False,
        change_path=change_path,
    )

    assert runtime_result.harness == "document"
    assert runtime_result.result == legacy
    assert runtime_result.task_results == {
        "task-document-change-pipeline": legacy,
    }


def test_single_operation_workflow_via_runtime(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change="GPU 서버 Docker 로그 장애 분석",
        dry_run=True,
        apply=False,
        request_id="mt-operation",
        metadata={"sample_dir": str(SAMPLES)},
    )

    assert runtime_result.harness == "operation"
    assert "task-operation-incident-analysis" in runtime_result.task_results
    assert runtime_result.task_results["task-operation-incident-analysis"]["harness"] == "operation"


def test_hybrid_workflow_executes_document_then_operation(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        goal="Req 변경 후 GPU 서버 장애 로그 분석",
        dry_run=True,
        apply=False,
        request_id="mt-hybrid",
        metadata={"sample_dir": str(SAMPLES)},
    )

    assert set(runtime_result.task_results.keys()) == {
        "task-document-change-pipeline",
        "task-operation-incident-analysis",
    }
    assert runtime_result.task_results["task-document-change-pipeline"]["mode"] == "dry-run"
    assert runtime_result.task_results["task-operation-incident-analysis"]["mode"] == "operation"
    assert runtime_result.result == runtime_result.task_results["task-document-change-pipeline"]


def test_hybrid_workflow_preserves_dependency_order(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    execution_order: list[str] = []

    class TrackingHarnessManager(HarnessManager):
        def run(self, name, request, task):
            execution_order.append(task.task_id)
            return super().run(name, request, task)

    runtime = PlatformRuntime(harness_manager=TrackingHarnessManager())
    runtime.run(
        case_dir=case_copy,
        change=change_path,
        goal="Req 변경 후 GPU 서버 장애 로그 분석",
        request_id="mt-order",
        metadata={"sample_dir": str(SAMPLES)},
    )

    assert execution_order == [
        "task-document-change-pipeline",
        "task-operation-incident-analysis",
    ]


def test_task_failure_skips_downstream_hybrid_tasks(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    class FailingDocumentHarnessManager:
        def run(self, name, request, task):
            if name == "document":
                raise RuntimeError("document task failed")
            return OperationHarness().run(request, task)

    runtime = PlatformRuntime(harness_manager=FailingDocumentHarnessManager())

    with pytest.raises(RuntimeError, match="document task failed"):
        runtime.run(
            case_dir=case_copy,
            change=change_path,
            goal="Req 변경 후 GPU 서버 장애 로그 분석",
            request_id="mt-failed",
            metadata={"sample_dir": str(SAMPLES)},
        )

    workflow = runtime.memory_manager.tasks.list_workflows(correlation_id="corr-mt-failed")[0]
    persisted = runtime.memory_manager.tasks.load_workflow(workflow["workflow_id"])
    assert persisted["tasks"]["task-document-change-pipeline"]["state"] == "FAILED"
    assert persisted["tasks"]["task-operation-incident-analysis"]["state"] == "SKIPPED"
    assert persisted["status"] == "FAILED"


def test_task_memory_and_event_memory_record_per_task(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        goal="Req 변경 후 GPU 서버 장애 로그 분석",
        request_id="mt-memory",
        metadata={"sample_dir": str(SAMPLES)},
    )

    workflow = runtime.memory_manager.tasks.load_workflow(runtime_result.workflow_id)
    assert workflow["tasks"]["task-document-change-pipeline"]["state"] == "COMPLETED"
    assert workflow["tasks"]["task-operation-incident-analysis"]["state"] == "COMPLETED"
    assert workflow["tasks"]["task-document-change-pipeline"]["result"] is not None
    assert workflow["tasks"]["task-operation-incident-analysis"]["result"] is not None

    events = runtime.memory_manager.events.list_events(correlation_id=runtime_result.correlation_id)
    started = [event for event in events if event["event_type"] == "TaskStarted"]
    completed = [event for event in events if event["event_type"] == "TaskCompleted"]
    assert {event["task_id"] for event in started} == {
        "task-document-change-pipeline",
        "task-operation-incident-analysis",
    }
    assert {event["task_id"] for event in completed} == {
        "task-document-change-pipeline",
        "task-operation-incident-analysis",
    }


def test_reasoning_and_evaluation_reflect_multitask_workflow(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        goal="Req 변경 후 GPU 서버 장애 로그 분석",
        request_id="mt-eval",
        metadata={"sample_dir": str(SAMPLES)},
    )

    trace = runtime.memory_manager.reasoning.load_trace(runtime_result.reasoning_id)
    document_steps = [step for step in trace["steps"] if step["task_id"] == "task-document-change-pipeline"]
    operation_steps = [step for step in trace["steps"] if step["task_id"] == "task-operation-incident-analysis"]
    assert document_steps
    assert operation_steps

    evaluation = runtime.memory_manager.evaluations.load_evaluation(runtime_result.evaluation_id)
    assert evaluation["metrics"]["task_success_rate"] == 1.0
    assert evaluation["metrics"]["workflow_completed"] is True
    assert evaluation["task_summary"]["completed_count"] == 2
