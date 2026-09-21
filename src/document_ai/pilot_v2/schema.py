# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — session, review item, and human review schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

SessionStatus = Literal[
    "CREATED",
    "UPLOADED",
    "IDENTITY_PENDING",
    "IDENTITY_RESOLVED",
    "ANALYZING",
    "ANALYZED",
    "REVIEW_IN_PROGRESS",
    "REVIEW_COMPLETE",
    "WRITER_BLOCKED",
    "WRITER_COMPLETED",
    "HUMAN_REVIEWED",
    "COMPLETED",
    "FAILED",
]

SESSION_STATUSES: tuple[str, ...] = (
    "CREATED",
    "UPLOADED",
    "IDENTITY_PENDING",
    "IDENTITY_RESOLVED",
    "ANALYZING",
    "ANALYZED",
    "REVIEW_IN_PROGRESS",
    "REVIEW_COMPLETE",
    "WRITER_BLOCKED",
    "WRITER_COMPLETED",
    "HUMAN_REVIEWED",
    "COMPLETED",
    "FAILED",
)

# Pilot-facing decision vocabulary (mapped internally onto workflow's
# PENDING/APPROVED/REJECTED/BLOCKED set — see orchestrator._map_decision).
ReviewDecision = Literal["PENDING", "APPROVE", "REJECT", "HOLD", "EDIT_PROPOSAL"]
REVIEW_DECISIONS: frozenset[str] = frozenset(
    {"PENDING", "APPROVE", "REJECT", "HOLD", "EDIT_PROPOSAL"}
)

HUMAN_REVIEW_SCORE_DIMENSIONS: tuple[str, ...] = (
    "understanding",
    "document_impact",
    "node_accuracy",
    "proposal_accuracy",
    "review_reason",
    "diff_readability",
    "no_unnecessary_change",
    "format_preservation",
    "trust",
    "usability",
)

HUMAN_REVIEW_VERDICTS: frozenset[str] = frozenset({"PASS", "PARTIAL", "FAIL", "PENDING"})


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ReviewItem:
    """Human-review card mapped from a workflow patch_candidate / review_required row."""

    item_id: str
    document_id: str
    kind: str  # PATCH_CANDIDATE | REVIEW_REQUIRED
    node_id: str | None = None
    display_name: str = ""
    reason_codes: list[str] = field(default_factory=list)
    reason_text_ko: str = ""
    evidence: list[str] = field(default_factory=list)
    decision: str = "PENDING"
    edited_text: str | None = None
    notes: str = ""
    decided_by: str | None = None
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HumanReviewRecord:
    """Post-session human review scoring (1-5 Likert per dimension)."""

    session_id: str
    participant_id: str
    scores: dict[str, int] = field(default_factory=dict)
    comments: str = ""
    verdict: str = "PENDING"
    submitted_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def average_score(self) -> float | None:
        vals = [v for v in self.scores.values() if isinstance(v, (int, float))]
        if not vals:
            return None
        return sum(vals) / len(vals)


@dataclass
class PilotSession:
    session_id: str
    participant_id: str
    document_set: str
    scenario_id: str | None = None
    status: str = "CREATED"
    change_request: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    documents: list[dict[str, Any]] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    workflow_ref: dict[str, Any] = field(default_factory=dict)
    review_items: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    writer_result: dict[str, Any] = field(default_factory=dict)
    human_review: dict[str, Any] | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def touch(self, status: str | None = None) -> None:
        if status:
            self.status = status
        self.updated_at = utc_now()

    def add_event(self, event: str, detail: str = "") -> None:
        self.timeline.append(
            {"at": utc_now(), "status": self.status, "event": event, "detail": detail}
        )
