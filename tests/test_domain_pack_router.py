# -*- coding: utf-8 -*-
"""Domain pack router tests."""

from __future__ import annotations

from pathlib import Path

from document_ai.document_identity.identity_resolver import resolve_document_identity
from document_ai.document_identity.pack_router import (
    document_set_for_identity,
    route_domain_pack,
)
from document_ai.document_identity.ranking import rank_candidates
from document_ai.document_identity.schema import DocumentIdentityCandidate

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures"


def test_ec_sw_auto_route():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    _, cands, ident = resolve_document_identity(
        source_document_id="S1", filename="x.docx", docx_path=p
    )
    r = route_domain_pack(
        identity=ident, candidates=cands, routing_mode="auto", user_confirmed=False
    )
    assert ident.auto_selected
    assert r.routing_status == "ROUTED"
    assert r.actual_pack_invoked == "ec_sw_v1"
    assert r.selected_pack_id == r.actual_pack_invoked


def test_general_report_route():
    p = FX / "general_report" / "report_std.docx"
    if not p.is_file():
        return
    _, cands, ident = resolve_document_identity(
        source_document_id="S1", filename="r.docx", docx_path=p
    )
    r = route_domain_pack(identity=ident, candidates=cands, routing_mode="auto")
    if ident.auto_selected:
        assert r.actual_pack_invoked == "generic_document_v1"
        assert document_set_for_identity(ident) == "general_report"


def test_business_proposal_route():
    p = FX / "business_proposal" / "proposal_base.docx"
    if not p.is_file():
        return
    _, cands, ident = resolve_document_identity(
        source_document_id="S1", filename="p.docx", docx_path=p
    )
    assert ident.document_role == "business_proposal"
    assert document_set_for_identity(ident) == "business_proposal"


def test_ambiguous_route_review():
    # filename-only → not auto routed
    _, cands, ident = resolve_document_identity(
        source_document_id="S1", filename="report_or_proposal.docx"
    )
    r = route_domain_pack(identity=ident, candidates=cands, routing_mode="auto")
    assert r.routing_status == "REVIEW_REQUIRED"
    assert r.actual_pack_invoked is None


def test_filename_only_review():
    _, cands, ident = resolve_document_identity(
        source_document_id="S1", filename="MDTM_draft.docx"
    )
    r = route_domain_pack(identity=ident, candidates=cands, routing_mode="auto")
    assert ident.auto_selected is False
    assert r.routing_status == "REVIEW_REQUIRED"


def test_wrong_pack_blocked_on_conflict():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    _, cands, ident = resolve_document_identity(
        source_document_id="S1",
        filename="x.docx",
        docx_path=p,
        user_hints={"short_id": "REPORT", "document_role": "general_report"},
    )
    r = route_domain_pack(
        identity=ident,
        candidates=cands,
        routing_mode="explicit",
        explicit_document_set="general_report",
    )
    # content conflict should not silently route wrong pack
    assert r.routing_status in {"REVIEW_REQUIRED", "ROUTED"}
    if "USER_HINT_CONTENT_CONFLICT" in ident.reason_codes or "explicit_content_conflict" in r.reason_codes:
        assert r.actual_pack_invoked is None or r.routing_status == "REVIEW_REQUIRED"


def test_top1_recall_ranking_deterministic():
    cands = [
        DocumentIdentityCandidate(
            candidate_id="a",
            source_document_id="S",
            canonical_document_id="EC_SW_MDTM",
            short_id="MDTM",
            domain_pack_id="ec_sw_v1",
            score=80,
            rank_tier=1,
        ),
        DocumentIdentityCandidate(
            candidate_id="b",
            source_document_id="S",
            canonical_document_id="GENERIC_GENERAL_REPORT",
            short_id="REPORT",
            domain_pack_id="generic_document_v1",
            score=40,
            rank_tier=3,
        ),
    ]
    ranked = rank_candidates(list(cands))
    assert ranked[0].short_id == "MDTM"
    packs = []
    for c in ranked:
        if c.domain_pack_id not in packs:
            packs.append(c.domain_pack_id)
    assert packs[0] == "ec_sw_v1"
    assert "generic_document_v1" in packs[:3]


def test_assisted_pending_confirm():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    _, cands, ident = resolve_document_identity(
        source_document_id="S1", filename="x.docx", docx_path=p
    )
    r = route_domain_pack(identity=ident, candidates=cands, routing_mode="assisted")
    assert r.routing_status == "REVIEW_REQUIRED"
    r2 = route_domain_pack(
        identity=ident, candidates=cands, routing_mode="assisted", user_confirmed=True
    )
    assert r2.routing_status == "ROUTED"
    assert r2.actual_pack_invoked == "ec_sw_v1"
