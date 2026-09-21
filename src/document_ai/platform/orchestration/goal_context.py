from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from document_ai.platform.planning.goal_parser import ParsedGoal
from document_ai.platform.planning.intent_classifier import PlannerIntent


@dataclass
class MemoryInsights:
    has_previous_failures: bool = False
    failed_evaluation_count: int = 0
    failed_workflow_count: int = 0
    runtime_failed_event_count: int = 0
    recent_evaluations: list[dict[str, Any]] = field(default_factory=list)
    recent_workflows: list[dict[str, Any]] = field(default_factory=list)
    recent_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_previous_failures": self.has_previous_failures,
            "failed_evaluation_count": self.failed_evaluation_count,
            "failed_workflow_count": self.failed_workflow_count,
            "runtime_failed_event_count": self.runtime_failed_event_count,
            "recent_evaluations": self.recent_evaluations,
            "recent_workflows": self.recent_workflows,
            "recent_events": self.recent_events,
        }


@dataclass
class GoalContext:
    goal: str
    parsed_goal: ParsedGoal
    intent: PlannerIntent
    hybrid: bool
    memory_snapshot: dict[str, Any]
    memory_insights: MemoryInsights
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "intent": self.intent,
            "hybrid": self.hybrid,
            "memory_insights": self.memory_insights.to_dict(),
            "metadata": self.metadata,
        }


def analyze_memory_snapshot(memory_snapshot: dict[str, Any]) -> MemoryInsights:
    evaluations = memory_snapshot.get("evaluations", {}).get("evaluations", [])
    workflows = memory_snapshot.get("tasks", {}).get("workflows", [])
    events = memory_snapshot.get("events", {}).get("events", [])

    failed_evaluations = [entry for entry in evaluations if entry.get("status") == "failed"]
    failed_workflows = [entry for entry in workflows if entry.get("status") == "FAILED"]
    runtime_failed_events = [
        event for event in events if event.get("event_type") == "RuntimeFailed"
    ]

    return MemoryInsights(
        has_previous_failures=bool(failed_evaluations or failed_workflows or runtime_failed_events),
        failed_evaluation_count=len(failed_evaluations),
        failed_workflow_count=len(failed_workflows),
        runtime_failed_event_count=len(runtime_failed_events),
        recent_evaluations=list(evaluations[-3:]),
        recent_workflows=list(workflows[-3:]),
        recent_events=list(events[-5:]),
    )


def build_goal_context(
    parsed_goal: ParsedGoal,
    *,
    intent: PlannerIntent,
    hybrid: bool,
    memory_snapshot: dict[str, Any],
) -> GoalContext:
    goal_text = parsed_goal.goal or parsed_goal.text or parsed_goal.combined_text
    memory_insights = analyze_memory_snapshot(memory_snapshot)
    return GoalContext(
        goal=goal_text,
        parsed_goal=parsed_goal,
        intent=intent,
        hybrid=hybrid,
        memory_snapshot=memory_snapshot,
        memory_insights=memory_insights,
        metadata=dict(parsed_goal.metadata),
    )
