from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from document_ai.platform.collaboration.consensus import ConsensusResult, build_consensus
from document_ai.platform.collaboration.discussion import DiscussionResult, discuss_proposals
from document_ai.platform.collaboration.proposal import Proposal
from document_ai.platform.collaboration.review_cycle import run_review_cycle
from document_ai.platform.improvement.execution_feedback import ExecutionFeedback
from document_ai.platform.improvement.improvement_engine import ImprovementEngine
from document_ai.platform.planning.goal_parser import ParsedGoal
from document_ai.platform.planning.intent_classifier import (
    PlannerIntent,
    classify_intent,
    detect_document_change_intent,
    detect_hybrid_intent,
    detect_operation_intent,
)
from document_ai.platform.planning.workflow_templates import select_workflow_template

AGENT_IDS = (
    "planning_agent",
    "requirement_agent",
    "design_agent",
    "security_agent",
    "operation_agent",
)


@dataclass
class CollaborationResult:
    proposals: list[Proposal]
    discussion: DiscussionResult
    consensus: ConsensusResult
    review_approved: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "discussion": self.discussion.to_dict(),
            "consensus": self.consensus.to_dict(),
            "review_approved": self.review_approved,
        }


class CollaborationManager:
    """Multi-agent collaboration layer before ExecutionPlan creation."""

    def __init__(self, improvement_engine: ImprovementEngine | None = None) -> None:
        self.improvement_engine = improvement_engine or ImprovementEngine()

    def collaborate(
        self,
        *,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
        case_dir: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
        execution_feedback: ExecutionFeedback | None = None,
    ) -> ConsensusResult:
        feedback = execution_feedback
        if feedback is None and case_dir is not None:
            feedback = self.improvement_engine.analyze_snapshot(
                memory_snapshot,
                case_dir=case_dir,
                correlation_id=(metadata or {}).get("correlation_id"),
            )

        proposals = self.collect_proposals(
            parsed_goal,
            memory_snapshot=memory_snapshot,
            execution_feedback=feedback,
        )
        discussion = discuss_proposals(proposals)
        consensus = build_consensus(discussion)
        review = run_review_cycle(consensus, discussion)
        consensus.review_status = "approved" if review.approved else "needs_revision"
        consensus.metadata = {
            "review_findings": [finding.to_dict() for finding in review.findings],
            "agent_count": len({proposal.agent_id for proposal in proposals}),
            "conflict_count": len(discussion.conflicts),
        }
        return consensus

    def run_full_cycle(
        self,
        *,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
        case_dir: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CollaborationResult:
        feedback = None
        if case_dir is not None:
            feedback = self.improvement_engine.analyze_snapshot(
                memory_snapshot,
                case_dir=case_dir,
                correlation_id=(metadata or {}).get("correlation_id"),
            )
        proposals = self.collect_proposals(
            parsed_goal,
            memory_snapshot=memory_snapshot,
            execution_feedback=feedback,
        )
        discussion = discuss_proposals(proposals)
        consensus = build_consensus(discussion)
        review = run_review_cycle(consensus, discussion)
        consensus.review_status = "approved" if review.approved else "needs_revision"
        consensus.metadata = {
            "review_findings": [finding.to_dict() for finding in review.findings],
            "agent_count": len({proposal.agent_id for proposal in proposals}),
            "conflict_count": len(discussion.conflicts),
        }
        return CollaborationResult(
            proposals=proposals,
            discussion=discussion,
            consensus=consensus,
            review_approved=review.approved,
        )

    def collect_proposals(
        self,
        parsed_goal: ParsedGoal,
        *,
        memory_snapshot: dict[str, Any],
        execution_feedback: ExecutionFeedback | None = None,
    ) -> list[Proposal]:
        proposals: list[Proposal] = []
        proposals.extend(self._planning_agent_proposals(parsed_goal, memory_snapshot, execution_feedback))
        proposals.extend(self._requirement_agent_proposals(parsed_goal, memory_snapshot))
        proposals.extend(self._design_agent_proposals(parsed_goal, memory_snapshot))
        proposals.extend(self._security_agent_proposals(parsed_goal, memory_snapshot))
        proposals.extend(self._operation_agent_proposals(parsed_goal, memory_snapshot))
        return proposals

    def _planning_agent_proposals(
        self,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
        execution_feedback: ExecutionFeedback | None,
    ) -> list[Proposal]:
        intent = classify_intent(parsed_goal)
        hybrid = detect_hybrid_intent(parsed_goal)
        template = select_workflow_template(intent, hybrid=hybrid)
        strategy = "sequential"
        if execution_feedback:
            for recommendation in execution_feedback.strategy_recommendations:
                candidate = recommendation.metadata.get("execution_strategy")
                if candidate in {"sequential", "parallel"}:
                    strategy = candidate
                    break

        evidence = {
            "classified_intent": intent,
            "hybrid_detected": hybrid,
            "template_id": template.template_id,
            "goal_text": parsed_goal.combined_text[:200],
        }
        if execution_feedback:
            evidence["improvement_feedback"] = execution_feedback.memory_summary

        return [
            Proposal(
                agent_id="planning_agent",
                topic="intent",
                recommendation=intent,
                confidence=0.92,
                rationale="Planning agent classified goal intent from parser and memory context",
                evidence=evidence,
            ),
            Proposal(
                agent_id="planning_agent",
                topic="hybrid",
                recommendation="true" if hybrid else "false",
                confidence=0.9,
                rationale="Planning agent evaluated document and operation signals",
                evidence={"hybrid_detected": hybrid},
            ),
            Proposal(
                agent_id="planning_agent",
                topic="workflow",
                recommendation=template.template_id,
                confidence=0.9,
                rationale="Planning agent selected workflow template for intent",
                evidence={"template_id": template.template_id},
            ),
            Proposal(
                agent_id="planning_agent",
                topic="strategy",
                recommendation=strategy,
                confidence=0.85,
                rationale="Planning agent chose execution strategy from failure history",
                evidence={"strategy": strategy},
            ),
        ]

    def _requirement_agent_proposals(
        self,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
    ) -> list[Proposal]:
        has_requirement_signal = detect_document_change_intent(parsed_goal)
        knowledge = memory_snapshot.get("knowledge", {})
        req_count = 0
        if knowledge.get("available"):
            req_count = knowledge.get("payload", {}).get("node_count", 0)

        intent: PlannerIntent = "document_change" if has_requirement_signal else "knowledge_query"
        return [
            Proposal(
                agent_id="requirement_agent",
                topic="intent",
                recommendation=intent,
                confidence=0.86 if has_requirement_signal else 0.55,
                rationale="Requirement agent checked change path and requirement keywords",
                evidence={
                    "has_requirement_signal": has_requirement_signal,
                    "knowledge_nodes": req_count,
                },
            ),
            Proposal(
                agent_id="requirement_agent",
                topic="hybrid",
                recommendation="false",
                confidence=0.7,
                rationale="Requirement agent prioritizes document traceability path",
                evidence={"focus": "requirements"},
            ),
        ]

    def _design_agent_proposals(
        self,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
    ) -> list[Proposal]:
        text = parsed_goal.combined_text.lower()
        design_signal = any(token in text for token in ("design", "mddr", "설계", "traceability"))
        intent: PlannerIntent = "document_change" if design_signal else classify_intent(parsed_goal)
        return [
            Proposal(
                agent_id="design_agent",
                topic="intent",
                recommendation=intent,
                confidence=0.78 if design_signal else 0.6,
                rationale="Design agent evaluated design and traceability relevance",
                evidence={"design_signal": design_signal},
            ),
            Proposal(
                agent_id="design_agent",
                topic="workflow",
                recommendation="document_workflow",
                confidence=0.75,
                rationale="Design agent prefers document workflow for design artifacts",
                evidence={"workflow": "document_workflow"},
            ),
        ]

    def _security_agent_proposals(
        self,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
    ) -> list[Proposal]:
        text = parsed_goal.combined_text
        security_signal = any(
            token in text.lower() for token in ("security", "xxcs", "ia-", "si-", "보안", "취약")
        )
        intent: PlannerIntent = "security_review" if security_signal else classify_intent(parsed_goal)
        return [
            Proposal(
                agent_id="security_agent",
                topic="intent",
                recommendation=intent,
                confidence=0.82 if security_signal else 0.58,
                rationale="Security agent scanned for XXCS and security verification signals",
                evidence={"security_signal": security_signal},
            ),
        ]

    def _operation_agent_proposals(
        self,
        parsed_goal: ParsedGoal,
        memory_snapshot: dict[str, Any],
    ) -> list[Proposal]:
        ops_signal = detect_operation_intent(parsed_goal.combined_text)
        hybrid = detect_hybrid_intent(parsed_goal)
        intent: PlannerIntent = "operation_analysis" if ops_signal and not hybrid else classify_intent(parsed_goal)
        workflow = (
            "hybrid_workflow"
            if hybrid
            else "operation_workflow"
            if intent == "operation_analysis"
            else select_workflow_template(intent, hybrid=False).template_id
        )
        return [
            Proposal(
                agent_id="operation_agent",
                topic="intent",
                recommendation=intent,
                confidence=0.84 if ops_signal else 0.5,
                rationale="Operation agent evaluated GPU/Docker/log incident signals",
                evidence={"operation_signal": ops_signal},
            ),
            Proposal(
                agent_id="operation_agent",
                topic="hybrid",
                recommendation="true" if hybrid else "false",
                confidence=0.88 if hybrid else 0.6,
                rationale="Operation agent recommends hybrid when ops follows document change",
                evidence={"hybrid_detected": hybrid},
            ),
            Proposal(
                agent_id="operation_agent",
                topic="workflow",
                recommendation=workflow,
                confidence=0.83 if ops_signal else 0.55,
                rationale="Operation agent proposed workflow based on incident analysis need",
                evidence={"workflow": workflow},
            ),
        ]
