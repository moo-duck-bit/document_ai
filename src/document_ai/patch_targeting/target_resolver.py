# -*- coding: utf-8 -*-
"""PR-22: Resolve logical patch targets (no physical locator)."""

from __future__ import annotations

from document_ai.patch_targeting.capability_gate import evaluate_capabilities
from document_ai.patch_targeting.schema import PatchIntent, PatchTargetCandidate
from document_ai.semantic_locator.schema import TemplateNodeCandidate


def resolve_patch_target(
    intent: PatchIntent,
    *,
    seq: int,
    node: TemplateNodeCandidate | None,
    match_status: str,
    combined_score: float,
    score_margin: float | None,
    ambiguity_status: str,
) -> PatchTargetCandidate:
    caps = evaluate_capabilities(
        intent.requested_operation,
        allowed_operations=list(node.allowed_operations) if node else [],
    )
    reasons = list(intent.reason_codes)
    for r in caps["reason_codes"]:
        if r not in reasons:
            reasons.append(r)

    if intent.intent_status == "INVALID":
        target_status = "INVALID"
    elif intent.intent_status == "BLOCKED":
        target_status = "UNRESOLVED"
    elif intent.intent_status == "REVIEW_REQUIRED":
        target_status = "REVIEW"
    elif intent.intent_status == "ELIGIBLE" and node is not None:
        target_status = "RESOLVED"
        if "TEMPLATE_NODE_RESOLVED" not in reasons:
            reasons.append("TEMPLATE_NODE_RESOLVED")
    elif intent.intent_status == "ELIGIBLE" and node is None:
        target_status = "UNRESOLVED"
        if "TEMPLATE_NODE_MISSING" not in reasons:
            reasons.append("TEMPLATE_NODE_MISSING")
    else:
        target_status = "UNRESOLVED"

    return PatchTargetCandidate(
        patch_target_candidate_id=f"PTC-{seq:04d}",
        patch_intent_id=intent.patch_intent_id,
        template_id=node.template_id if node else intent.template_id,
        template_node_id=node.template_node_id if node else intent.template_node_id,
        section_id=node.section_id if node else None,
        field_id=node.field_id if node else None,
        target_status=target_status,
        template_allowed=bool(caps["template_allowed"]),
        writer_supported=bool(caps["writer_supported"]),
        activation_allowed=bool(caps["activation_allowed"]),
        match_status=match_status,
        combined_score=combined_score,
        score_margin=score_margin,
        ambiguity_status=ambiguity_status,
        reason_codes=reasons,
        evidence={
            "logical_target_only": True,
            "physical_locator": None,
            "capability": {
                "template_allowed": caps["template_allowed"],
                "writer_supported": caps["writer_supported"],
                "activation_allowed": caps["activation_allowed"],
                "external_activation_flag": caps.get("external_activation_flag", False),
                "observational_gate_forced_off": caps.get(
                    "observational_gate_forced_off", True
                ),
            },
            "external_activation_flag": caps.get("external_activation_flag", False),
            "observational_gate_forced_off": caps.get(
                "observational_gate_forced_off", True
            ),
            "source_requirement_id": (
                node.source_requirement_id if node else None
            ),
        },
    )
