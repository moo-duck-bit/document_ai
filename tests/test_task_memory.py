from pathlib import Path

import pytest

from document_ai.platform.memory.task_memory import WORKFLOW_FIELDS, TaskMemory, task_spec_to_dict
from document_ai.platform.models import TaskSpec
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.runtime import PlatformRuntime
from document_ai.platform.task_graph import build_task_graph
from document_ai.platform.workflow import Workflow


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


def test_task_memory_creates_workflow_and_index(tmp_path):
    tasks = TaskMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    workflow = tasks.create_workflow(
        workflow_id="wf-tg-test",
        correlation_id="corr-test",
        case_id="case",
        task_graph={
            "graph_id": "tg-test",
            "tasks": [task_spec_to_dict(TaskSpec(task_id="task-1", name="T1", harness="document", action="run"))],
            "metadata": {},
        },
        execution_order=["task-1"],
    )

    assert tasks.tasks_dir is not None
    assert tasks.tasks_dir.exists()
    assert tasks.index_path is not None
    assert tasks.index_path.exists()
    assert (tasks.tasks_dir / "wf-tg-test.json").exists()
    assert workflow["workflow_id"] == "wf-tg-test"


def test_task_memory_saves_snapshots_on_state_changes(tmp_path):
    tasks = TaskMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    tasks.create_workflow(
        workflow_id="wf-snap",
        correlation_id="corr-snap",
        case_id="case",
        task_graph={
            "graph_id": "tg-snap",
            "tasks": [task_spec_to_dict(TaskSpec(task_id="task-1", name="T1", harness="document", action="run"))],
            "metadata": {},
        },
        execution_order=["task-1"],
    )
    tasks.save_snapshot("wf-snap", trigger="workflow_started", workflow_status="RUNNING")
    tasks.update_task("wf-snap", "task-1", "RUNNING")
    tasks.update_task("wf-snap", "task-1", "COMPLETED", result={"ok": True})
    tasks.complete_workflow("wf-snap", status="COMPLETED")

    workflow = tasks.load_workflow("wf-snap")
    triggers = [snapshot["trigger"] for snapshot in workflow["snapshots"]]
    assert "workflow_started" in triggers
    assert "task_updated" in triggers
    assert "workflow_completed" in triggers
    assert workflow["tasks"]["task-1"]["state"] == "COMPLETED"


def test_workflow_schema_fields_present(tmp_path):
    tasks = TaskMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    workflow = tasks.create_workflow(
        workflow_id="wf-schema",
        correlation_id="corr-schema",
        case_id="case",
        task_graph={
            "graph_id": "tg-schema",
            "tasks": [task_spec_to_dict(TaskSpec(task_id="task-1", name="T1", harness="document", action="run"))],
            "metadata": {},
        },
        execution_order=["task-1"],
    )

    for field_name in WORKFLOW_FIELDS:
        assert field_name in workflow


def test_runtime_persists_workflow_and_returns_workflow_id(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="task-runtime",
    )

    assert runtime_result.workflow_id.startswith("wf-")
    assert (case_copy / "tasks" / "index.jsonl").exists()
    assert (case_copy / "tasks" / f"{runtime_result.workflow_id}.json").exists()


def test_runtime_task_state_transitions(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="task-states",
    )

    workflow = runtime.memory_manager.tasks.load_workflow(runtime_result.workflow_id)
    task = workflow["tasks"]["task-document-change-pipeline"]
    assert task["state"] == "COMPLETED"
    assert task["result"] is not None
    assert workflow["status"] == "COMPLETED"


def test_runtime_links_reasoning_to_task(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="task-reasoning",
    )

    workflow = runtime.memory_manager.tasks.load_workflow(runtime_result.workflow_id)
    trace = runtime.memory_manager.reasoning.load_trace(runtime_result.reasoning_id)
    task = workflow["tasks"]["task-document-change-pipeline"]

    assert workflow["reasoning_id"] == runtime_result.reasoning_id
    assert task["reasoning_id"] == runtime_result.reasoning_id
    assert all(step["task_id"] == "task-document-change-pipeline" for step in trace["steps"])


def test_runtime_records_task_events(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="task-events",
    )

    events = runtime.memory_manager.events.list_events(correlation_id="corr-task-events")
    event_types = [event["event_type"] for event in events]
    assert "TaskStarted" in event_types
    assert "TaskCompleted" in event_types


def test_runtime_failure_records_task_failed(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    class BrokenHarnessManager:
        def run(self, name, request, task):
            raise RuntimeError("task harness failed")

    runtime = PlatformRuntime(harness_manager=BrokenHarnessManager())

    with pytest.raises(RuntimeError, match="task harness failed"):
        runtime.run(
            case_dir=case_copy,
            change=change_path,
            dry_run=True,
            apply=False,
            request_id="task-failed",
        )

    workflows = runtime.memory_manager.tasks.list_workflows(correlation_id="corr-task-failed")
    assert workflows
    workflow = runtime.memory_manager.tasks.load_workflow(workflows[0]["workflow_id"])
    assert workflow["status"] == "FAILED"
    assert workflow["tasks"]["task-document-change-pipeline"]["state"] == "FAILED"

    failed_events = [
        event
        for event in runtime.memory_manager.events.list_events(correlation_id="corr-task-failed")
        if event["event_type"] == "TaskFailed"
    ]
    assert failed_events


def test_task_memory_replay_reconstructs_execution_order(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="task-replay",
    )

    replay = runtime.memory_manager.tasks.replay(runtime_result.workflow_id)
    planner = RuleBasedPlanner()
    request = planner.create_request(case_dir=case_copy, change=change_path, request_id="task-replay")
    task_graph = build_task_graph(request)
    workflow = Workflow.from_task_graph(task_graph)
    expected_order = [task.task_id for task in task_graph.ordered_tasks()]

    assert replay["execution_order"] == expected_order
    assert [step["task_id"] for step in replay["replay_steps"]] == expected_order
    assert replay["replay_steps"][0]["harness"] == "document"
    assert replay["replay_steps"][0]["action"] == "run_change_pipeline"
    assert replay["status"] == "COMPLETED"
    assert replay["correlation_id"] == "corr-task-replay"


def test_task_memory_list_and_clear(tmp_path):
    tasks = TaskMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    tasks.create_workflow(
        workflow_id="wf-list",
        correlation_id="corr-list",
        case_id="case",
        task_graph={
            "graph_id": "tg-list",
            "tasks": [task_spec_to_dict(TaskSpec(task_id="task-1", name="T1", harness="document", action="run"))],
            "metadata": {},
        },
        execution_order=["task-1"],
    )
    tasks.complete_workflow("wf-list", status="COMPLETED")

    listed = tasks.list_workflows(correlation_id="corr-list")
    assert len(listed) == 1
    assert listed[0]["workflow_id"] == "wf-list"

    tasks.clear_workflows()
    assert tasks.list_workflows() == []
