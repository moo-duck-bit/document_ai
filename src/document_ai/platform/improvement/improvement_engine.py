from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.platform.improvement.execution_feedback import ExecutionFeedback
from document_ai.platform.improvement.improvement_rules import (
    detect_failure_patterns,
    recommend_harness_changes,
    recommend_retries,
    recommend_strategy_changes,
    recommend_workflow_changes,
)
from document_ai.platform.improvement.planner_feedback import build_planner_recommendations
from document_ai.platform.memory_manager import MemoryManager


class ImprovementEngine:
    """Analyze Platform Memory and produce execution feedback for future planning."""

    def __init__(self, memory_manager: MemoryManager | None = None) -> None:
        self.memory_manager = memory_manager

    def analyze_snapshot(
        self,
        memory_snapshot: dict[str, Any],
        *,
        case_dir: str | Path,
        correlation_id: str | None = None,
    ) -> ExecutionFeedback:
        case_path = Path(case_dir)
        failure_patterns = detect_failure_patterns(memory_snapshot)
        retry_candidates = recommend_retries(memory_snapshot, failure_patterns=failure_patterns)
        workflow_recommendations = recommend_workflow_changes(
            memory_snapshot,
            failure_patterns=failure_patterns,
        )
        harness_recommendations = recommend_harness_changes(
            memory_snapshot,
            failure_patterns=failure_patterns,
        )
        strategy_recommendations = recommend_strategy_changes(
            memory_snapshot,
            failure_patterns=failure_patterns,
        )
        planner_recommendations = build_planner_recommendations(
            memory_snapshot,
            failure_patterns=failure_patterns,
            retry_candidates=retry_candidates,
        )

        return ExecutionFeedback(
            case_id=case_path.name,
            correlation_id=correlation_id,
            failure_patterns=failure_patterns,
            retry_candidates=retry_candidates,
            planner_recommendations=planner_recommendations,
            harness_recommendations=harness_recommendations,
            workflow_recommendations=workflow_recommendations,
            strategy_recommendations=strategy_recommendations,
            knowledge_context=self._extract_knowledge_context(memory_snapshot),
            memory_summary=self._build_memory_summary(memory_snapshot),
        )

    def analyze(
        self,
        case_dir: str | Path,
        *,
        correlation_id: str | None = None,
        memory_snapshot: dict[str, Any] | None = None,
    ) -> ExecutionFeedback:
        snapshot = memory_snapshot or self._load_snapshot(case_dir, correlation_id=correlation_id)
        return self.analyze_snapshot(
            snapshot,
            case_dir=case_dir,
            correlation_id=correlation_id,
        )

    def _load_snapshot(
        self,
        case_dir: str | Path,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        if self.memory_manager is None:
            return {
                "knowledge": {"available": False},
                "events": {"available": False, "events": []},
                "reasoning": {"available": False, "traces": []},
                "tasks": {"available": False, "workflows": []},
                "evaluations": {"available": False, "evaluations": []},
            }

        manager = self.memory_manager
        case_path = Path(case_dir)
        knowledge: dict[str, Any]
        try:
            record = manager.load_knowledge_memory(case_path)
            knowledge = {"available": True, "payload": record.payload}
        except Exception as exc:
            knowledge = {"available": False, "error": str(exc)}

        manager.events.bind_case(case_path)
        manager.reasoning.bind_case(case_path)
        manager.tasks.bind_case(case_path)
        manager.evaluations.bind_case(case_path)

        return {
            "knowledge": knowledge,
            "events": {
                "available": True,
                "events": manager.events.list_events(correlation_id=correlation_id),
            },
            "reasoning": {
                "available": True,
                "traces": manager.reasoning.list_traces(correlation_id=correlation_id),
            },
            "tasks": {
                "available": True,
                "workflows": manager.tasks.list_workflows(correlation_id=correlation_id),
            },
            "evaluations": {
                "available": True,
                "evaluations": manager.evaluations.list_evaluations(correlation_id=correlation_id),
            },
        }

    @staticmethod
    def _extract_knowledge_context(memory_snapshot: dict[str, Any]) -> dict[str, Any]:
        knowledge = memory_snapshot.get("knowledge", {})
        if not knowledge.get("available"):
            return {"available": False}
        payload = knowledge.get("payload", {})
        return {
            "available": True,
            "case_id": payload.get("case_id"),
            "node_count": payload.get("node_count", 0),
            "edge_count": payload.get("edge_count", 0),
        }

    @staticmethod
    def _build_memory_summary(memory_snapshot: dict[str, Any]) -> dict[str, Any]:
        evaluations = memory_snapshot.get("evaluations", {}).get("evaluations", [])
        workflows = memory_snapshot.get("tasks", {}).get("workflows", [])
        events = memory_snapshot.get("events", {}).get("events", [])
        traces = memory_snapshot.get("reasoning", {}).get("traces", [])

        return {
            "evaluation_count": len(evaluations),
            "failed_evaluation_count": sum(1 for entry in evaluations if entry.get("status") == "failed"),
            "workflow_count": len(workflows),
            "failed_workflow_count": sum(1 for entry in workflows if entry.get("status") == "FAILED"),
            "event_count": len(events),
            "runtime_failed_count": sum(
                1 for event in events if event.get("event_type") == "RuntimeFailed"
            ),
            "reasoning_trace_count": len(traces),
            "failed_reasoning_count": sum(1 for trace in traces if trace.get("status") == "failed"),
        }
