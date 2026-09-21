from __future__ import annotations

from typing import Any, Literal

from document_ai.platform.improvement.execution_feedback import ExecutionFeedback, Recommendation

ExecutionStrategy = Literal["sequential", "parallel"]


def select_execution_strategy(feedback: ExecutionFeedback) -> ExecutionStrategy:
    for recommendation in feedback.strategy_recommendations:
        strategy = recommendation.metadata.get("execution_strategy")
        if strategy in {"sequential", "parallel"}:
            return strategy  # type: ignore[return-value]

    if feedback.failure_patterns:
        return "sequential"
    return "sequential"


def build_strategy_recommendations(
    memory_snapshot: dict[str, Any],
    *,
    failure_patterns: list,
) -> list[Recommendation]:
    from document_ai.platform.improvement.improvement_rules import recommend_strategy_changes

    return recommend_strategy_changes(memory_snapshot, failure_patterns=failure_patterns)
