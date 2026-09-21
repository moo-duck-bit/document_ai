# -*- coding: utf-8 -*-
"""PR-22: Build observational PatchIntent."""

from __future__ import annotations

from document_ai.patch_targeting.eligibility import evaluate_eligibility
from document_ai.patch_targeting.schema import PatchIntent, PatchTargetingInput
from document_ai.semantic_locator.schema import TemplateNodeCandidate


def build_patch_intent(
    inp: PatchTargetingInput,
    *,
    seq: int,
    node: TemplateNodeCandidate | None,
) -> PatchIntent:
    node_exists = node is not None
    allowed = list(node.allowed_operations) if node else []
    status, reasons, evidence = evaluate_eligibility(
        inp,
        node_allowed_operations=allowed,
        node_exists=node_exists,
        node_template_id=node.template_id if node else None,
    )
    evidence = dict(evidence)
    evidence["match_reason_codes"] = list(inp.match_reason_codes or [])
    evidence["match_evidence"] = dict(inp.match_evidence or {})
    if node and node.source_requirement_id is None:
        evidence["source_requirement_id"] = None
        evidence["generic_requirement_id_optional"] = True

    return PatchIntent(
        patch_intent_id=f"PI-{seq:04d}",
        change_id=inp.change_id,
        document_id=inp.document_id,
        semantic_match_id=inp.semantic_match_id,
        template_id=inp.template_id,
        template_node_id=inp.template_node_id if node_exists else inp.template_node_id,
        requested_operation=str(inp.requested_operation or "").upper(),
        intent_status=status,
        reason_codes=reasons,
        source_text=inp.source_text,
        proposed_text=inp.proposed_text,
        evidence=evidence,
        actual_patch_created=False,
        actual_document_changed=False,
    )
