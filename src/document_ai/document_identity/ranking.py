# -*- coding: utf-8 -*-
"""Candidate ranking tiers for document identity."""

from __future__ import annotations

from typing import Any

from document_ai.document_identity.schema import DocumentIdentityCandidate, DocumentSignal


def _has_types(signals: list[DocumentSignal], types: set[str]) -> bool:
    return any(s.signal_type in types for s in signals)


def _content_evidence(signals: list[DocumentSignal]) -> bool:
    return any(
        s.signal_type
        in {
            "DOCUMENT_TITLE",
            "HEADING_TEXT",
            "TABLE_HEADER",
            "IDENTIFIER_PATTERN",
            "TEMPLATE_STRUCTURE",
            "CONTENT_CONCEPT",
            "REGISTRY_MATCH",
        }
        for s in signals
    )


def compute_rank_tier(signals: list[DocumentSignal], *, short_id: str | None) -> int:
    """Return 1..5 (lower is stronger). Filename-only → 5."""
    ids = [s for s in signals if s.signal_type == "IDENTIFIER_PATTERN"]
    struct = [s for s in signals if s.signal_type in {"TEMPLATE_STRUCTURE", "TABLE_HEADER"}]
    heading = [s for s in signals if s.signal_type in {"DOCUMENT_TITLE", "HEADING_TEXT", "CONTENT_CONCEPT"}]
    filename = [s for s in signals if s.signal_type in {"FILENAME_TOKEN", "DOCUMENT_ROLE_HINT"}]
    content = _content_evidence(signals)

    strong_id_struct = any("mdtm_strong_evidence" in s.reason_codes for s in ids) or (
        any(s.normalized_value == "MDTM" for s in struct) and ids
    )
    if strong_id_struct and short_id in {None, "MDTM", "MDSR", "MDDR", "MDVP", "XXCS"}:
        return 1
    if ids and struct and short_id:
        return 1
    if struct and heading and content:
        return 2
    if heading and any(s.signal_type == "CONTENT_CONCEPT" for s in signals):
        return 3
    if filename and content:
        return 4
    if filename and not content:
        return 5
    if not signals:
        return 5
    return 4 if content else 5


def score_candidate(
    *,
    short_id: str | None,
    document_role: str | None,
    domain_pack_id: str | None,
    signals: list[DocumentSignal],
    conflicts: list[str],
) -> tuple[float, int, list[str]]:
    reasons: list[str] = []
    score = 0.0
    relevant = [
        s
        for s in signals
        if (short_id and short_id in {s.normalized_value, s.signal_value.upper()})
        or (document_role and document_role in {s.normalized_value, s.signal_value})
        or (domain_pack_id and domain_pack_id in {s.normalized_value, s.signal_value})
        or s.signal_type
        in {
            "IDENTIFIER_PATTERN",
            "TEMPLATE_STRUCTURE",
            "TABLE_HEADER",
            "CONTENT_CONCEPT",
            "DOCUMENT_TITLE",
            "HEADING_TEXT",
            "FILENAME_TOKEN",
            "DOCUMENT_ROLE_HINT",
            "EXPLICIT_USER_HINT",
            "REGISTRY_MATCH",
        }
    ]
    for s in relevant:
        weight = {
            "IDENTIFIER_PATTERN": 18.0,
            "TEMPLATE_STRUCTURE": 14.0,
            "TABLE_HEADER": 10.0,
            "CONTENT_CONCEPT": 12.0,
            "DOCUMENT_TITLE": 8.0,
            "HEADING_TEXT": 6.0,
            "REGISTRY_MATCH": 10.0,
            "EXPLICIT_USER_HINT": 8.0,
            "FILENAME_TOKEN": 5.0,
            "DOCUMENT_ROLE_HINT": 4.0,
        }.get(s.signal_type, 3.0)
        score += weight * float(s.confidence)
        reasons.extend(s.reason_codes[:1])

    if any("mdtm_strong_evidence" in s.reason_codes for s in signals):
        score += 25.0
        reasons.append("tier1_mdtm_structure")
    if any(s.normalized_value == "REQUIREMENT" for s in signals) and document_role == "requirements":
        score += 15.0
    if any(s.normalized_value == "DESIGN" for s in signals) and document_role == "design":
        score += 15.0
    if any(s.normalized_value == "general_report" for s in signals) and document_role == "general_report":
        score += 18.0
    if any(s.normalized_value == "business_proposal" for s in signals) and document_role == "business_proposal":
        score += 18.0

    if conflicts:
        score *= 0.55
        reasons.append("conflict_penalty")

    tier = compute_rank_tier(signals, short_id=short_id)
    # Soft boost by tier
    score += {1: 20, 2: 12, 3: 6, 4: 2, 5: 0}.get(tier, 0)
    return score, tier, reasons


def rank_candidates(candidates: list[DocumentIdentityCandidate]) -> list[DocumentIdentityCandidate]:
    ordered = sorted(candidates, key=lambda c: (-c.score, c.canonical_document_id or "", c.candidate_id))
    for i, c in enumerate(ordered, start=1):
        c.rank = i
        if c.conflicts:
            c.status = "CONFLICTED"
        elif c.score >= 40 and c.rank_tier <= 2:
            c.status = "STRONG_CANDIDATE"
        elif c.score <= 0:
            c.status = "INVALID"
        else:
            c.status = "CANDIDATE"
    return ordered
