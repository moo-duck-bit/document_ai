from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FailurePattern:
    pattern_id: str
    category: str
    description: str
    count: int
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "category": self.category,
            "description": self.description,
            "count": self.count,
            "evidence": self.evidence,
        }


@dataclass
class Recommendation:
    category: str
    action: str
    reason: str
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionFeedback:
    case_id: str
    correlation_id: str | None = None
    failure_patterns: list[FailurePattern] = field(default_factory=list)
    retry_candidates: list[Recommendation] = field(default_factory=list)
    planner_recommendations: list[Recommendation] = field(default_factory=list)
    harness_recommendations: list[Recommendation] = field(default_factory=list)
    workflow_recommendations: list[Recommendation] = field(default_factory=list)
    strategy_recommendations: list[Recommendation] = field(default_factory=list)
    knowledge_context: dict[str, Any] = field(default_factory=dict)
    memory_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "correlation_id": self.correlation_id,
            "failure_patterns": [pattern.to_dict() for pattern in self.failure_patterns],
            "retry_candidates": [item.to_dict() for item in self.retry_candidates],
            "planner_recommendations": [item.to_dict() for item in self.planner_recommendations],
            "harness_recommendations": [item.to_dict() for item in self.harness_recommendations],
            "workflow_recommendations": [item.to_dict() for item in self.workflow_recommendations],
            "strategy_recommendations": [item.to_dict() for item in self.strategy_recommendations],
            "knowledge_context": self.knowledge_context,
            "memory_summary": self.memory_summary,
        }

    @property
    def has_actionable_feedback(self) -> bool:
        return bool(
            self.failure_patterns
            or self.retry_candidates
            or self.planner_recommendations
            or self.harness_recommendations
            or self.workflow_recommendations
            or self.strategy_recommendations
        )
