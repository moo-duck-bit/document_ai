from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Proposal:
    agent_id: str
    recommendation: str
    confidence: float
    rationale: str
    evidence: dict[str, Any] = field(default_factory=dict)
    topic: str = "workflow"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "topic": self.topic,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence": self.evidence,
        }


def new_proposal_id() -> str:
    return f"prop-{uuid.uuid4().hex[:12]}"
