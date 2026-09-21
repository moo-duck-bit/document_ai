import json
from pathlib import Path

from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.platform.document_harness import DocumentHarness
from document_ai.platform.harness_manager import HarnessManager
from document_ai.platform.memory_manager import MemoryManager
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.runtime import PlatformRuntime
from document_ai.platform.task_graph import build_task_graph
from document_ai.platform.workflow import Workflow


def test_planner_creates_request():
    planner = RuleBasedPlanner()
    request = planner.create_request(
        case_dir="data/cases/mindrium_xa",
        change="data/cases/mindrium_xa/changes/req6_update.json",
        request_id="req-1",
    )
    assert request.request_id == "req-1"
    assert request.mode == "change_request"
    assert request.case_dir == Path("data/cases/mindrium_xa")
    assert request.change == Path("data/cases/mindrium_xa/changes/req6_update.json")
    assert request.dry_run is True
    assert request.apply is False


def test_workflow_and_task_graph_creation():
    planner = RuleBasedPlanner()
    request = planner.create_request(
        case_dir="data/cases/mindrium_xa",
        change="data/cases/mindrium_xa/changes/req6_update.json",
        request_id="req-2",
    )
    task_graph = build_task_graph(request)
    workflow = Workflow.from_task_graph(task_graph)

    assert task_graph.graph_id == "tg-req-2"
    assert len(task_graph.tasks) == 1
    task = task_graph.tasks[0]
    assert task.harness == "document"
    assert task.action == "run_change_pipeline"
    assert workflow.workflow_id == "wf-tg-req-2"
    assert len(workflow.steps) == 1
    assert workflow.steps[0].task_id == task.task_id


def test_document_harness_executes_existing_pipeline():
    planner = RuleBasedPlanner()
    request = planner.create_request(
        case_dir="data/cases/mindrium_xa",
        change="data/cases/mindrium_xa/changes/req6_update.json",
    )
    task_graph = build_task_graph(request)
    harness = DocumentHarness()

    result = harness.run(request, task_graph.tasks[0])

    assert result["dry_run"] is True
    assert result["mode"] == "dry-run"
    assert "traceability" in result["agents"]
    assert "IA-04" in result["impact"]["linked_security_ids"]


def test_memory_manager_records_stub_updates(tmp_path):
    memory = MemoryManager()
    planner = RuleBasedPlanner()
    source_case = Path("data/cases/mindrium_xa")
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    (case_copy / "requirements.json").write_text(
        (source_case / "requirements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    change_path = source_case / "changes" / "req6_update.json"
    request = planner.create_request(
        case_dir=case_copy,
        change=change_path,
        request_id="req-3",
    )
    task_graph = build_task_graph(request)
    workflow = Workflow.from_task_graph(task_graph)
    workflow.mark_running()
    result = run_change_pipeline(
        case_copy,
        change_path,
        dry_run=True,
        apply=False,
        change_path=change_path,
    )
    workflow_result = workflow.complete(result)
    task = task_graph.tasks[0]

    memory.update_knowledge_memory(result, case_dir=case_copy)
    memory.update_event_memory(request, workflow_result)
    memory.update_reasoning_memory(result)
    memory.update_task_memory(task, workflow_result)
    memory.update_evaluation_memory(result)

    records = memory.snapshot()
    assert len(records) == 5
    assert [record["memory_type"] for record in records] == [
        "knowledge",
        "event",
        "reasoning",
        "task",
        "evaluation",
    ]
    assert records[0]["payload"]["node_count"] > 0


def test_runtime_returns_existing_pipeline_result(tmp_path):
    runtime = PlatformRuntime()
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

    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="req-4",
    )
    legacy = run_change_pipeline(
        case_copy,
        change_path,
        dry_run=True,
        apply=False,
        change_path=change_path,
    )

    assert runtime_result.harness == "document"
    assert runtime_result.workflow_id == "wf-tg-req-4"
    assert runtime_result.task_graph_id == "tg-req-4"
    assert len(runtime_result.memory_records) == 5
    assert runtime_result.result == legacy


def test_harness_manager_registers_document_harness():
    manager = HarnessManager()
    harness = manager.get("document")
    assert isinstance(harness, DocumentHarness)
