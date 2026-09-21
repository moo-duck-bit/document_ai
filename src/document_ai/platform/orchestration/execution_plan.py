from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from document_ai.platform.models import PlannerRequest
from document_ai.platform.orchestration.goal_context import GoalContext
from document_ai.platform.task_graph import TaskGraph
from document_ai.platform.workflow import Workflow

ExecutionStrategy = Literal["sequential", "parallel"]


@dataclass
class ExecutionPlan:
    plan_id: str
    goal_context: GoalContext
    workflows: list[Workflow]
    task_graphs: list[TaskGraph]
    harness_sequence: list[str]
    execution_strategy: ExecutionStrategy
    estimated_steps: int
    request: PlannerRequest
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_workflow(self) -> Workflow:
        return self.workflows[0]

    @property
    def primary_task_graph(self) -> TaskGraph:
        return self.task_graphs[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal_context.goal,
            "intent": self.goal_context.intent,
            "hybrid": self.goal_context.hybrid,
            "workflows": [workflow.workflow_id for workflow in self.workflows],
            "task_graphs": [task_graph.graph_id for task_graph in self.task_graphs],
            "harness_sequence": list(self.harness_sequence),
            "execution_strategy": self.execution_strategy,
            "estimated_steps": self.estimated_steps,
            "memory_insights": self.goal_context.memory_insights.to_dict(),
            "metadata": self.metadata,
        }


def new_plan_id() -> str:
    return f"plan-{uuid.uuid4().hex[:12]}"
