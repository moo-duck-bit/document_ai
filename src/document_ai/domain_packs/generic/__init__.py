# -*- coding: utf-8 -*-
"""Generic domain pack helpers."""

from document_ai.domain_packs.generic.no_impact_policy import NoImpactDecision, decide_no_impact
from document_ai.domain_packs.generic.target_existence import (
    TargetExistenceDecision,
    decide_target_existence,
)

__all__ = [
    "NoImpactDecision",
    "TargetExistenceDecision",
    "decide_no_impact",
    "decide_target_existence",
]
