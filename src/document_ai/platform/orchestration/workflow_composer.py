from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.platform.models import PlannerMode, PlannerRequest
from document_ai.platform.orchestration.execution_plan import ExecutionPlan, ExecutionStrategy, new_plan_id
from document_ai.platform.orchestration.goal_context import GoalContext
from document_ai.platform.planning.planner_modes import intent_action, resolve_legacy_mode
from document_ai.platform.planning.workflow_builder import build_task_graph_from_template
from document_ai.platform.planning.workflow_templates import (
    DOCUMENT_WORKFLOW,
    HYBRID_WORKFLOW,
    OPERATION_WORKFLOW,
    WorkflowTemplate,
    get_template,
    select_workflow_template,
)
from document_ai.platform.workflow import Workflow


def select_templates(goal_context: GoalContext) -> list[WorkflowTemplate]:
    consensus = goal_context.metadata.get("collaboration_consensus")
    if isinstance(consensus, dict) and consensus.get("workflow_template"):
        return [get_template(consensus["workflow_template"])]
    if goal_context.hybrid:
        return [HYBRID_WORKFLOW]
    if goal_context.intent == "operation_analysis":
        return [OPERATION_WORKFLOW]
    return [DOCUMENT_WORKFLOW]


def compose_execution_plan(
    goal_context: GoalContext,
    *,
    request: PlannerRequest,
    execution_strategy: ExecutionStrategy = "sequential",
) -> ExecutionPlan:
    templates = select_templates(goal_context)
    workflows: list[Workflow] = []
    task_graphs = []
    harness_sequence: list[str] = []
    estimated_steps = 0

    for template in templates:
        task_graph = build_task_graph_from_template(request, template)
        workflow = Workflow.from_task_graph(task_graph)
        task_graphs.append(task_graph)
        workflows.append(workflow)
        ordered = task_graph.ordered_tasks()
        harness_sequence.extend(task.harness for task in ordered)
        estimated_steps += len(ordered)

    return ExecutionPlan(
        plan_id=new_plan_id(),
        goal_context=goal_context,
        workflows=workflows,
        task_graphs=task_graphs,
        harness_sequence=harness_sequence,
        execution_strategy=execution_strategy,
        estimated_steps=estimated_steps,
        request=request,
        metadata={
            "workflow_templates": [template.template_id for template in templates],
            "planner_intent": goal_context.intent,
            "hybrid": goal_context.hybrid,
        },
    )


def build_planner_request(
    goal_context: GoalContext,
    *,
    case_dir: str | Path,
    change: dict[str, Any] | Path | str,
    dry_run: bool,
    apply: bool,
    report_path: Path | None,
    change_path: Path | None,
    request_id: str,
    memory_snapshot: dict[str, Any],
) -> PlannerRequest:
    mode = resolve_legacy_mode(goal_context.intent, goal_context.parsed_goal)
    template = select_workflow_template(goal_context.intent, hybrid=goal_context.hybrid)

    if mode == "operation_request":
        if isinstance(change, dict):
            resolved_change: dict[str, Any] | Path | str = change
        elif isinstance(change, Path):
            resolved_change = change
        else:
            resolved_change = str(change)
    else:
        resolved_change = (
            Path(change) if isinstance(change, (str, Path)) and not isinstance(change, dict) else change
        )

    request_metadata = {
        **goal_context.metadata,
        "planner_intent": goal_context.intent,
        "workflow_template": template.template_id,
        "goal": goal_context.goal,
        "hybrid": goal_context.hybrid,
        "intent_action": intent_action(goal_context.intent),
        "memory_snapshot": memory_snapshot,
        "memory_insights": goal_context.memory_insights.to_dict(),
        "goal_context": goal_context.to_dict(),
    }

    return PlannerRequest(
        request_id=request_id,
        mode=mode,
        case_dir=Path(case_dir),
        change=resolved_change,  # type: ignore[arg-type]
        dry_run=dry_run,
        apply=apply,
        report_path=report_path,
        change_path=change_path,
        metadata=request_metadata,
    )
