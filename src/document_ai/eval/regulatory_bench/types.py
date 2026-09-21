"""Shared types and constants for Small-A regulatory_bench."""

from __future__ import annotations

from typing import Any, TypedDict

MU_KEYS = (
    "false_patch",
    "unsafe_write",
    "original_broken",
    "unapproved_write",
)

# Ablation B must be labeled honestly in reports (sandbox counterfactuals).
ABLATION_MU_MAP = {
    "no_gate": ("unapproved_write", "unsafe_write"),
    "no_copy_only": ("original_broken",),
    "no_closure": ("false_patch",),
}


class MuDict(TypedDict):
    false_patch: int
    unsafe_write: int
    original_broken: int
    unapproved_write: int


def zero_mu() -> MuDict:
    return {
        "false_patch": 0,
        "unsafe_write": 0,
        "original_broken": 0,
        "unapproved_write": 0,
    }


# Alias used by some call sites.
empty_mu = zero_mu


def mu_is_zero(mu: dict[str, Any]) -> bool:
    return all(int(mu.get(k, 0) or 0) == 0 for k in MU_KEYS)
