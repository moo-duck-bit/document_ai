"""Document-TNR safety contract (non-regression for document agents)."""

from document_ai.safety.document_tnr import (
    DocumentTNRSpec,
    assess_scorecard,
    assess_severity,
    baseline_from_session,
    baseline_ok_from_scorecard,
    counterfactual_mu_for_variant,
    document_tnr_definition,
    map_safety_scorecard_to_mu,
    mu_pilot_key_alignment,
)

__all__ = [
    "DocumentTNRSpec",
    "assess_scorecard",
    "assess_severity",
    "baseline_from_session",
    "baseline_ok_from_scorecard",
    "counterfactual_mu_for_variant",
    "document_tnr_definition",
    "map_safety_scorecard_to_mu",
    "mu_pilot_key_alignment",
]
