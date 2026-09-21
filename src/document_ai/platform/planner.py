from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.platform.memory.knowledge_memory import KnowledgeMemory
from document_ai.platform.memory_manager import MemoryManager
from document_ai.platform.models import PlannerMode, PlannerRequest
from document_ai.platform.planning.goal_parser import is_document_change_path, parse_goal
from document_ai.platform.planning.intent_classifier import classify_intent, detect_operation_intent
from document_ai.platform.planning.planner import AdaptivePlanner, MemoryQueryContext, PlanningResult
from document_ai.platform.orchestration.execution_plan import ExecutionPlan


class RuleBasedPlanner:
    """Backward-compatible planner facade over the adaptive planner."""

    def __init__(self, *, memory_context: MemoryQueryContext | None = None) -> None:
        self._adaptive = AdaptivePlanner(memory_context=memory_context or MemoryQueryContext())

    @staticmethod
    def detect_operation_intent(text: str) -> bool:
        return detect_operation_intent(text)

    @classmethod
    def _is_document_change_path(cls, change: Any) -> bool:
        return is_document_change_path(change)

    @classmethod
    def resolve_mode(
        cls,
        *,
        intent: str | None = None,
        change: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> PlannerMode:
        parsed = parse_goal(
            case_dir=".",
            change=change if change is not None else "",
            metadata=metadata,
            intent=intent,
        )
        planner_intent = classify_intent(parsed)
        return AdaptivePlanner.resolve_legacy_mode(planner_intent, parsed)

    def create_request(
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
    ) -> PlannerRequest:
        return self._adaptive.plan(
            case_dir=case_dir,
            change=change,
            dry_run=dry_run,
            apply=apply,
            report_path=report_path,
            change_path=change_path,
            request_id=request_id,
            metadata=metadata,
            intent=intent,
            goal=goal,
        ).request

    def create_execution_plan(
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
        return self._adaptive.orchestrate(
            case_dir=case_dir,
            change=change,
            dry_run=dry_run,
            apply=apply,
            report_path=report_path,
            change_path=change_path,
            request_id=request_id,
            metadata=metadata,
            intent=intent,
            goal=goal,
        )

    def plan_workflow(
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
        return self._adaptive.plan(
            case_dir=case_dir,
            change=change,
            dry_run=dry_run,
            apply=apply,
            report_path=report_path,
            change_path=change_path,
            request_id=request_id,
            metadata=metadata,
            intent=intent,
            goal=goal,
        )

    def lookup_requirement_context(
        self,
        knowledge_memory: KnowledgeMemory | MemoryManager,
        req_ids: list[str],
    ) -> dict[str, Any]:
        """Read requirement nodes and downstream links from Knowledge Memory."""
        if isinstance(knowledge_memory, MemoryManager):
            graph = knowledge_memory.knowledge.graph
        else:
            graph = knowledge_memory.graph
        if graph is None:
            return {"available": False, "requirements": []}

        requirements: list[dict[str, Any]] = []
        for req_id in req_ids:
            node = graph.find_node(req_id)
            requirements.append(
                {
                    "req_id": req_id,
                    "node": node.to_dict() if node else None,
                    "downstream": graph.find_downstream(req_id, max_depth=1),
                    "related_documents": graph.find_related_documents(req_id),
                }
            )
        return {"available": True, "requirements": requirements}
