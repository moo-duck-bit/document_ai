from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from document_ai.platform.orchestration.execution_plan import ExecutionPlan
from document_ai.platform.orchestration.goal_context import GoalContext, build_goal_context
from document_ai.platform.collaboration.consensus import apply_consensus_to_goal_context
from document_ai.platform.orchestration.workflow_composer import build_planner_request, compose_execution_plan
from document_ai.platform.planning.goal_parser import ParsedGoal, parse_goal
from document_ai.platform.planning.intent_classifier import classify_intent, detect_hybrid_intent


class GoalOrchestrator:
    """Compose execution plans from goals, metadata, and memory snapshots."""

    def analyze_goal(
        self,
        *,
        goal: str | None,
        metadata: dict[str, Any] | None,
        memory_snapshot: dict[str, Any],
        parsed_goal: ParsedGoal | None = None,
        case_dir: str | Path | None = None,
        change: Any = None,
        intent: str | None = None,
    ):
        if parsed_goal is None:
            parsed_goal = parse_goal(
                case_dir=case_dir or ".",
                change=change if change is not None else "",
                metadata=metadata,
                intent=intent,
                goal=goal,
            )
        planner_intent = classify_intent(parsed_goal)
        hybrid = detect_hybrid_intent(parsed_goal)
        return build_goal_context(
            parsed_goal,
            intent=planner_intent,
            hybrid=hybrid,
            memory_snapshot=memory_snapshot,
        )

    def compose(
        self,
        goal_context,
        *,
        case_dir: str | Path,
        change: dict[str, Any] | Path | str,
        dry_run: bool,
        apply: bool,
        report_path: Path | None,
        change_path: Path | None,
        request_id: str,
        memory_snapshot: dict[str, Any],
        execution_strategy: str = "sequential",
    ) -> ExecutionPlan:
        request = build_planner_request(
            goal_context,
            case_dir=case_dir,
            change=change,
            dry_run=dry_run,
            apply=apply,
            report_path=report_path,
            change_path=change_path,
            request_id=request_id,
            memory_snapshot=memory_snapshot,
        )
        plan = compose_execution_plan(
            goal_context,
            request=request,
            execution_strategy=execution_strategy,  # type: ignore[arg-type]
        )
        plan.request = replace(
            request,
            metadata={**request.metadata, "execution_plan": plan.to_dict()},
        )
        return plan

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
        memory_snapshot: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        resolved_metadata = dict(metadata or {})
        snapshot = memory_snapshot or resolved_metadata.get("memory_snapshot", {})
        parsed_goal = parse_goal(
            case_dir=case_dir,
            change=change,
            metadata=resolved_metadata,
            intent=intent,
            goal=goal,
        )
        goal_context = self.analyze_goal(
            goal=goal,
            metadata=resolved_metadata,
            memory_snapshot=snapshot,
            parsed_goal=parsed_goal,
        )
        goal_context = self._apply_collaboration_consensus(goal_context, resolved_metadata)
        strategy = "sequential"
        consensus_data = resolved_metadata.get("collaboration_consensus")
        if isinstance(consensus_data, dict) and consensus_data.get("execution_strategy"):
            strategy = consensus_data["execution_strategy"]
        return self.compose(
            goal_context,
            case_dir=case_dir,
            change=change,
            dry_run=dry_run,
            apply=apply,
            report_path=Path(report_path) if report_path else None,
            change_path=Path(change_path) if change_path else None,
            request_id=request_id,
            memory_snapshot=snapshot,
            execution_strategy=strategy,
        )

    @staticmethod
    def _apply_collaboration_consensus(
        goal_context: GoalContext,
        metadata: dict[str, Any],
    ) -> GoalContext:
        consensus_data = metadata.get("collaboration_consensus")
        if not isinstance(consensus_data, dict):
            return goal_context
        from document_ai.platform.collaboration.consensus import ConsensusResult
        from document_ai.platform.collaboration.proposal import Proposal

        selected = {
            topic: Proposal(
                agent_id=value.get("agent_id", "unknown"),
                topic=topic,
                recommendation=value.get("recommendation", ""),
                confidence=float(value.get("confidence", 0.5)),
                rationale=value.get("rationale", ""),
                evidence=value.get("evidence", {}),
            )
            for topic, value in consensus_data.get("selected_proposals", {}).items()
        }
        consensus = ConsensusResult(
            consensus_id=consensus_data.get("consensus_id", "cons-restored"),
            intent=consensus_data.get("intent", goal_context.intent),  # type: ignore[arg-type]
            hybrid=bool(consensus_data.get("hybrid", goal_context.hybrid)),
            workflow_template=consensus_data.get(
                "workflow_template",
                goal_context.metadata.get("workflow_template", "document_workflow"),
            ),
            execution_strategy=consensus_data.get("execution_strategy", "sequential"),  # type: ignore[arg-type]
            confidence=float(consensus_data.get("confidence", 0.5)),
            selected_proposals=selected,
            review_status=consensus_data.get("review_status", "approved"),
            metadata=consensus_data.get("metadata", {}),
        )
        return apply_consensus_to_goal_context(goal_context, consensus)
