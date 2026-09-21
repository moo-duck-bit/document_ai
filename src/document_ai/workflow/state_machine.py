# -*- coding: utf-8 -*-
"""Explicit workflow state transition policy."""

from __future__ import annotations

from typing import Any

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "CREATED": frozenset({"UPLOADED", "FAILED"}),
    "UPLOADED": frozenset({"ANALYZING", "FAILED"}),
    "ANALYZING": frozenset({"REVIEW_READY", "FAILED"}),
    "REVIEW_READY": frozenset({"WAITING_APPROVAL", "FAILED"}),
    "WAITING_APPROVAL": frozenset({"WRITING", "WAITING_APPROVAL", "FAILED"}),
    "WRITING": frozenset({"VALIDATING", "FAILED"}),
    "VALIDATING": frozenset({"COMPLETED", "FAILED"}),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
}

TERMINAL_STATES = frozenset({"COMPLETED", "FAILED"})

# Operations that mutate workflow state
MUTATING_OPS = frozenset({"analyze", "approve", "write", "complete"})


class WorkflowStateError(ValueError):
    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}")


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def can_transition(from_state: str, to_state: str) -> bool:
    if from_state == to_state and from_state == "WAITING_APPROVAL":
        return True  # approval updates stay in waiting
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


def assert_transition(from_state: str, to_state: str) -> None:
    if is_terminal(from_state):
        raise WorkflowStateError(
            "TERMINAL_STATE_IMMUTABLE",
            f"cannot leave terminal state {from_state} → {to_state}",
        )
    if not can_transition(from_state, to_state):
        raise WorkflowStateError(
            "INVALID_STATE_TRANSITION",
            f"transition not allowed: {from_state} → {to_state}",
        )


def assert_can_analyze(state: str) -> None:
    if is_terminal(state):
        raise WorkflowStateError("TERMINAL_STATE_IMMUTABLE", f"analyze blocked in {state}")
    if state != "UPLOADED":
        raise WorkflowStateError(
            "ANALYSIS_NOT_COMPLETED"
            if state in {"CREATED"}
            else "INVALID_STATE_TRANSITION",
            f"analyze requires UPLOADED, got {state}",
        )


def assert_can_approve(state: str) -> None:
    if is_terminal(state):
        raise WorkflowStateError("TERMINAL_STATE_IMMUTABLE", f"approve blocked in {state}")
    if state not in {"REVIEW_READY", "WAITING_APPROVAL"}:
        raise WorkflowStateError(
            "APPROVAL_NOT_READY",
            f"approve requires REVIEW_READY|WAITING_APPROVAL, got {state}",
        )


def assert_can_write(state: str) -> None:
    if is_terminal(state):
        raise WorkflowStateError("TERMINAL_STATE_IMMUTABLE", f"writer blocked in {state}")
    if state != "WAITING_APPROVAL":
        raise WorkflowStateError(
            "WRITER_NOT_READY",
            f"writer requires WAITING_APPROVAL, got {state}",
        )


def transition_record(record: Any, to_state: str, *, event: str = "", detail: str = "") -> None:
    assert_transition(record.state, to_state)
    record.touch(to_state)
    if event:
        record.add_event(event, detail)
