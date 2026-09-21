from __future__ import annotations

from typing import Any

from document_ai.platform.improvement.execution_feedback import ExecutionFeedback, Recommendation


def build_planner_recommendations(
    memory_snapshot: dict[str, Any],
    *,
    failure_patterns: list,
    retry_candidates: list[Recommendation],
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    evaluations = memory_snapshot.get("evaluations", {}).get("evaluations", [])
    events = memory_snapshot.get("events", {}).get("events", [])

    failed_evaluations = [entry for entry in evaluations if entry.get("status") == "failed"]
    if failed_evaluations:
        recommendations.append(
            Recommendation(
                category="planner",
                action="include_failure_context",
                reason="Previous evaluations failed; planner should include failure context in metadata",
                confidence=0.8,
                metadata={"failed_evaluation_ids": [entry.get("evaluation_id") for entry in failed_evaluations[-3:]]},
            )
        )

    runtime_failed = [event for event in events if event.get("event_type") == "RuntimeFailed"]
    if runtime_failed:
        recommendations.append(
            Recommendation(
                category="planner",
                action="avoid_repeat_plan",
                reason="Recent runtime failure suggests adjusting goal, change input, or harness selection",
                confidence=0.75,
                metadata={"last_failed_task_id": runtime_failed[-1].get("task_id")},
            )
        )

    if retry_candidates:
        recommendations.append(
            Recommendation(
                category="planner",
                action="plan_retry_first",
                reason="Retry candidates exist; planner should prioritize retry-aware execution plan",
                confidence=0.7,
                metadata={"retry_actions": [item.action for item in retry_candidates]},
            )
        )

    if failure_patterns:
        recommendations.append(
            Recommendation(
                category="planner",
                action="apply_improvement_feedback",
                reason="Failure patterns detected; planner should consult execution feedback before orchestrating",
                confidence=0.85,
                metadata={"pattern_ids": [pattern.pattern_id for pattern in failure_patterns]},
            )
        )

    return recommendations


def apply_planner_feedback(
    feedback: ExecutionFeedback,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge execution feedback into planner metadata without changing planner APIs."""
    merged = dict(metadata or {})
    merged["execution_feedback"] = feedback.to_dict()
    merged["improvement_recommendations"] = {
        "planner": [item.to_dict() for item in feedback.planner_recommendations],
        "harness": [item.to_dict() for item in feedback.harness_recommendations],
        "workflow": [item.to_dict() for item in feedback.workflow_recommendations],
        "strategy": [item.to_dict() for item in feedback.strategy_recommendations],
        "retry": [item.to_dict() for item in feedback.retry_candidates],
    }
    return merged
