# -*- coding: utf-8 -*-
"""Writer evaluation metrics."""

from __future__ import annotations

from typing import Any


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def compute_writer_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Each row: gold + pred writer expectation."""
    n = len(rows) or 1
    attempts = sum(1 for r in rows if r.get("pred_attempted"))
    apply_ok = sum(1 for r in rows if r.get("gold_should_write") and r.get("pred_applied"))
    block_ok = sum(
        1
        for r in rows
        if (not r.get("gold_should_write")) and (not r.get("pred_applied")) and r.get("pred_blocked", True)
    )
    orig_ok = sum(1 for r in rows if r.get("original_unchanged", True))
    unauthorized = sum(1 for r in rows if r.get("unauthorized_write"))
    rollback_ok = sum(1 for r in rows if r.get("rollback_ok", True))
    return {
        "writer_attempt_rate": _safe_div(attempts, n),
        "apply_success_rate": _safe_div(apply_ok, sum(1 for r in rows if r.get("gold_should_write")) or 1),
        "block_correctness": _safe_div(block_ok, sum(1 for r in rows if not r.get("gold_should_write")) or 1),
        "original_preservation_rate": _safe_div(orig_ok, n),
        "rollback_success_rate": _safe_div(rollback_ok, n),
        "unauthorized_write_rate": _safe_div(unauthorized, n),
        "n": len(rows),
    }
