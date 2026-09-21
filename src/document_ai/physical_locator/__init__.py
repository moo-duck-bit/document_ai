# -*- coding: utf-8 -*-
"""PR-23 Generic Physical Locator — package exports."""

from document_ai.physical_locator.candidate_builder import build_physical_candidates
from document_ai.physical_locator.locator_engine import locate_physical_target
from document_ai.physical_locator.orchestrator import (
    run_physical_locator_engine,
    sample_physical_locator_inputs,
)
from document_ai.physical_locator.ranking import decide_location_status, rank_candidates
from document_ai.physical_locator.schema import (
    PhysicalLocatorInput,
    PhysicalLocationCandidate,
    PrimaryPhysicalLocation,
)
from document_ai.physical_locator.validation import validate_physical_locator

__all__ = [
    "PhysicalLocatorInput",
    "PhysicalLocationCandidate",
    "PrimaryPhysicalLocation",
    "build_physical_candidates",
    "rank_candidates",
    "decide_location_status",
    "locate_physical_target",
    "validate_physical_locator",
    "sample_physical_locator_inputs",
    "run_physical_locator_engine",
]
