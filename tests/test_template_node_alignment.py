# -*- coding: utf-8 -*-
"""Template ↔ document node alignment tests."""

from __future__ import annotations

from document_ai.template.node_alignment import (
    boost_template_alignment_scores,
    build_node_alignments,
    expand_acceptable_groups_with_alignments,
)


def test_heading_to_template_section():
    payload = build_node_alignments(
        document_id="REPORT_BASE",
        template_review_items=[
            {
                "node_id": "general_report_v1.schedule",
                "display_name": "일정",
                "document_id": "REPORT_BASE",
            }
        ],
        document_review_items=[
            {
                "node_id": "heading_0007",
                "display_name": "일정",
                "document_id": "REPORT_BASE",
                "canonical_concepts": ["SCHEDULE"],
            }
        ],
    )
    assert payload["alignments"]
    a = payload["alignments"][0]
    assert a["alignment_type"] == "HEADING_TO_SECTION"
    assert a["equivalent_for_evaluation"] is True


def test_paragraph_to_template_field():
    payload = build_node_alignments(
        document_id="REPORT_BASE",
        template_review_items=[
            {"node_id": "general_report_v1.results", "display_name": "결과", "document_id": "REPORT_BASE"}
        ],
        document_review_items=[
            {
                "node_id": "paragraph_0002",
                "display_name": "결과 요약",
                "document_id": "REPORT_BASE",
                "source_locator": {"paragraph_index": 2},
            }
        ],
    )
    assert any(a["alignment_type"] == "PARAGRAPH_TO_FIELD" for a in payload["alignments"])
    assert any(a["template_node_id"].endswith(".results") for a in payload["alignments"])


def test_table_to_schedule_section():
    payload = build_node_alignments(
        document_id="REPORT_BASE",
        template_review_items=[
            {"node_id": "general_report_v1.schedule", "display_name": "일정", "document_id": "REPORT_BASE"}
        ],
        document_review_items=[
            {
                "node_id": "table_00",
                "display_name": "일정 표",
                "document_id": "REPORT_BASE",
                "canonical_concepts": ["SCHEDULE", "TABLE"],
                "source_locator": {"table_index": 0},
            }
        ],
    )
    assert any(a["alignment_type"] == "TABLE_TO_SECTION" for a in payload["alignments"])


def test_wrong_document_rejected():
    payload = build_node_alignments(
        document_id="REPORT_BASE",
        template_review_items=[
            {"node_id": "general_report_v1.schedule", "display_name": "일정", "document_id": "REPORT_BASE"}
        ],
        document_review_items=[
            {
                "node_id": "heading_0001",
                "display_name": "일정",
                "document_id": "OTHER_DOC",
                "canonical_concepts": ["SCHEDULE"],
            }
        ],
    )
    assert payload["alignments"] == []


def test_unsupported_alignment_no_match():
    payload = build_node_alignments(
        document_id="REPORT_BASE",
        template_review_items=[
            {"node_id": "general_report_v1.schedule", "display_name": "일정", "document_id": "REPORT_BASE"}
        ],
        document_review_items=[
            {
                "node_id": "heading_0001",
                "display_name": "예산 편성",
                "document_id": "REPORT_BASE",
                "canonical_concepts": ["BUDGET"],
            }
        ],
    )
    assert payload["alignments"] == []


def test_evaluation_equivalence_true():
    payload = build_node_alignments(
        document_id="REPORT_BASE",
        template_review_items=[
            {"node_id": "general_report_v1.schedule", "display_name": "일정", "document_id": "REPORT_BASE"}
        ],
        document_review_items=[
            {
                "node_id": "heading_0007",
                "display_name": "일정",
                "document_id": "REPORT_BASE",
                "canonical_concepts": ["SCHEDULE"],
            }
        ],
    )
    assert payload["alignments"][0]["equivalent_for_evaluation"] is True


def test_patch_equivalence_false_when_locator_unresolved():
    payload = build_node_alignments(
        document_id="REPORT_BASE",
        template_review_items=[
            {"node_id": "general_report_v1.schedule", "display_name": "일정", "document_id": "REPORT_BASE"}
        ],
        document_review_items=[
            {
                "node_id": "heading_0007",
                "display_name": "일정",
                "document_id": "REPORT_BASE",
                "canonical_concepts": ["SCHEDULE"],
                # no source_locator
            }
        ],
    )
    assert payload["alignments"][0]["equivalent_for_patch"] is False
    assert payload["validation"]["evaluation_patch_equivalence_separated"] is True


def test_structural_group_hit_expansion():
    groups = [["general_report_v1.schedule"]]
    alignments = [
        {
            "template_node_id": "general_report_v1.schedule",
            "document_node_id": "heading_0007",
            "equivalent_for_evaluation": True,
        }
    ]
    expanded = expand_acceptable_groups_with_alignments(groups, alignments)
    assert "heading_0007" in expanded[0]
    assert "general_report_v1.schedule" in expanded[0]


def test_boost_template_scores():
    items = [
        {
            "node_id": "general_report_v1.schedule",
            "overlap": 0.7,
            "metadata": {"overlap": 0.7},
            "reason_codes": [],
        }
    ]
    alignments = [
        {
            "template_node_id": "general_report_v1.schedule",
            "document_node_id": "heading_0007",
            "equivalent_for_evaluation": True,
            "confidence": 0.9,
        }
    ]
    boost_template_alignment_scores(items, alignments)
    assert items[0]["overlap"] >= 1.25
