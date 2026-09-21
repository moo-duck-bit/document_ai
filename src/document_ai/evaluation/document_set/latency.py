# -*- coding: utf-8 -*-
"""Latency aggregation helpers."""

from __future__ import annotations

import statistics
from typing import Any


def summarize_latencies(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0, "min": 0.0, "stdev": 0.0, "n": 0}
    xs = sorted(float(v) for v in values)
    n = len(xs)
    p95_idx = min(n - 1, max(0, int(0.95 * (n - 1))))
    return {
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "p95": xs[p95_idx],
        "max": xs[-1],
        "min": xs[0],
        "stdev": statistics.pstdev(xs) if n > 1 else 0.0,
        "n": n,
    }


def validate_non_negative(latency: dict[str, Any]) -> list[str]:
    issues = []
    for k, v in latency.items():
        if isinstance(v, (int, float)) and v < 0:
            issues.append(f"negative_latency:{k}")
    return issues
