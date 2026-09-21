# -*- coding: utf-8 -*-
"""EC-SW document impact policy unit tests."""

from __future__ import annotations

from document_ai.domain_packs.ec_sw.document_impact import (
    DocumentImpactEvidence,
    build_evidences_for_uploads,
    decide_document_impacts,
    decide_status_from_evidence,
    validate_document_impact_decisions,
)


def _ev(**kwargs) -> DocumentImpactEvidence:
    base = dict(
        document_id="MDTM",
        document_role="traceability",
        evidence_type="DOCUMENT_PRESENCE",
        evidence_value="x",
        source_stage="test",
        confidence=0.1,
        independent_group="g",
        reason_codes=[],
        supports_impacted=False,
        supports_review=False,
    )
    base.update(kwargs)
    return DocumentImpactEvidence(**base)


def test_exact_evidence_impacted():
    status, _ = decide_status_from_evidence(
        [
            _ev(
                evidence_type="EXACT_IDENTIFIER_MATCH",
                supports_impacted=True,
                confidence=0.95,
                independent_group="n1",
            )
        ]
    )
    assert status == "IMPACTED"


def test_normalized_evidence_impacted():
    status, _ = decide_status_from_evidence(
        [
            _ev(
                evidence_type="NORMALIZED_IDENTIFIER_MATCH",
                supports_impacted=True,
                confidence=0.9,
                independent_group="n1",
            )
        ]
    )
    assert status == "IMPACTED"


def test_role_only_unrelated():
    status, codes = decide_status_from_evidence(
        [_ev(evidence_type="ROLE_COMPATIBILITY", evidence_value="requirements")]
    )
    assert status == "UNRELATED"
    assert "no_role_only_impacted" in codes or "role_or_presence_only" in codes


def test_presence_only_unrelated():
    status, _ = decide_status_from_evidence([_ev(evidence_type="DOCUMENT_PRESENCE")])
    assert status == "UNRELATED"


def test_semantic_only_review():
    status, codes = decide_status_from_evidence(
        [
            _ev(
                evidence_type="SEMANTIC_SECTION_MATCH",
                supports_review=True,
                confidence=0.5,
                independent_group="s1",
            )
        ]
    )
    assert status == "REVIEW_REQUIRED"
    assert "no_semantic_only_patch" in codes


def test_malformed_only_unrelated():
    status, codes = decide_status_from_evidence(
        [_ev(evidence_type="MALFORMED_IDENTIFIER", evidence_value="REQ2")],
        malformed_only=True,
    )
    assert status == "UNRELATED"
    assert "malformed_id_not_exact" in codes


def test_malformed_plus_semantic_review():
    status, _ = decide_status_from_evidence(
        [
            _ev(evidence_type="MALFORMED_IDENTIFIER"),
            _ev(
                evidence_type="SEMANTIC_SECTION_MATCH",
                supports_review=True,
                independent_group="s",
            ),
        ]
    )
    assert status == "REVIEW_REQUIRED"


def test_indirect_design_review():
    status, _ = decide_status_from_evidence(
        [
            _ev(
                evidence_type="SEMANTIC_SECTION_MATCH",
                supports_review=True,
                reason_codes=["indirect_design_or_test_match"],
                independent_group="d",
            )
        ]
    )
    assert status == "REVIEW_REQUIRED"


def test_mdtm_only_does_not_propagate():
    ev = build_evidences_for_uploads(
        change_request="Req. 2 MDTM만 영향",
        uploaded_docs=[
            {"document_id": "MDTM", "role": "traceability", "filename": "MDTM.docx"},
            {"document_id": "MDSR_STUB", "role": "requirements", "filename": "MDSR_stub.docx"},
        ],
        patch_candidates=[
            {
                "document_id": "MDTM",
                "node_id": "n1",
                "matched_requirement_ids": ["Req. 2"],
                "reason_codes": ["exact_requirement_id_match"],
            }
        ],
        review_required=[],
    )
    decisions = {d["document_id"]: d for d in decide_document_impacts(ev)}
    assert decisions["MDTM"]["predicted_status"] == "IMPACTED"
    assert decisions["MDSR_STUB"]["predicted_status"] == "UNRELATED"


def test_explicit_cross_doc_can_support_mdtm():
    ev = build_evidences_for_uploads(
        change_request="Req. 2 MDTM 문서 수정",
        uploaded_docs=[
            {"document_id": "MDTM", "role": "traceability", "filename": "MDTM.docx"},
        ],
        patch_candidates=[
            {
                "document_id": "MDTM",
                "node_id": "n1",
                "matched_requirement_ids": ["Req. 2"],
                "reason_codes": ["exact_requirement_id_match"],
            }
        ],
        review_required=[],
    )
    decisions = decide_document_impacts(ev)
    assert any(d["document_id"] == "MDTM" and d["predicted_status"] == "IMPACTED" for d in decisions)


def test_missing_evidence_unrelated():
    status, _ = decide_status_from_evidence([])
    assert status == "UNRELATED"


def test_validation_rejects_role_only_impacted():
    evs = [_ev(evidence_type="ROLE_COMPATIBILITY")]
    decisions = [
        {
            "document_id": "MDSR_STUB",
            "predicted_status": "IMPACTED",
            "substantive_evidence_count": 0,
            "exact_identifier_count": 0,
            "normalized_identifier_count": 0,
            "semantic_evidence_count": 0,
        }
    ]
    v = validate_document_impact_decisions(decisions, {"MDSR_STUB": evs})
    assert v["status"] == "INVALID"
    assert any("substantive" in i or "role_only" in i for i in v["issues"])
