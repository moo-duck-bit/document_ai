# -*- coding: utf-8 -*-
"""EC-SW node ranking configuration (thresholds only — no case IDs)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RankingConfig:
    tier0_base: float = 120.0
    tier1_base: float = 100.0
    tier2_base: float = 80.0
    tier3_base: float = 60.0
    tier4_base: float = 30.0
    tier5_base: float = 10.0
    tier6_base: float = 5.0
    primary_exact_bonus: float = 20.0
    secondary_exact_bonus: float = 8.0
    normalized_bonus: float = 4.0
    stable_base_bonus: float = 15.0
    instance_match_bonus: float = 10.0
    row_local_semantic_weight: float = 5.0
    context_support_weight: float = 1.0
    neighbor_penalty: float = 15.0
    duplicate_penalty: float = 2.0
    ambiguity_penalty: float = 3.0
    inherited_discount: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_RANKING_CONFIG = RankingConfig()
