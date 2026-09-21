from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PlannerMode = Literal["change_request", "operation_request"]
WorkflowStatus = Literal["pending", "running", "completed", "failed"]
TaskState = Literal["pending", "running", "completed", "failed"]


@dataclass(frozen=True)
class PlannerRequest:
    request_id: str
    mode: PlannerMode
    case_dir: Path
    change: dict[str, Any] | Path
    dry_run: bool = True
    apply: bool = False
    report_path: Path | None = None
    change_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    name: str
    harness: str
    action: str
    state: TaskState = "pending"
    dependencies: tuple[str, ...] = ()
    agent_assignment: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowStep:
    step_id: str
    name: str
    task_id: str
    status: WorkflowStatus = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    workflow_id: str
    status: WorkflowStatus
    result: dict[str, Any]
    executed_tasks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRecord:
    memory_type: str
    action: str
    payload: dict[str, Any]


@dataclass
class RuntimeResult:
    planner_request: PlannerRequest
    workflow_id: str
    task_graph_id: str
    harness: str
    result: dict[str, Any]
    memory_records: list[MemoryRecord] = field(default_factory=list)
    knowledge_context: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    event_refs: list[str] = field(default_factory=list)
    reasoning_id: str = ""
    evaluation_id: str = ""
    task_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    execution_plan_id: str = ""
