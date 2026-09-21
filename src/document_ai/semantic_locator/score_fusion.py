# -*- coding: utf-8 -*-
"""PR-21: Score fusion."""

from __future__ import annotations

from document_ai.semantic_locator.thresholds import DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS, ScoreWeights


def fuse_scores(
    rule_score: float,
    semantic_score: float,
    *,
    weights: ScoreWeights | None = None,
) -> float:
    w = weights or DEFAULT_WEIGHTS
    combined = rule_score * w.rule_weight + semantic_score * w.semantic_weight
    return round(min(max(combined, 0.0), 1.0), DEFAULT_THRESHOLDS.round_digits)
