# -*- coding: utf-8 -*-
"""PR-22 Generic Patch Targeting — package exports."""

from document_ai.patch_targeting.capability_gate import evaluate_capabilities
from document_ai.patch_targeting.eligibility import evaluate_eligibility
from document_ai.patch_targeting.intent_builder import build_patch_intent
from document_ai.patch_targeting.orchestrator import (
    run_patch_targeting_engine,
    sample_patch_targeting_inputs,
)
from document_ai.patch_targeting.preview import build_activation_preview
from document_ai.patch_targeting.schema import (
    ActivationPreview,
    PatchIntent,
    PatchTargetCandidate,
    PatchTargetingInput,
)
from document_ai.patch_targeting.target_resolver import resolve_patch_target
from document_ai.patch_targeting.validation import validate_patch_targeting

__all__ = [
    "PatchTargetingInput",
    "PatchIntent",
    "PatchTargetCandidate",
    "ActivationPreview",
    "evaluate_eligibility",
    "evaluate_capabilities",
    "build_patch_intent",
    "resolve_patch_target",
    "build_activation_preview",
    "validate_patch_targeting",
    "sample_patch_targeting_inputs",
    "run_patch_targeting_engine",
]
