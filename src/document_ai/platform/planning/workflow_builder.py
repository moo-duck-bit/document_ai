from __future__ import annotations

from document_ai.platform.models import PlannerRequest, TaskSpec
from document_ai.platform.planning.workflow_templates import WorkflowTemplate
from document_ai.platform.task_graph import TaskGraph


def build_task_graph_from_template(
    request: PlannerRequest,
    template: WorkflowTemplate,
) -> TaskGraph:
    tasks: list[TaskSpec] = []
    for blueprint in template.task_blueprints:
        metadata = {
            "case_dir": str(request.case_dir),
            "dry_run": request.dry_run,
            "apply": request.apply,
            "planner_intent": request.metadata.get("planner_intent", ""),
            "workflow_template": template.template_id,
        }
        if blueprint["harness"] == "operation":
            metadata["sample_dir"] = str(request.metadata.get("sample_dir", ""))
        if request.metadata.get("intent_action"):
            metadata["intent_action"] = request.metadata["intent_action"]

        tasks.append(
            TaskSpec(
                task_id=blueprint["task_id"],
                name=blueprint["name"],
                harness=blueprint["harness"],
                action=blueprint["action"],
                agent_assignment=blueprint.get("agent_assignment"),
                dependencies=tuple(blueprint.get("dependencies", ())),
                metadata=metadata,
            )
        )

    return TaskGraph(
        graph_id=f"tg-{request.request_id}",
        tasks=tasks,
        metadata={
            "mode": request.mode,
            "workflow_template": template.template_id,
            "planner_intent": request.metadata.get("planner_intent", ""),
        },
    )


def build_task_graph_from_plan(request: PlannerRequest) -> TaskGraph:
    template_id = str(request.metadata.get("workflow_template", "document_workflow"))
    from document_ai.platform.planning.workflow_templates import get_template

    template = get_template(template_id)
    return build_task_graph_from_template(request, template)
