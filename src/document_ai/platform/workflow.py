from __future__ import annotations

from dataclasses import dataclass, field

from document_ai.platform.models import WorkflowResult, WorkflowStep
from document_ai.platform.task_graph import TaskGraph


@dataclass
class Workflow:
    workflow_id: str
    task_graph: TaskGraph
    status: str = "pending"
    steps: list[WorkflowStep] = field(default_factory=list)

    @classmethod
    def from_task_graph(cls, task_graph: TaskGraph) -> "Workflow":
        steps = [
            WorkflowStep(
                step_id=f"step-{idx + 1}",
                name=task.name,
                task_id=task.task_id,
            )
            for idx, task in enumerate(task_graph.ordered_tasks())
        ]
        return cls(workflow_id=f"wf-{task_graph.graph_id}", task_graph=task_graph, steps=steps)

    def mark_running(self) -> None:
        self.status = "running"

    def complete(
        self,
        result: dict[str, object],
        *,
        status: str = "completed",
        executed_tasks: list[str] | None = None,
    ) -> WorkflowResult:
        self.status = status
        executed = executed_tasks or [task.task_id for task in self.task_graph.ordered_tasks()]
        executed_set = set(executed)
        for step in self.steps:
            if step.task_id in executed_set and step.status not in {"failed", "skipped"}:
                step.status = "completed" if status == "completed" else step.status
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status=status,  # type: ignore[arg-type]
            result=result,
            executed_tasks=list(executed),
        )
