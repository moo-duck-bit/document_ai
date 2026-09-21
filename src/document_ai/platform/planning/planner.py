from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from document_ai.platform.memory_manager import MemoryManager
from document_ai.platform.models import PlannerMode, PlannerRequest
from document_ai.platform.collaboration.collaboration_manager import CollaborationManager
from document_ai.platform.improvement.execution_feedback import ExecutionFeedback
from document_ai.platform.improvement.improvement_engine import ImprovementEngine
from document_ai.platform.orchestration.execution_plan import ExecutionPlan
from document_ai.platform.orchestration.goal_orchestrator import GoalOrchestrator
from document_ai.platform.planning.goal_parser import ParsedGoal, parse_goal
from document_ai.platform.planning.planner_modes import intent_action, resolve_legacy_mode
from document_ai.platform.planning.intent_classifier import PlannerIntent
from document_ai.platform.planning.workflow_templates import WorkflowTemplate, select_workflow_template
from document_ai.platform.task_graph import TaskGraph
from document_ai.platform.workflow import Workflow

class PlannerBackend(Protocol):
    """Future LLM planner backend interface."""

    def plan(self, parsed_goal: ParsedGoal, memory_context: dict[str, Any]) -> "PlanningResult":
        ...


@dataclass
class MemoryQueryContext:
    """Read-only interface for Platform Memory lookups during planning."""

    memory_manager: MemoryManager | None = None
    improvement_engine: ImprovementEngine | None = None

    def _improvement_engine(self) -> ImprovementEngine:
        if self.improvement_engine is not None:
            return self.improvement_engine
        return ImprovementEngine(self.memory_manager)

    def query_knowledge(self, case_dir: str | Path) -> dict[str, Any]:
        if self.memory_manager is None:
            return {"available": False}
        case_path = Path(case_dir)
        try:
            record = self.memory_manager.load_knowledge_memory(case_path)
            return {"available": True, "payload": record.payload}
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    def query_events(self, case_dir: str | Path, *, correlation_id: str | None = None) -> dict[str, Any]:
        if self.memory_manager is None:
            return {"available": False, "events": []}
        self.memory_manager.events.bind_case(case_dir)
        events = self.memory_manager.events.list_events(correlation_id=correlation_id)
        return {"available": True, "events": events}

    def query_reasoning(self, case_dir: str | Path, *, correlation_id: str | None = None) -> dict[str, Any]:
        if self.memory_manager is None:
            return {"available": False, "traces": []}
        self.memory_manager.reasoning.bind_case(case_dir)
        traces = self.memory_manager.reasoning.list_traces(correlation_id=correlation_id)
        return {"available": True, "traces": traces}

    def query_tasks(self, case_dir: str | Path, *, correlation_id: str | None = None) -> dict[str, Any]:
        if self.memory_manager is None:
            return {"available": False, "workflows": []}
        self.memory_manager.tasks.bind_case(case_dir)
        workflows = self.memory_manager.tasks.list_workflows(correlation_id=correlation_id)
        return {"available": True, "workflows": workflows}

    def query_evaluations(self, case_dir: str | Path, *, correlation_id: str | None = None) -> dict[str, Any]:
        if self.memory_manager is None:
            return {"available": False, "evaluations": []}
        self.memory_manager.evaluations.bind_case(case_dir)
        evaluations = self.memory_manager.evaluations.list_evaluations(correlation_id=correlation_id)
        return {"available": True, "evaluations": evaluations}

    def snapshot(self, case_dir: str | Path, *, correlation_id: str | None = None) -> dict[str, Any]:
        return {
            "knowledge": self.query_knowledge(case_dir),
            "events": self.query_events(case_dir, correlation_id=correlation_id),
            "reasoning": self.query_reasoning(case_dir, correlation_id=correlation_id),
            "tasks": self.query_tasks(case_dir, correlation_id=correlation_id),
            "evaluations": self.query_evaluations(case_dir, correlation_id=correlation_id),
        }

    def query_execution_feedback(
        self,
        case_dir: str | Path,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        feedback = self._improvement_engine().analyze(
            case_dir,
            correlation_id=correlation_id,
            memory_snapshot=self.snapshot(case_dir, correlation_id=correlation_id),
        )
        return feedback.to_dict()


@dataclass
class PlanningResult:
    parsed_goal: ParsedGoal
    intent: PlannerIntent
    template: WorkflowTemplate
    request: PlannerRequest
    task_graph: TaskGraph
    workflow: Workflow
    memory_context: dict[str, Any] = field(default_factory=dict)
    harness_assignments: list[dict[str, str]] = field(default_factory=list)
    execution_plan: ExecutionPlan | None = None
    collaboration_consensus: dict[str, Any] | None = None


class AdaptivePlanner:
    """Goal-based workflow planner with rule backend and LLM-ready interface."""

    def __init__(
        self,
        *,
        memory_context: MemoryQueryContext | None = None,
        backend: PlannerBackend | None = None,
        collaboration_manager: CollaborationManager | None = None,
    ) -> None:
        self.memory_context = memory_context or MemoryQueryContext()
        self.backend = backend
        self.orchestrator = GoalOrchestrator()
        self.collaboration_manager = collaboration_manager or CollaborationManager()

    def _run_collaboration(
        self,
        *,
        case_dir: str | Path,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        consensus = self.collaboration_manager.collaborate(
            parsed_goal=parsed_goal,
            memory_snapshot=memory_snapshot,
            case_dir=case_dir,
            metadata=metadata,
        )
        resolved = dict(metadata or {})
        resolved["collaboration_consensus"] = consensus.to_dict()
        return resolved

    def orchestrate(
        self,
        *,
        case_dir: str | Path,
        change: dict[str, Any] | Path | str,
        dry_run: bool = True,
        apply: bool = False,
        report_path: str | Path | None = None,
        change_path: str | Path | None = None,
        request_id: str = "platform-runtime",
        metadata: dict[str, Any] | None = None,
        intent: str | None = None,
        goal: str | None = None,
    ) -> ExecutionPlan:
        memory_snapshot = self.memory_context.snapshot(
            case_dir,
            correlation_id=(metadata or {}).get("correlation_id"),
        )
        parsed_goal = parse_goal(
            case_dir=case_dir,
            change=change,
            metadata=metadata,
            intent=intent,
            goal=goal,
        )
        resolved_metadata = self._run_collaboration(
            case_dir=case_dir,
            parsed_goal=parsed_goal,
            memory_snapshot=memory_snapshot,
            metadata=metadata,
        )
        return self.orchestrator.orchestrate(
            case_dir=case_dir,
            change=change,
            dry_run=dry_run,
            apply=apply,
            report_path=report_path,
            change_path=change_path,
            request_id=request_id,
            metadata=resolved_metadata,
            intent=intent,
            goal=goal,
            memory_snapshot=memory_snapshot,
        )

    def query_execution_feedback(
        self,
        case_dir: str | Path,
        *,
        correlation_id: str | None = None,
    ) -> ExecutionFeedback:
        """Read-only self-improvement feedback from prior executions."""
        return self.memory_context._improvement_engine().analyze(
            case_dir,
            correlation_id=correlation_id,
            memory_snapshot=self.memory_context.snapshot(
                case_dir,
                correlation_id=correlation_id,
            ),
        )

    def plan(
        self,
        *,
        case_dir: str | Path,
        change: dict[str, Any] | Path | str,
        dry_run: bool = True,
        apply: bool = False,
        report_path: str | Path | None = None,
        change_path: str | Path | None = None,
        request_id: str = "platform-runtime",
        metadata: dict[str, Any] | None = None,
        intent: str | None = None,
        goal: str | None = None,
    ) -> PlanningResult:
        parsed_goal = parse_goal(
            case_dir=case_dir,
            change=change,
            metadata=metadata,
            intent=intent,
            goal=goal,
        )

        memory_snapshot = self.memory_context.snapshot(
            case_dir,
            correlation_id=(metadata or {}).get("correlation_id"),
        )

        if self.backend is not None:
            return self.backend.plan(parsed_goal, memory_snapshot)

        resolved_metadata = self._run_collaboration(
            case_dir=case_dir,
            parsed_goal=parsed_goal,
            memory_snapshot=memory_snapshot,
            metadata=metadata,
        )
        execution_plan = self.orchestrator.orchestrate(
            case_dir=case_dir,
            change=change,
            dry_run=dry_run,
            apply=apply,
            report_path=report_path,
            change_path=change_path,
            request_id=request_id,
            metadata=resolved_metadata,
            intent=intent,
            goal=goal,
            memory_snapshot=memory_snapshot,
        )
        request = execution_plan.request
        task_graph = execution_plan.primary_task_graph
        workflow = execution_plan.primary_workflow
        harness_assignments = [
            {"task_id": task.task_id, "harness": task.harness, "action": task.action}
            for task in task_graph.ordered_tasks()
        ]

        return PlanningResult(
            parsed_goal=parsed_goal,
            intent=execution_plan.goal_context.intent,
            template=select_workflow_template(
                execution_plan.goal_context.intent,
                hybrid=execution_plan.goal_context.hybrid,
            ),
            request=request,
            task_graph=task_graph,
            workflow=workflow,
            memory_context=memory_snapshot,
            harness_assignments=harness_assignments,
            execution_plan=execution_plan,
            collaboration_consensus=resolved_metadata.get("collaboration_consensus"),
        )

    resolve_legacy_mode = staticmethod(resolve_legacy_mode)
    _intent_action = staticmethod(intent_action)
