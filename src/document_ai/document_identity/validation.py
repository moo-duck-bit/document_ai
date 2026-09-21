# -*- coding: utf-8 -*-
"""Identity / routing validation invariants."""

from __future__ import annotations

from typing import Any

from document_ai.document_identity.schema import (
    DocumentIdentityDecision,
    DomainPackRoutingDecision,
    DocumentSignal,
)


def validate_identity_invariants(
    *,
    signals: list[DocumentSignal],
    decision: DocumentIdentityDecision,
    routing: DomainPackRoutingDecision | None = None,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    content = any(
        s.signal_type
        not in {"FILENAME_TOKEN", "DOCUMENT_ROLE_HINT", "FILE_FORMAT", "EXPLICIT_USER_HINT"}
        for s in signals
    )
    filename_only = (not content) and any(s.signal_type == "FILENAME_TOKEN" for s in signals)
    checks["no_filename_only_auto_route"] = not (
        decision.auto_selected and filename_only
    )
    if not checks["no_filename_only_auto_route"]:
        reasons.append("filename_only_auto_route_violation")

    checks["canonical_id_deterministic"] = bool(
        decision.metadata.get("canonical_id_deterministic", True)
    )
    checks["temporary_and_canonical_id_separated"] = (
        decision.canonical_document_id is None
        or decision.canonical_document_id != decision.source_document_id
        or decision.source_document_id.startswith("EC_SW_")
        or decision.source_document_id.startswith("GENERIC_")
    )
    # Allow equality only when source already looks canonical
    if decision.canonical_document_id == decision.source_document_id and not (
        str(decision.source_document_id).startswith("EC_SW_")
        or str(decision.source_document_id).startswith("GENERIC_")
    ):
        # still OK if temporary id happens to equal short form used as upload stem like MDTM
        checks["temporary_and_canonical_id_separated"] = decision.canonical_document_id in {
            "EC_SW_MDTM",
            "EC_SW_MDSR",
            "EC_SW_MDDR",
            "EC_SW_MDVP",
            "EC_SW_XXCS",
            "GENERIC_GENERAL_REPORT",
            "GENERIC_BUSINESS_PROPOSAL",
            None,
        } or decision.source_document_id != decision.canonical_document_id

    conflict_flags = {
        "conflict_requires_review",
        "USER_HINT_CONTENT_CONFLICT",
        "filename_only_no_auto",
    }
    has_conflict_reason = any(r in decision.reason_codes for r in conflict_flags) or any(
        "CONFLICT" in r or "AMBIGUOUS" in r for r in decision.reason_codes
    )
    checks["conflict_requires_review"] = (not has_conflict_reason) or (
        decision.decision_status == "REVIEW_REQUIRED" and not decision.auto_selected
    )

    if routing is not None:
        checks["routed_pack_matches_decision"] = (
            routing.actual_pack_invoked is None
            or routing.actual_pack_invoked == routing.selected_pack_id
            or routing.routing_status != "ROUTED"
        )
        checks["wrong_route_never_writes"] = (
            routing.actual_pack_invoked is None
            or routing.routing_status == "ROUTED"
        ) and not (
            routing.routing_status == "ROUTED"
            and decision.decision_status == "REVIEW_REQUIRED"
            and "USER_HINT_CONTENT_CONFLICT" in decision.reason_codes
            and routing.actual_pack_invoked is not None
            and routing.metadata.get("routing_mode") != "explicit"
        )
    else:
        checks["routed_pack_matches_decision"] = True
        checks["wrong_route_never_writes"] = True

    ok = all(checks.values())
    return {"ok": ok, "checks": checks, "reasons": reasons, "invariants": list(checks.keys())}
