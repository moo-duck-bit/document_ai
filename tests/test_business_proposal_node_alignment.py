# -*- coding: utf-8 -*-
"""Business Proposal node alignment tests."""

from document_ai.domain_packs.business_proposal.node_alignment import build_proposal_alignments
from document_ai.template.node_alignment import NodeAlignment


def test_proposal_template_section_aligns_heading():
    out = build_proposal_alignments(
        document_id="PROPOSAL_BASE",
        template_review_items=[
            {
                "node_id": "business_proposal_v1.schedule",
                "display_name": "일정",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["SCHEDULE"]},
            }
        ],
        document_review_items=[
            {
                "node_id": "heading_0001",
                "display_name": "일정",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["SCHEDULE"], "physical": True},
            }
        ],
    )
    aligns = out.get("alignments") or []
    assert aligns
    a = aligns[0]
    assert a["template_node_id"] == "business_proposal_v1.schedule"
    assert a["document_node_id"] == "heading_0001"
    assert a.get("equivalent_for_evaluation") or a.get("evaluation_equivalence")


def test_budget_field_aligns_budget_table():
    out = build_proposal_alignments(
        document_id="PROPOSAL_BASE",
        template_review_items=[
            {
                "node_id": "business_proposal_v1.budget",
                "display_name": "예산",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["BUDGET"]},
            }
        ],
        document_review_items=[
            {
                "node_id": "table_01",
                "display_name": "항목 단가 금액",
                "status": "REVIEW_REQUIRED",
                "metadata": {
                    "canonical_concepts": ["BUDGET", "TABLE"],
                    "structural_role": "BUDGET_TABLE",
                    "physical": True,
                },
            }
        ],
    )
    assert any(
        a["template_node_id"] == "business_proposal_v1.budget" and a["document_node_id"] == "table_01"
        for a in (out.get("alignments") or [])
    )


def test_schedule_field_aligns_schedule_table():
    out = build_proposal_alignments(
        document_id="PROPOSAL_BASE",
        template_review_items=[
            {
                "node_id": "business_proposal_v1.schedule",
                "display_name": "일정",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["SCHEDULE"]},
            }
        ],
        document_review_items=[
            {
                "node_id": "table_00",
                "display_name": "단계 기간 일정",
                "status": "REVIEW_REQUIRED",
                "metadata": {
                    "canonical_concepts": ["SCHEDULE", "TABLE"],
                    "structural_role": "SCHEDULE_TABLE",
                    "physical": True,
                },
            }
        ],
    )
    assert any(a["document_node_id"] == "table_00" for a in (out.get("alignments") or []))


def test_risk_field_aligns_paragraph():
    out = build_proposal_alignments(
        document_id="PROPOSAL_BASE",
        template_review_items=[
            {
                "node_id": "business_proposal_v1.risks",
                "display_name": "위험 관리",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["RISK", "RISK_MANAGEMENT"]},
            }
        ],
        document_review_items=[
            {
                "node_id": "paragraph_0010",
                "display_name": "위험 완화 방안 본문",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["RISK"], "physical": True},
            }
        ],
    )
    assert any(a["document_node_id"] == "paragraph_0010" for a in (out.get("alignments") or []))


def test_wrong_document_rejected():
    out = build_proposal_alignments(
        document_id="DOC_A",
        template_review_items=[
            {
                "node_id": "business_proposal_v1.budget",
                "display_name": "예산",
                "status": "REVIEW_REQUIRED",
                "document_id": "DOC_A",
            }
        ],
        document_review_items=[
            {
                "node_id": "heading_0001",
                "display_name": "예산",
                "status": "REVIEW_REQUIRED",
                "document_id": "DOC_B",
                "metadata": {"canonical_concepts": ["BUDGET"]},
            }
        ],
    )
    # Alignments are scoped to document_id argument; mismatched doc items should not pair wrongly
    for a in out.get("alignments") or []:
        assert a.get("document_id") == "DOC_A"


def test_patch_equivalence_false_without_physical_locator():
    # Ensure evaluation/patch separation in alignment payload
    out = build_proposal_alignments(
        document_id="PROPOSAL_BASE",
        template_review_items=[
            {
                "node_id": "business_proposal_v1.schedule",
                "display_name": "일정",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["SCHEDULE"]},
            }
        ],
        document_review_items=[
            {
                "node_id": "heading_0001",
                "display_name": "일정",
                "status": "REVIEW_REQUIRED",
                "metadata": {"canonical_concepts": ["SCHEDULE"]},
                # no source_locator
            }
        ],
    )
    for a in out.get("alignments") or []:
        if a.get("equivalent_for_evaluation") or a.get("evaluation_equivalence"):
            assert not a.get("equivalent_for_patch") and not a.get("patch_equivalence")


def test_node_alignment_dataclass_fields():
    a = NodeAlignment(
        alignment_id="a1",
        document_id="D1",
        template_node_id="business_proposal_v1.budget",
        document_node_id="table_01",
        alignment_type="section_table",
        confidence=0.9,
        equivalent_for_evaluation=True,
        equivalent_for_patch=False,
    )
    d = a.to_dict()
    assert d["equivalent_for_evaluation"] is True
    assert d["equivalent_for_patch"] is False
