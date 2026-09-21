# -*- coding: utf-8 -*-
"""Canonical document identity resolution."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from document_ai.document_identity.ranking import rank_candidates, score_candidate
from document_ai.document_identity.schema import (
    DocumentIdentityCandidate,
    DocumentIdentityDecision,
    DocumentSignal,
)
from document_ai.document_identity.signal_extractor import extract_all_signals
from document_ai.document_identity.thresholds import DEFAULT_THRESHOLDS, IdentityThresholds

# Registry-aligned EC-SW short ids (no case hardcoding)
_EC_SW_PROFILES: list[dict[str, str]] = [
    {
        "short_id": "MDTM",
        "document_type": "MDTM",
        "document_role": "traceability",
        "domain_pack_id": "ec_sw_v1",
        "template_id": "ec_sw_mdtm",
        "canonical_document_id": "EC_SW_MDTM",
    },
    {
        "short_id": "MDSR",
        "document_type": "MDSR",
        "document_role": "requirements",
        "domain_pack_id": "ec_sw_v1",
        "template_id": "ec_sw_mdsr",
        "canonical_document_id": "EC_SW_MDSR",
    },
    {
        "short_id": "MDDR",
        "document_type": "MDDR",
        "document_role": "design",
        "domain_pack_id": "ec_sw_v1",
        "template_id": "ec_sw_mddr",
        "canonical_document_id": "EC_SW_MDDR",
    },
    {
        "short_id": "MDVP",
        "document_type": "MDVP",
        "document_role": "verification_plan",
        "domain_pack_id": "ec_sw_v1",
        "template_id": "ec_sw_mdvp",
        "canonical_document_id": "EC_SW_MDVP",
    },
    {
        "short_id": "XXCS",
        "document_type": "XXCS",
        "document_role": "security_tests",
        "domain_pack_id": "ec_sw_v1",
        "template_id": "ec_sw_xxcs",
        "canonical_document_id": "EC_SW_XXCS",
    },
]

_GENERIC_PROFILES: list[dict[str, str]] = [
    {
        "short_id": "REPORT",
        "document_type": "GENERAL_REPORT",
        "document_role": "general_report",
        "domain_pack_id": "generic_document_v1",
        "template_id": "general_report_v1",
        "canonical_document_id": "GENERIC_GENERAL_REPORT",
    },
    {
        "short_id": "PROPOSAL",
        "document_type": "BUSINESS_PROPOSAL",
        "document_role": "business_proposal",
        "domain_pack_id": "generic_document_v1",
        "template_id": "business_proposal_v1",
        "canonical_document_id": "GENERIC_BUSINESS_PROPOSAL",
    },
]


def _decision_id(source_id: str, canonical: str | None) -> str:
    h = hashlib.sha1(f"{source_id}:{canonical or 'none'}".encode("utf-8")).hexdigest()[:12]
    return f"idec_{h}"


def _candidate_id(source_id: str, canonical: str) -> str:
    h = hashlib.sha1(f"{source_id}:{canonical}".encode("utf-8")).hexdigest()[:10]
    return f"icand_{h}"


def _signals_for_profile(signals: list[DocumentSignal], profile: dict[str, str]) -> list[DocumentSignal]:
    sid = profile["short_id"]
    role = profile["document_role"]
    pack = profile["domain_pack_id"]
    out: list[DocumentSignal] = []
    for s in signals:
        nv = (s.normalized_value or "").upper()
        sv = (s.signal_value or "").lower()
        if sid in {nv, (s.signal_value or "").upper()}:
            out.append(s)
            continue
        if role in {(s.normalized_value or ""), s.signal_value}:
            out.append(s)
            continue
        if pack in {(s.normalized_value or ""), s.signal_value}:
            out.append(s)
            continue
        if s.signal_type == "IDENTIFIER_PATTERN":
            if sid == "MDTM" and (
                "mdtm_strong_evidence" in s.reason_codes or s.normalized_value == "trace_row"
            ):
                out.append(s)
            elif sid == "MDSR" and s.normalized_value == "REQUIREMENT":
                out.append(s)
            elif sid == "MDDR" and s.normalized_value == "DESIGN":
                out.append(s)
            elif sid in {"MDTM", "MDSR"} and "requirement" in sv:
                out.append(s)
        if s.signal_type == "TEMPLATE_STRUCTURE" and sid == "MDTM" and "trace" in sv:
            out.append(s)
        if s.signal_type == "CONTENT_CONCEPT":
            if role == "general_report" and s.normalized_value == "general_report":
                out.append(s)
            if role == "business_proposal" and s.normalized_value == "business_proposal":
                out.append(s)
        if s.signal_type in {"DOCUMENT_TITLE", "HEADING_TEXT", "TABLE_HEADER"}:
            blob = f"{s.signal_value} {s.normalized_value}".lower()
            if sid == "MDTM" and any(k in blob for k in ("trace", "matrix", "추적", "mdtm")):
                out.append(s)
            if sid == "MDSR" and any(k in blob for k in ("requirement", "요구", "mdsr")):
                out.append(s)
            if sid == "MDDR" and any(k in blob for k in ("design", "설계", "mddr")):
                out.append(s)
            if role == "general_report" and any(
                k in blob for k in ("배경", "방법", "결과", "결론", "report", "methodology")
            ):
                out.append(s)
            if role == "business_proposal" and any(
                k in blob for k in ("제안", "예산", "일정", "proposal", "budget", "schedule")
            ):
                out.append(s)
    # Always include user hints for conflict detection
    out.extend([s for s in signals if s.signal_type == "EXPLICIT_USER_HINT" and s not in out])
    return out


def detect_conflicts(signals: list[DocumentSignal], profile: dict[str, str]) -> list[str]:
    conflicts: list[str] = []
    # Strong EC-SW vs generic
    has_mdtm = any("mdtm_strong_evidence" in s.reason_codes or s.normalized_value == "MDTM" for s in signals)
    has_report = any(s.normalized_value == "general_report" for s in signals)
    has_proposal = any(s.normalized_value == "business_proposal" for s in signals)
    has_req = any(s.normalized_value == "REQUIREMENT" for s in signals)
    has_des = any(s.normalized_value == "DESIGN" for s in signals)

    if has_mdtm and profile["short_id"] in {"REPORT", "PROPOSAL"}:
        conflicts.append("EC_SW_VS_GENERIC")
    if has_report and has_proposal and profile["short_id"] in {"REPORT", "PROPOSAL"}:
        conflicts.append("REPORT_PROPOSAL_AMBIGUOUS")
    if has_mdtm and has_req and profile["short_id"] == "MDSR" and any(
        "mdtm_strong_evidence" in s.reason_codes for s in signals
    ):
        # MDTM matrix can contain req ids — not necessarily MDSR
        pass
    if has_req and has_des and not has_mdtm and profile["short_id"] in {"MDSR", "MDDR"}:
        conflicts.append("MDSR_MDDR_AMBIGUOUS")

    # User hint vs content
    user_hints = [s for s in signals if s.signal_type == "EXPLICIT_USER_HINT"]
    for uh in user_hints:
        hint = (uh.normalized_value or uh.signal_value or "").upper()
        if has_mdtm and hint in {"REPORT", "PROPOSAL", "GENERAL_REPORT", "BUSINESS_PROPOSAL"}:
            conflicts.append("USER_HINT_CONTENT_CONFLICT")
        if (has_report or has_proposal) and hint in {"MDTM", "MDSR", "MDDR"} and not has_mdtm and not has_req:
            conflicts.append("USER_HINT_CONTENT_CONFLICT")
        if hint == "MDTM" and has_report and not has_mdtm:
            conflicts.append("USER_HINT_CONTENT_CONFLICT")
    return conflicts


def build_candidates(
    *,
    source_document_id: str,
    signals: list[DocumentSignal],
) -> list[DocumentIdentityCandidate]:
    candidates: list[DocumentIdentityCandidate] = []
    for profile in _EC_SW_PROFILES + _GENERIC_PROFILES:
        relevant = _signals_for_profile(signals, profile)
        if not relevant and not any(s.signal_type == "FILENAME_TOKEN" for s in signals):
            continue
        # Skip empty profiles unless filename/user points at them
        pointed = any(
            (s.normalized_value or "").upper() == profile["short_id"]
            or s.signal_value == profile["document_role"]
            for s in signals
            if s.signal_type in {"FILENAME_TOKEN", "DOCUMENT_ROLE_HINT", "EXPLICIT_USER_HINT", "TEMPLATE_STRUCTURE"}
        )
        contentish = any(
            s.signal_type
            in {"IDENTIFIER_PATTERN", "TEMPLATE_STRUCTURE", "CONTENT_CONCEPT", "TABLE_HEADER", "HEADING_TEXT"}
            for s in relevant
        )
        if not pointed and not contentish:
            continue
        conflicts = detect_conflicts(signals, profile)
        score, tier, reasons = score_candidate(
            short_id=profile["short_id"],
            document_role=profile["document_role"],
            domain_pack_id=profile["domain_pack_id"],
            signals=relevant if relevant else signals,
            conflicts=conflicts,
        )
        if score <= 0 and not pointed:
            continue
        candidates.append(
            DocumentIdentityCandidate(
                candidate_id=_candidate_id(source_document_id, profile["canonical_document_id"]),
                source_document_id=source_document_id,
                canonical_document_id=profile["canonical_document_id"],
                short_id=profile["short_id"],
                document_type=profile["document_type"],
                document_role=profile["document_role"],
                domain_pack_id=profile["domain_pack_id"],
                template_id=profile["template_id"],
                score=round(score, 3),
                rank_tier=tier,
                reason_codes=list(dict.fromkeys(reasons))[:12],
                evidence_ids=[s.signal_id for s in relevant][:20],
                conflicts=conflicts,
                metadata={"profile": profile["short_id"]},
            )
        )
    return rank_candidates(candidates)


def decide_identity(
    *,
    source_document_id: str,
    candidates: list[DocumentIdentityCandidate],
    signals: list[DocumentSignal],
    thresholds: IdentityThresholds = DEFAULT_THRESHOLDS,
) -> DocumentIdentityDecision:
    if not candidates:
        return DocumentIdentityDecision(
            decision_id=_decision_id(source_document_id, None),
            source_document_id=source_document_id,
            canonical_document_id=None,
            decision_status="UNRESOLVED",
            reason_codes=["no_candidates"],
            human_review_required=True,
            auto_selected=False,
        )

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    margin = top.score - (second.score if second else 0.0)
    content = any(
        s.signal_type
        not in {"FILENAME_TOKEN", "DOCUMENT_ROLE_HINT", "FILE_FORMAT", "EXPLICIT_USER_HINT"}
        for s in signals
    )
    filename_only = (not content) and any(s.signal_type == "FILENAME_TOKEN" for s in signals)
    reasons = list(top.reason_codes)
    conflicts = list(top.conflicts)
    if second and second.conflicts:
        conflicts.extend(second.conflicts)
    # Cross-pack ambiguity when top two close
    if second and margin < thresholds.auto_min_margin and top.domain_pack_id != second.domain_pack_id:
        conflicts.append("CROSS_PACK_AMBIGUOUS")
    if second and margin < thresholds.auto_min_margin and top.short_id != second.short_id:
        if top.rank_tier >= 3 or second.rank_tier <= top.rank_tier:
            conflicts.append("TOP_CANDIDATES_CLOSE")

    status: str = "REVIEW_REQUIRED"
    auto = False
    if conflicts:
        status = "REVIEW_REQUIRED"
        reasons.append("conflict_requires_review")
        if "USER_HINT_CONTENT_CONFLICT" in conflicts:
            reasons.append("USER_HINT_CONTENT_CONFLICT")
    elif filename_only or top.rank_tier >= thresholds.filename_only_max_tier:
        status = "REVIEW_REQUIRED"
        reasons.append("filename_only_no_auto")
        reasons.append("no_filename_only_auto_route")
    elif (
        top.rank_tier <= thresholds.auto_max_tier
        and top.score >= thresholds.auto_min_score
        and margin >= thresholds.auto_min_margin
        and content
        and not conflicts
    ):
        status = "AUTO_SELECTED"
        auto = True
        reasons.append("auto_selected_strong_evidence")
    else:
        status = "REVIEW_REQUIRED"
        reasons.append("insufficient_margin_or_tier")

    return DocumentIdentityDecision(
        decision_id=_decision_id(source_document_id, top.canonical_document_id),
        source_document_id=source_document_id,
        canonical_document_id=top.canonical_document_id,
        short_id=top.short_id,
        document_type=top.document_type,
        document_role=top.document_role,
        domain_pack_id=top.domain_pack_id,
        template_id=top.template_id,
        decision_status=status,  # type: ignore[arg-type]
        top_score=top.score,
        second_score=second.score if second else 0.0,
        score_margin=round(margin, 3),
        rank_tier=top.rank_tier,
        reason_codes=list(dict.fromkeys(reasons))[:16],
        evidence=[{"signal_id": s.signal_id, "type": s.signal_type, "value": s.signal_value[:80]} for s in signals[:12]],
        human_review_required=not auto,
        auto_selected=auto,
        metadata={
            "temporary_source_id": source_document_id,
            "canonical_id_deterministic": True,
            "filename_only": filename_only,
        },
    )


def resolve_document_identity(
    *,
    source_document_id: str,
    filename: str,
    docx_path: Path | None = None,
    file_bytes: bytes | None = None,
    user_hints: dict[str, Any] | None = None,
    thresholds: IdentityThresholds = DEFAULT_THRESHOLDS,
) -> tuple[list[DocumentSignal], list[DocumentIdentityCandidate], DocumentIdentityDecision]:
    signals = extract_all_signals(
        source_document_id=source_document_id,
        filename=filename,
        docx_path=docx_path,
        file_bytes=file_bytes,
        user_hints=user_hints,
    )
    candidates = build_candidates(source_document_id=source_document_id, signals=signals)
    decision = decide_identity(
        source_document_id=source_document_id,
        candidates=candidates,
        signals=signals,
        thresholds=thresholds,
    )
    return signals, candidates, decision
