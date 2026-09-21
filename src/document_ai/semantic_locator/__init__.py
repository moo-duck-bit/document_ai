# -*- coding: utf-8 -*-
"""PR-21 Generic Template Semantic Locator Engine — package exports."""

from document_ai.semantic_locator.locator import (
    load_generic_node_candidates,
    run_semantic_locator_engine,
    sample_locator_inputs,
)
from document_ai.semantic_locator.ranking import build_match_results, score_all_nodes
from document_ai.semantic_locator.rule_matcher import compute_rule_score
from document_ai.semantic_locator.schema import (
    SemanticLocatorInput,
    SemanticMatchResult,
    TemplateNodeCandidate,
)
from document_ai.semantic_locator.score_fusion import fuse_scores
from document_ai.semantic_locator.semantic_matcher import compute_semantic_score
from document_ai.semantic_locator.text_normalization import normalize_text, tokenize
from document_ai.semantic_locator.thresholds import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    GENERIC_TEMPLATE_IDS,
)
from document_ai.semantic_locator.validation import validate_semantic_locator

__all__ = [
    "SemanticLocatorInput",
    "SemanticMatchResult",
    "TemplateNodeCandidate",
    "normalize_text",
    "tokenize",
    "compute_rule_score",
    "compute_semantic_score",
    "fuse_scores",
    "score_all_nodes",
    "build_match_results",
    "validate_semantic_locator",
    "load_generic_node_candidates",
    "sample_locator_inputs",
    "run_semantic_locator_engine",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_WEIGHTS",
    "GENERIC_TEMPLATE_IDS",
]
