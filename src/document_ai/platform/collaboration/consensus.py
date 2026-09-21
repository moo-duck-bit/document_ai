from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from document_ai.platform.collaboration.discussion import Conflict, DiscussionResult
from document_ai.platform.collaboration.proposal import Proposal
from document_ai.platform.collaboration.voting import select_winning_proposal, vote_summary
from document_ai.platform.planning.intent_classifier import PlannerIntent
from document_ai.platform.planning.workflow_templates import select_workflow_template

ExecutionStrategy = Literal["sequential", "parallel"]


@dataclass
class ConsensusResult:
    consensus_id: str
    intent: PlannerIntent
    hybrid: bool
    workflow_template: str
    execution_strategy: ExecutionStrategy
    confidence: float
    selected_proposals: dict[str, Proposal]
    conflicts_resolved: list[Conflict] = field(default_factory=list)
    vote_summary: dict[str, Any] = field(default_factory=dict)
    review_status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "consensus_id": self.consensus_id,
            "intent": self.intent,
            "hybrid": self.hybrid,
            "workflow_template": self.workflow_template,
            "execution_strategy": self.execution_strategy,
            "confidence": self.confidence,
            "selected_proposals": {
                topic: proposal.to_dict() for topic, proposal in self.selected_proposals.items()
            },
            "conflicts_resolved": [conflict.to_dict() for conflict in self.conflicts_resolved],
            "vote_summary": self.vote_summary,
            "review_status": self.review_status,
            "metadata": self.metadata,
        }


def build_consensus(discussion: DiscussionResult) -> ConsensusResult:
    intent_proposal = select_winning_proposal(discussion.proposals, topic="intent")
    hybrid_proposal = select_winning_proposal(discussion.proposals, topic="hybrid")
    workflow_proposal = select_winning_proposal(discussion.proposals, topic="workflow")
    strategy_proposal = select_winning_proposal(discussion.proposals, topic="strategy")

    intent: PlannerIntent = (
        intent_proposal.recommendation if intent_proposal else "knowledge_query"  # type: ignore[assignment]
    )
    hybrid = hybrid_proposal.recommendation == "true" if hybrid_proposal else False
    workflow_template = workflow_proposal.recommendation if workflow_proposal else select_workflow_template(
        intent,
        hybrid=hybrid,
    ).template_id
    execution_strategy: ExecutionStrategy = (
        strategy_proposal.recommendation if strategy_proposal else "sequential"  # type: ignore[assignment]
    )

    if workflow_proposal is None:
        workflow_template = select_workflow_template(intent, hybrid=hybrid).template_id

    selected = {
        key: value
        for key, value in {
            "intent": intent_proposal,
            "hybrid": hybrid_proposal,
            "workflow": workflow_proposal,
            "strategy": strategy_proposal,
        }.items()
        if value is not None
    }

    confidences = [proposal.confidence for proposal in selected.values()]
    confidence = sum(confidences) / len(confidences) if confidences else 0.5

    return ConsensusResult(
        consensus_id=f"cons-{uuid.uuid4().hex[:12]}",
        intent=intent,
        hybrid=hybrid,
        workflow_template=workflow_template,
        execution_strategy=execution_strategy,
        confidence=confidence,
        selected_proposals=selected,  # type: ignore[arg-type]
        conflicts_resolved=list(discussion.conflicts),
        vote_summary={
            "intent": vote_summary(discussion.proposals, topic="intent"),
            "hybrid": vote_summary(discussion.proposals, topic="hybrid"),
            "workflow": vote_summary(discussion.proposals, topic="workflow"),
            "strategy": vote_summary(discussion.proposals, topic="strategy"),
        },
    )


def apply_consensus_to_goal_context(goal_context, consensus: ConsensusResult):
    from dataclasses import replace

    return replace(
        goal_context,
        intent=consensus.intent,
        hybrid=consensus.hybrid,
        metadata={
            **goal_context.metadata,
            "collaboration_consensus": consensus.to_dict(),
            "workflow_template": consensus.workflow_template,
            "execution_strategy": consensus.execution_strategy,
        },
    )
