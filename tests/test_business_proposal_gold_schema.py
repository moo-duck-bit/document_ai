# -*- coding: utf-8 -*-
"""Schema round-trip / defaults tests for Business Proposal gold rows (Cycle 6)."""

from __future__ import annotations

from document_ai.evaluation.business_proposal_gold.schema import (
    ALLOWED_LOCATION_TYPES,
    ALLOWED_MODES,
    ALLOWED_OPERATIONS,
    ALLOWED_PHYSICAL_NODE_TYPES,
    ALLOWED_REFERENCE_TYPES,
    BusinessProposalGoldRow,
    PrimaryReference,
)


def test_allowed_modes_exactly_four():
    assert ALLOWED_MODES == {"REQUIRED", "AMBIGUOUS", "OPTIONAL", "NOT_APPLICABLE"}


def test_allowed_reference_types():
    assert ALLOWED_REFERENCE_TYPES == {"STABLE", "TEMPLATE", "PHYSICAL", "VIRTUAL"}


def test_allowed_physical_node_types():
    assert ALLOWED_PHYSICAL_NODE_TYPES == {"HEADING", "PARAGRAPH", "TABLE", "NONE"}


def test_allowed_location_types():
    assert ALLOWED_LOCATION_TYPES == {"SECTION", "TABLE", "PARAGRAPH", "DOCUMENT_LEVEL", "VIRTUAL"}


def test_allowed_operations():
    assert ALLOWED_OPERATIONS == {"ADD", "UPDATE", "DELETE", "REPLACE", "REVIEW", "UNKNOWN"}


def test_primary_reference_to_dict_from_dict_round_trip():
    ref = PrimaryReference(
        reference_type="TEMPLATE",
        template_node_id="business_proposal_v1.schedule",
        document_node_id="heading_0001",
        canonical_concepts=["SCHEDULE"],
    )
    d = ref.to_dict()
    ref2 = PrimaryReference.from_dict(d)
    assert ref2 is not None
    assert ref2.reference_type == "TEMPLATE"
    assert ref2.template_node_id == "business_proposal_v1.schedule"
    assert ref2.document_node_id == "heading_0001"
    assert ref2.canonical_concepts == ["SCHEDULE"]


def test_primary_reference_from_dict_none_returns_none():
    assert PrimaryReference.from_dict(None) is None
    assert PrimaryReference.from_dict({}) is None


def test_primary_reference_from_dict_defaults_reference_type():
    ref = PrimaryReference.from_dict({"template_node_id": "x"})
    assert ref is not None
    assert ref.reference_type == "TEMPLATE"
    assert ref.stable_locator == {}


def test_gold_row_to_dict_from_dict_round_trip():
    row = BusinessProposalGoldRow(
        case_id="v2_dev_bp_schedule",
        document_id="PROPOSAL_BASE",
        node_evaluation_mode="REQUIRED",
        primary_reference={"reference_type": "TEMPLATE", "template_node_id": "business_proposal_v1.schedule"},
        acceptable_references=[{"reference_type": "PHYSICAL", "document_node_id": "paragraph_0003"}],
        acceptable_groups=[["heading_0001", "paragraph_0003"]],
        expected_node_type="PARAGRAPH",
        expected_physical_node_type="PARAGRAPH",
        expected_location_type="SECTION",
        expected_operation="UPDATE",
        label_rationale="unique matching physical node",
        labeled_by="pass1_structure_policy",
        labeled_at="2026-08-01T00:00:00+00:00",
        label_confidence=0.9,
    )
    d = row.to_dict()
    row2 = BusinessProposalGoldRow.from_dict(d)
    assert row2.case_id == row.case_id
    assert row2.node_evaluation_mode == "REQUIRED"
    assert row2.primary_reference == row.primary_reference
    assert row2.acceptable_groups == [["heading_0001", "paragraph_0003"]]
    assert row2.label_confidence == 0.9


def test_gold_row_defaults():
    row = BusinessProposalGoldRow(
        case_id="c1", document_id="D1", node_evaluation_mode="NOT_APPLICABLE"
    )
    assert row.primary_reference is None
    assert row.acceptable_references == []
    assert row.acceptable_groups == []
    assert row.label_source == "document_structure_and_change_request"
    assert row.label_confidence == 0.0
    assert row.labeled_by == ""


def test_gold_row_from_dict_missing_optional_fields():
    minimal = {"case_id": "c2", "document_id": "D2", "node_evaluation_mode": "OPTIONAL"}
    row = BusinessProposalGoldRow.from_dict(minimal)
    assert row.acceptable_references == []
    assert row.acceptable_groups == []
    assert row.label_rationale == ""
    assert row.label_source == "document_structure_and_change_request"
    assert row.label_confidence == 0.0


def test_gold_row_acceptable_groups_are_lists_not_tuples():
    d = {
        "case_id": "c3",
        "document_id": "D3",
        "node_evaluation_mode": "AMBIGUOUS",
        "acceptable_groups": [["a", "b"], ["c"]],
    }
    row = BusinessProposalGoldRow.from_dict(d)
    assert all(isinstance(g, list) for g in row.acceptable_groups)
    assert row.acceptable_groups == [["a", "b"], ["c"]]
