import json
from pathlib import Path

import pytest

from document_ai.platform.memory.event_memory import EVENT_FIELDS, EventMemory
from document_ai.platform.memory_manager import MemoryManager
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


def test_event_memory_creates_events_jsonl(tmp_path):
    events = EventMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    record = events.append_event(
        "WorkflowStarted",
        correlation_id="corr-test",
        case_id="case",
        workflow_id="wf-1",
    )

    assert events.events_path is not None
    assert events.events_path.exists()
    assert record["event_type"] == "WorkflowStarted"


def test_event_memory_append_only(tmp_path):
    events = EventMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    first = events.append_event(
        "WorkflowStarted",
        correlation_id="corr-test",
        case_id="case",
    )
    second = events.append_event(
        "WorkflowCompleted",
        correlation_id="corr-test",
        case_id="case",
    )

    loaded = events.load_events()
    assert len(loaded) == 2
    assert loaded[0]["event_id"] == first["event_id"]
    assert loaded[1]["event_id"] == second["event_id"]
    assert events.list_events(correlation_id="corr-test") == loaded


def test_event_schema_fields_present(tmp_path):
    events = EventMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    record = events.append_event(
        "HarnessStarted",
        correlation_id="corr-schema",
        case_id="case",
        workflow_id="wf-1",
        task_id="task-1",
        harness="document",
        payload={"action": "run_change_pipeline"},
        metadata={"dry_run": True},
    )

    for field_name in EVENT_FIELDS:
        assert field_name in record


def test_runtime_records_workflow_and_harness_events(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="event-runtime",
    )

    events = runtime.memory_manager.events.load_events()
    event_types = [event["event_type"] for event in events]

    assert runtime_result.correlation_id == "corr-event-runtime"
    assert runtime_result.event_refs
    assert "WorkflowStarted" in event_types
    assert "WorkflowCompleted" in event_types
    assert "HarnessStarted" in event_types
    assert "HarnessCompleted" in event_types
    assert "KnowledgeMemoryLoaded" in event_types
    assert "KnowledgeMemoryUpdated" in event_types
    assert (case_copy / "events.jsonl").exists()


def test_runtime_records_knowledge_memory_events(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="event-knowledge",
    )

    events = runtime.memory_manager.events.list_events(correlation_id="corr-event-knowledge")
    loaded = [event for event in events if event["event_type"] == "KnowledgeMemoryLoaded"][0]
    updated = [event for event in events if event["event_type"] == "KnowledgeMemoryUpdated"][0]

    assert loaded["payload"]["node_count"] > 0
    assert updated["payload"]["knowledge_graph"].endswith("knowledge_graph.json")


def test_runtime_records_runtime_failed(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    class BrokenHarnessManager:
        def run(self, name, request, task):
            raise RuntimeError("harness failed")

    runtime = PlatformRuntime(harness_manager=BrokenHarnessManager())
    memory = runtime.memory_manager
    memory.begin_runtime(case_copy, "corr-failed")

    with pytest.raises(RuntimeError, match="harness failed"):
        runtime.run(
            case_dir=case_copy,
            change=change_path,
            dry_run=True,
            apply=False,
            request_id="failed",
        )

    failed_events = [
        event
        for event in memory.events.load_events()
        if event["event_type"] == "RuntimeFailed"
    ]
    assert failed_events
    assert failed_events[-1]["payload"]["error_message"] == "harness failed"


def test_event_memory_clear_events_for_tests(tmp_path):
    events = EventMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()
    events.append_event("WorkflowStarted", correlation_id="corr-clear", case_id="case")
    assert len(events.load_events()) == 1

    events.clear_events()
    assert events.load_events() == []


def test_memory_manager_event_refs_track_runtime(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="event-refs",
    )

    events = runtime.memory_manager.events.load_events()
    event_ids = {event["event_id"] for event in events}
    assert set(runtime_result.event_refs) == event_ids
