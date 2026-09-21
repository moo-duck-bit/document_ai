# -*- coding: utf-8 -*-
"""PR-21: Score thresholds and fusion weights (constants)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    rule_weight: float = 0.65
    semantic_weight: float = 0.35


@dataclass(frozen=True)
class MatchThresholds:
    matched_min: float = 0.80
    review_min: float = 0.55
    score_margin_min: float = 0.08
    round_digits: int = 4


DEFAULT_WEIGHTS = ScoreWeights()
DEFAULT_THRESHOLDS = MatchThresholds()

GENERIC_TEMPLATE_IDS = frozenset({"general_report_v1", "business_proposal_v1"})
