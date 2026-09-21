from __future__ import annotations

from dataclasses import dataclass, field

from document_ai.platform.models import PlannerRequest, TaskSpec


@dataclass
class TaskGraph:
    graph_id: str
    tasks: list[TaskSpec]
    metadata: dict[str, object] = field(default_factory=dict)

    def get_task(self, task_id: str) -> TaskSpec:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(f"Unknown task_id: {task_id}")

    def ordered_tasks(self) -> list[TaskSpec]:
        ordered: list[TaskSpec] = []
        remaining = {task.task_id: task for task in self.tasks}
        resolved: set[str] = set()

        while remaining:
            ready = [
                task for task in remaining.values()
                if all(dep in resolved for dep in task.dependencies)
            ]
            if not ready:
                unresolved = ", ".join(sorted(remaining))
                raise ValueError(f"Task graph contains a cycle or missing dependency: {unresolved}")
            ready.sort(key=lambda task: task.task_id)
            for task in ready:
                ordered.append(task)
                resolved.add(task.task_id)
                del remaining[task.task_id]
        return ordered


def build_task_graph(request: PlannerRequest) -> TaskGraph:
    if request.metadata.get("workflow_template"):
        from document_ai.platform.planning.workflow_builder import build_task_graph_from_plan

        return build_task_graph_from_plan(request)

    if request.mode == "operation_request":
        sample_dir = request.metadata.get("sample_dir", "")
        task = TaskSpec(
            task_id="task-operation-incident-analysis",
            name="Analyze GPU server incident samples",
            harness="operation",
            action="analyze_incidents",
            agent_assignment="operation_harness",
            metadata={
                "case_dir": str(request.case_dir),
                "sample_dir": str(sample_dir),
            },
        )
        return TaskGraph(
            graph_id=f"tg-{request.request_id}",
            tasks=[task],
            metadata={"mode": request.mode},
        )

    task = TaskSpec(
        task_id="task-document-change-pipeline",
        name="Run document change pipeline",
        harness="document",
        action="run_change_pipeline",
        agent_assignment="document_harness",
        metadata={
            "case_dir": str(request.case_dir),
            "dry_run": request.dry_run,
            "apply": request.apply,
        },
    )
    return TaskGraph(
        graph_id=f"tg-{request.request_id}",
        tasks=[task],
        metadata={"mode": request.mode},
    )
