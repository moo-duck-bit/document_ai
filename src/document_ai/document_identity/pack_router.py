# -*- coding: utf-8 -*-
"""Domain pack routing from identity decisions."""

from __future__ import annotations

import hashlib
from typing import Any

from document_ai.document_identity.schema import (
    DocumentIdentityCandidate,
    DocumentIdentityDecision,
    DomainPackRoutingDecision,
)

# Map workflow document_set ids ↔ pack ids
PACK_TO_DOCUMENT_SET = {
    "ec_sw_v1": "ec_sw",
    "generic_document_v1": "general_report",  # disambiguated by template
}
DOCUMENT_SET_TO_PACK = {
    "ec_sw": "ec_sw_v1",
    "general_report": "generic_document_v1",
    "business_proposal": "generic_document_v1",
}


def _rid(source_id: str, pack: str | None) -> str:
    h = hashlib.sha1(f"route:{source_id}:{pack or ''}".encode("utf-8")).hexdigest()[:10]
    return f"route_{h}"


def route_domain_pack(
    *,
    identity: DocumentIdentityDecision,
    candidates: list[DocumentIdentityCandidate],
    routing_mode: str = "assisted",
    explicit_document_set: str | None = None,
    user_confirmed: bool = False,
) -> DomainPackRoutingDecision:
    """Route to a domain pack. Never invokes wrong pack for writer (caller enforces)."""
    mode = (routing_mode or "assisted").lower()
    pack_scores: dict[str, float] = {}
    for c in candidates:
        if not c.domain_pack_id:
            continue
        pack_scores[c.domain_pack_id] = max(pack_scores.get(c.domain_pack_id, 0.0), c.score)
    ordered = sorted(pack_scores.items(), key=lambda x: (-x[1], x[0]))
    candidate_packs = [p for p, _ in ordered]
    top_pack = ordered[0][0] if ordered else identity.domain_pack_id
    top_score = ordered[0][1] if ordered else identity.top_score
    second = ordered[1][1] if len(ordered) > 1 else 0.0
    margin = top_score - second

    reasons: list[str] = list(identity.reason_codes[:6])
    status = "UNRESOLVED"
    selected: str | None = None
    review = True
    actual_invoked: str | None = None

    if mode == "explicit" and explicit_document_set:
        selected = DOCUMENT_SET_TO_PACK.get(explicit_document_set, explicit_document_set)
        # Conflict with content → review/block
        if identity.decision_status == "REVIEW_REQUIRED" and "USER_HINT_CONTENT_CONFLICT" in identity.reason_codes:
            status = "REVIEW_REQUIRED"
            reasons.append("explicit_content_conflict")
            selected = None
        elif identity.domain_pack_id and identity.domain_pack_id != selected and identity.auto_selected is False:
            if identity.top_score >= 40 and identity.domain_pack_id != selected:
                status = "REVIEW_REQUIRED"
                reasons.append("explicit_pack_content_mismatch")
                selected = None
            else:
                status = "ROUTED"
                review = False
                actual_invoked = selected
                reasons.append("explicit_user_pack")
        else:
            status = "ROUTED"
            review = False
            actual_invoked = selected
            reasons.append("explicit_user_pack")
    elif mode == "auto":
        if identity.auto_selected and identity.domain_pack_id and identity.decision_status == "AUTO_SELECTED":
            selected = identity.domain_pack_id
            status = "ROUTED"
            review = False
            actual_invoked = selected
            reasons.append("auto_route_from_identity")
        else:
            status = "REVIEW_REQUIRED"
            selected = top_pack
            reasons.append("auto_mode_insufficient_evidence")
    else:  # assisted
        selected = identity.domain_pack_id or top_pack
        if user_confirmed and selected:
            status = "ROUTED"
            review = False
            actual_invoked = selected
            reasons.append("assisted_user_confirmed")
        elif identity.auto_selected and selected:
            # Still require confirmation in assisted unless confirmed
            status = "REVIEW_REQUIRED"
            reasons.append("assisted_recommendation_pending_confirm")
        else:
            status = "REVIEW_REQUIRED"
            reasons.append("assisted_review_required")

    if identity.decision_status == "INVALID":
        status = "INVALID"
        selected = None
        actual_invoked = None

    return DomainPackRoutingDecision(
        routing_id=_rid(identity.source_document_id, selected),
        source_document_id=identity.source_document_id,
        selected_pack_id=selected,
        candidate_pack_ids=candidate_packs[:5],
        routing_status=status,  # type: ignore[arg-type]
        score=round(top_score, 3),
        score_margin=round(margin, 3),
        reason_codes=list(dict.fromkeys(reasons))[:16],
        human_review_required=review,
        actual_pack_invoked=actual_invoked,
        metadata={
            "routing_mode": mode,
            "identity_status": identity.decision_status,
            "document_set_hint": pack_to_document_set(selected, identity.template_id),
        },
    )


def pack_to_document_set(pack_id: str | None, template_id: str | None = None) -> str | None:
    if not pack_id:
        return None
    if pack_id == "ec_sw_v1":
        return "ec_sw"
    if pack_id == "generic_document_v1":
        if template_id and "proposal" in template_id:
            return "business_proposal"
        if template_id and "report" in template_id:
            return "general_report"
        return "general_report"
    return PACK_TO_DOCUMENT_SET.get(pack_id)


def document_set_for_identity(identity: DocumentIdentityDecision) -> str | None:
    return pack_to_document_set(identity.domain_pack_id, identity.template_id)
