from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from document_ai.platform.collaboration.consensus import ConsensusResult
from document_ai.platform.collaboration.discussion import DiscussionResult
from document_ai.platform.collaboration.proposal import Proposal

MIN_CONFIDENCE = 0.45
MIN_EVIDENCE_KEYS = 1


@dataclass
class ReviewFinding:
    severity: str
    category: str
    message: str
    agent_id: str = "review_agent"

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "agent_id": self.agent_id,
        }


@dataclass
class ReviewResult:
    approved: bool
    findings: list[ReviewFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def run_review_cycle(
    consensus: ConsensusResult,
    discussion: DiscussionResult,
) -> ReviewResult:
    findings: list[ReviewFinding] = []

    for conflict in discussion.conflicts:
        findings.append(
            ReviewFinding(
                severity="warning",
                category="conflict",
                message=conflict.description,
            )
        )

    for topic, proposal in consensus.selected_proposals.items():
        if proposal.confidence < MIN_CONFIDENCE:
            findings.append(
                ReviewFinding(
                    severity="warning",
                    category="low_confidence",
                    message=f"Low confidence on {topic} from {proposal.agent_id}",
                )
            )
        if len(proposal.evidence) < MIN_EVIDENCE_KEYS:
            findings.append(
                ReviewFinding(
                    severity="info",
                    category="insufficient_evidence",
                    message=f"Limited evidence provided for {topic} by {proposal.agent_id}",
                )
            )

    if consensus.hybrid and consensus.intent != "document_change":
        findings.append(
            ReviewFinding(
                severity="error",
                category="risk",
                message="Hybrid workflow requested with non-document primary intent",
            )
        )

    if consensus.execution_strategy == "parallel" and consensus.hybrid:
        findings.append(
            ReviewFinding(
                severity="warning",
                category="risk",
                message="Parallel execution with hybrid workflow may skip dependency guarantees",
            )
        )

    has_blocking = any(finding.severity == "error" for finding in findings)
    approved = not has_blocking
    return ReviewResult(approved=approved, findings=findings)


def review_agent_proposal(
    consensus: ConsensusResult,
    discussion: DiscussionResult,
) -> Proposal:
    review = run_review_cycle(consensus, discussion)
    recommendation = "approve" if review.approved else "revise"
    confidence = 0.9 if review.approved else 0.55
    return Proposal(
        agent_id="review_agent",
        topic="review",
        recommendation=recommendation,
        confidence=confidence,
        rationale="Review agent evaluated conflicts, evidence, and execution risks",
        evidence={
            "approved": review.approved,
            "finding_count": len(review.findings),
            "findings": [finding.to_dict() for finding in review.findings],
        },
    )
