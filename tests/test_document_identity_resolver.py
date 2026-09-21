# -*- coding: utf-8 -*-
"""Identity resolver tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from document_ai.document_identity.identity_resolver import resolve_document_identity
from document_ai.document_identity.orchestrator import analyze_duplicates, file_content_hash
from document_ai.document_identity.validation import validate_identity_invariants

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures"


def _resolve(filename: str, path: Path | None = None, **kw):
    return resolve_document_identity(
        source_document_id="TMP_" + filename.upper()[:12],
        filename=filename,
        docx_path=path,
        **kw,
    )


def test_mdtm_renamed_file_auto():
    p = FX / "ec_sw" / "uploaded_trace_matrix.docx"
    if not p.is_file():
        return
    _, _, d = _resolve("trace_matrix_final_v3.docx", p)
    assert d.short_id == "MDTM"
    assert d.canonical_document_id == "EC_SW_MDTM"
    assert d.auto_selected is True
    assert d.decision_status == "AUTO_SELECTED"


def test_mdsr_renamed_filename_only_review():
    _, _, d = _resolve("요구사항_MDSR_초안.docx")
    assert d.decision_status == "REVIEW_REQUIRED"
    assert "filename_only_no_auto" in d.reason_codes or d.rank_tier >= 5 or not d.auto_selected


def test_mddr_renamed_filename_only_review():
    _, _, d = _resolve("설계_MDDR.docx")
    assert d.auto_selected is False


def test_general_report_unknown_filename():
    p = FX / "general_report" / "report_std.docx"
    if not p.is_file():
        return
    _, _, d = _resolve("2026_중간성과자료.docx", p)
    assert d.document_role == "general_report"
    assert d.domain_pack_id == "generic_document_v1"


def test_business_proposal_unknown_filename():
    p = FX / "business_proposal" / "proposal_base.docx"
    if not p.is_file():
        return
    _, _, d = _resolve("제출용_초안.docx", p)
    assert d.document_role == "business_proposal"


def test_filename_content_conflict_review():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    _, _, d = resolve_document_identity(
        source_document_id="TMP1",
        filename="중간성과_보고서.docx",
        docx_path=p,
        user_hints={"short_id": "REPORT", "document_role": "general_report"},
    )
    # MDTM content vs report hint/filename
    assert d.decision_status == "REVIEW_REQUIRED"
    assert d.auto_selected is False


def test_user_hint_content_conflict():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    sigs, _, d = resolve_document_identity(
        source_document_id="TMP1",
        filename="x.docx",
        docx_path=p,
        user_hints={"short_id": "REPORT"},
    )
    assert "USER_HINT_CONTENT_CONFLICT" in d.reason_codes or d.decision_status == "REVIEW_REQUIRED"
    v = validate_identity_invariants(signals=sigs, decision=d)
    assert v["checks"]["conflict_requires_review"]


def test_no_signal_unresolved_or_review():
    _, cands, d = _resolve("zzzz_unknown_qqq.docx")
    assert d.decision_status in {"UNRESOLVED", "REVIEW_REQUIRED"}
    assert d.auto_selected is False


def test_deterministic_canonical_id():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    a = _resolve("a.docx", p)[2]
    b = _resolve("b.docx", p)[2]
    assert a.canonical_document_id == b.canonical_document_id == "EC_SW_MDTM"


def test_temporary_vs_canonical_separated():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    _, _, d = resolve_document_identity(
        source_document_id="MDTM_BASE",
        filename="mdtm_base.docx",
        docx_path=p,
    )
    assert d.source_document_id == "MDTM_BASE"
    assert d.canonical_document_id == "EC_SW_MDTM"
    assert d.source_document_id != d.canonical_document_id


def test_duplicate_exact():
    data = b"same-bytes"
    h = file_content_hash(data)
    from document_ai.document_identity.schema import DocumentIdentityDecision

    decisions = [
        DocumentIdentityDecision(
            decision_id="1",
            source_document_id="A",
            canonical_document_id="EC_SW_MDTM",
            decision_status="AUTO_SELECTED",
        ),
        DocumentIdentityDecision(
            decision_id="2",
            source_document_id="B",
            canonical_document_id="EC_SW_MDTM",
            decision_status="AUTO_SELECTED",
        ),
    ]
    dups = analyze_duplicates(decisions=decisions, content_hashes={"A": h, "B": h})
    assert dups and dups[0]["status"] == "DUPLICATE_EXACT"


def test_duplicate_variant():
    from document_ai.document_identity.schema import DocumentIdentityDecision

    decisions = [
        DocumentIdentityDecision(
            decision_id="1",
            source_document_id="A",
            canonical_document_id="EC_SW_MDTM",
            decision_status="AUTO_SELECTED",
        ),
        DocumentIdentityDecision(
            decision_id="2",
            source_document_id="B",
            canonical_document_id="EC_SW_MDTM",
            decision_status="AUTO_SELECTED",
        ),
    ]
    dups = analyze_duplicates(
        decisions=decisions,
        content_hashes={"A": hashlib.sha256(b"1").hexdigest(), "B": hashlib.sha256(b"2").hexdigest()},
    )
    assert dups and dups[0]["status"] == "DUPLICATE_VARIANT"


def test_no_filename_only_auto_invariant():
    sigs, _, d = _resolve("mdtm_only_name.docx")
    v = validate_identity_invariants(signals=sigs, decision=d)
    assert v["checks"]["no_filename_only_auto_route"]
