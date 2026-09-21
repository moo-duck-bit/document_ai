from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from document_ai.platform.planning.intent_classifier import PlannerIntent

TaskBlueprint = dict[str, Any]


@dataclass(frozen=True)
class WorkflowTemplate:
    template_id: str
    name: str
    description: str
    intents: tuple[PlannerIntent, ...]
    task_blueprints: tuple[TaskBlueprint, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


DOCUMENT_WORKFLOW = WorkflowTemplate(
    template_id="document_workflow",
    name="Document Workflow",
    description="Run the document change impact pipeline.",
    intents=("document_change", "document_generation", "security_review", "knowledge_query"),
    task_blueprints=(
        {
            "task_id": "task-document-change-pipeline",
            "name": "Run document change pipeline",
            "harness": "document",
            "action": "run_change_pipeline",
            "agent_assignment": "document_harness",
            "dependencies": (),
        },
    ),
)

OPERATION_WORKFLOW = WorkflowTemplate(
    template_id="operation_workflow",
    name="Operation Workflow",
    description="Analyze GPU/Docker sample logs and produce incident report.",
    intents=("operation_analysis",),
    task_blueprints=(
        {
            "task_id": "task-operation-incident-analysis",
            "name": "Analyze GPU server incident samples",
            "harness": "operation",
            "action": "analyze_incidents",
            "agent_assignment": "operation_harness",
            "dependencies": (),
        },
    ),
)

HYBRID_WORKFLOW = WorkflowTemplate(
    template_id="hybrid_workflow",
    name="Hybrid Workflow",
    description="Document change analysis followed by operational incident review.",
    intents=("document_change",),
    task_blueprints=(
        {
            "task_id": "task-document-change-pipeline",
            "name": "Run document change pipeline",
            "harness": "document",
            "action": "run_change_pipeline",
            "agent_assignment": "document_harness",
            "dependencies": (),
        },
        {
            "task_id": "task-operation-incident-analysis",
            "name": "Analyze GPU server incident samples",
            "harness": "operation",
            "action": "analyze_incidents",
            "agent_assignment": "operation_harness",
            "dependencies": ("task-document-change-pipeline",),
        },
    ),
    metadata={"includes_evaluation": True},
)

TEMPLATES: dict[str, WorkflowTemplate] = {
    DOCUMENT_WORKFLOW.template_id: DOCUMENT_WORKFLOW,
    OPERATION_WORKFLOW.template_id: OPERATION_WORKFLOW,
    HYBRID_WORKFLOW.template_id: HYBRID_WORKFLOW,
}


def get_template(template_id: str) -> WorkflowTemplate:
    try:
        return TEMPLATES[template_id]
    except KeyError as exc:
        known = ", ".join(sorted(TEMPLATES))
        raise KeyError(f"Unknown workflow template {template_id!r}. Known: {known}") from exc


def select_workflow_template(intent: PlannerIntent, *, hybrid: bool = False) -> WorkflowTemplate:
    if hybrid:
        return HYBRID_WORKFLOW
    if intent == "operation_analysis":
        return OPERATION_WORKFLOW
    return DOCUMENT_WORKFLOW
