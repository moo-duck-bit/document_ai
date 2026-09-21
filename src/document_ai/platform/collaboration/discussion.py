from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from document_ai.platform.collaboration.proposal import Proposal


@dataclass
class Conflict:
    topic: str
    agents: list[str]
    recommendations: list[str]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "agents": self.agents,
            "recommendations": self.recommendations,
            "description": self.description,
        }


@dataclass
class DiscussionResult:
    proposals: list[Proposal]
    conflicts: list[Conflict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "notes": self.notes,
        }


def discuss_proposals(proposals: list[Proposal]) -> DiscussionResult:
    conflicts: list[Conflict] = []
    notes: list[str] = []
    grouped: dict[str, list[Proposal]] = {}

    for proposal in proposals:
        grouped.setdefault(proposal.topic, []).append(proposal)

    for topic, topic_proposals in grouped.items():
        recommendations = {proposal.recommendation for proposal in topic_proposals}
        if len(recommendations) <= 1:
            notes.append(f"No conflict on topic '{topic}'.")
            continue

        agents = [proposal.agent_id for proposal in topic_proposals]
        recs = sorted(recommendations)
        conflicts.append(
            Conflict(
                topic=topic,
                agents=agents,
                recommendations=recs,
                description=f"Agents disagree on {topic}: {', '.join(recs)}",
            )
        )
        notes.append(f"Conflict detected on topic '{topic}' among {', '.join(agents)}.")

    return DiscussionResult(proposals=proposals, conflicts=conflicts, notes=notes)
