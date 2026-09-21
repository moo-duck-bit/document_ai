# -*- coding: utf-8 -*-
"""Identity / routing thresholds (no case IDs)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IdentityThresholds:
    auto_min_score: float = 55.0
    auto_min_margin: float = 12.0
    auto_max_tier: int = 2  # TIER_1 or TIER_2 only for AUTO
    strong_candidate_score: float = 40.0
    filename_only_max_tier: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_THRESHOLDS = IdentityThresholds()
