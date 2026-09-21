from pathlib import Path

import pytest

from document_ai.platform.memory.reasoning_memory import (
    REASONING_FIELDS,
    STEP_FIELDS,
    ReasoningMemory,
    pipeline_step_to_reasoning_step,
)
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


def test_reasoning_memory_creates_directory_and_index(tmp_path):
    reasoning = ReasoningMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    trace = reasoning.create_trace(
        correlation_id="corr-test",
        case_id="case",
        workflow_id="wf-1",
        goal="change_request:test",
    )

    assert reasoning.reasoning_dir is not None
    assert reasoning.reasoning_dir.exists()
    assert reasoning.index_path is not None
    assert reasoning.index_path.exists()
    assert (reasoning.reasoning_dir / f"{trace['reasoning_id']}.json").exists()


def test_reasoning_trace_schema_fields_present(tmp_path):
    reasoning = ReasoningMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    trace = reasoning.create_trace(
        correlation_id="corr-schema",
        case_id="case",
        workflow_id="wf-1",
        goal="change_request:schema",
        event_refs=["evt-1"],
        knowledge_refs=["req:Req.6"],
        metadata={"dry_run": True},
    )
    step = pipeline_step_to_reasoning_step(
        {"agent_id": "requirement", "status": "ok", "data": {"req_id": "Req.6"}, "issues": []},
        1,
        event_refs=["evt-1"],
    )
    reasoning.append_step(trace["reasoning_id"], step)
    finalized = reasoning.finalize_trace(
        trace["reasoning_id"],
        status="completed",
        conclusion={"review_status": "ok"},
    )

    for field_name in REASONING_FIELDS:
        assert field_name in finalized
    for field_name in STEP_FIELDS:
        assert field_name in finalized["steps"][0]


def test_runtime_creates_reasoning_trace(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="reasoning-runtime",
    )

    reasoning_dir = case_copy / "reasoning"
    assert reasoning_dir.exists()
    assert (reasoning_dir / "index.jsonl").exists()
    assert runtime_result.reasoning_id
    assert runtime_result.reasoning_id.startswith("rsn-")


def test_runtime_pipeline_steps_become_reasoning_steps(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="reasoning-steps",
    )

    trace = runtime.memory_manager.reasoning.load_trace(runtime_result.reasoning_id)
    pipeline_agent_ids = [step["agent_id"] for step in runtime_result.result["pipeline"]]
    reasoning_agent_ids = [step["agent_id"] for step in trace["steps"]]

    assert len(trace["steps"]) == len(pipeline_agent_ids)
    assert reasoning_agent_ids == pipeline_agent_ids
    assert trace["steps"][0]["action"] == "run_requirement_agent"


def test_reasoning_trace_links_event_refs(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="reasoning-events",
    )

    trace = runtime.memory_manager.reasoning.load_trace(runtime_result.reasoning_id)
    assert set(runtime_result.event_refs).issubset(set(trace["event_refs"]))
    assert all(trace["event_refs"] for step in trace["steps"])


def test_reasoning_trace_includes_knowledge_context(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="reasoning-knowledge",
    )

    trace = runtime.memory_manager.reasoning.load_trace(runtime_result.reasoning_id)
    assert runtime_result.knowledge_context
    assert trace["conclusion"]["knowledge_context"] == runtime_result.knowledge_context
    assert any(ref.startswith("req:") for ref in trace["knowledge_refs"])


def test_runtime_failure_creates_failed_reasoning_trace(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    class BrokenHarnessManager:
        def run(self, name, request, task):
            raise RuntimeError("harness failed")

    runtime = PlatformRuntime(harness_manager=BrokenHarnessManager())

    with pytest.raises(RuntimeError, match="harness failed"):
        runtime.run(
            case_dir=case_copy,
            change=change_path,
            dry_run=True,
            apply=False,
            request_id="reasoning-failed",
        )

    traces = runtime.memory_manager.reasoning.list_traces(correlation_id="corr-reasoning-failed")
    assert traces
    failed_trace = runtime.memory_manager.reasoning.load_trace(traces[0]["reasoning_id"])
    assert failed_trace["status"] == "failed"
    assert failed_trace["conclusion"]["error_message"] == "harness failed"

    failed_events = [
        event
        for event in runtime.memory_manager.events.list_events(correlation_id="corr-reasoning-failed")
        if event["event_type"] == "RuntimeFailed"
    ]
    assert failed_events
    assert failed_events[0]["event_id"] in failed_trace["event_refs"]


def test_reasoning_memory_list_traces_and_clear(tmp_path):
    reasoning = ReasoningMemory(tmp_path / "case")
    (tmp_path / "case").mkdir()

    trace = reasoning.create_trace(
        correlation_id="corr-list",
        case_id="case",
        workflow_id="wf-1",
        goal="change_request:list",
    )
    reasoning.finalize_trace(trace["reasoning_id"], status="completed", conclusion={})

    listed = reasoning.list_traces(correlation_id="corr-list")
    assert len(listed) == 1
    assert listed[0]["reasoning_id"] == trace["reasoning_id"]

    reasoning.clear_traces()
    assert reasoning.list_traces() == []
    assert not (reasoning.reasoning_dir / f"{trace['reasoning_id']}.json").exists()
