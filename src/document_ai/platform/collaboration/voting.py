from __future__ import annotations

from collections import defaultdict
from typing import Any

from document_ai.platform.collaboration.proposal import Proposal

AGENT_WEIGHTS = {
    "planning_agent": 1.5,
    "requirement_agent": 1.2,
    "design_agent": 1.0,
    "security_agent": 1.0,
    "operation_agent": 1.1,
    "review_agent": 0.5,
}


def score_proposals(proposals: list[Proposal], *, topic: str) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for proposal in proposals:
        if proposal.topic != topic:
            continue
        weight = AGENT_WEIGHTS.get(proposal.agent_id, 1.0)
        scores[proposal.recommendation] += proposal.confidence * weight
    return dict(scores)


def select_winning_proposal(
    proposals: list[Proposal],
    *,
    topic: str,
) -> Proposal | None:
    topic_proposals = [proposal for proposal in proposals if proposal.topic == topic]
    if not topic_proposals:
        return None

    scores = score_proposals(topic_proposals, topic=topic)
    if not scores:
        return topic_proposals[0]

    winning_recommendation = max(scores, key=scores.get)
    candidates = [p for p in topic_proposals if p.recommendation == winning_recommendation]
    return max(candidates, key=lambda proposal: proposal.confidence)


def vote_summary(proposals: list[Proposal], *, topic: str) -> dict[str, Any]:
    scores = score_proposals(proposals, topic=topic)
    winner = select_winning_proposal(proposals, topic=topic)
    return {
        "topic": topic,
        "scores": scores,
        "winner": winner.to_dict() if winner else None,
    }
