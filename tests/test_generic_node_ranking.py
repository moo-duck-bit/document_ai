# -*- coding: utf-8 -*-
from document_ai.domain_packs.generic.query_intent import parse_generic_query_intent
from document_ai.domain_packs.generic.structural_match import rank_generic_candidates


def test_parent_child_direct_match_boost():
    intent = parse_generic_query_intent("방법론 본문 수정")
    cands = [
        {
            "node_id": "heading_0001",
            "status": "REVIEW_REQUIRED",
            "display_name": "방법론",
            "metadata": {
                "structural_role": "DOCUMENT_HEADING",
                "canonical_concepts": ["METHODOLOGY"],
                "inherited_match": False,
                "direct_match": True,
            },
        },
        {
            "node_id": "paragraph_0003",
            "status": "REVIEW_REQUIRED",
            "display_name": "방법론 세부 접근",
            "metadata": {
                "structural_role": "PARAGRAPH_BODY",
                "canonical_concepts": ["METHODOLOGY"],
                "parent_section_id": "heading_0001",
                "direct_match": True,
                "parent_context_match": 0.85,
                "content_specificity": 0.8,
                "alignment_confidence": 0.85,
                "evaluation_equivalent": True,
            },
        },
    ]
    out = rank_generic_candidates(cands, intent=intent)
    assert out["ranking_candidates"][0]["node_id"] in {"paragraph_0003", "heading_0001"}


def test_operation_role_rank_consistent_validation():
    intent = parse_generic_query_intent("일정 표 수정")
    cands = [
        {
            "node_id": "table_00",
            "status": "REVIEW_REQUIRED",
            "display_name": "일정",
            "metadata": {"structural_role": "TABLE", "canonical_concepts": ["SCHEDULE", "TABLE"]},
        },
        {
            "node_id": "paragraph_0099",
            "status": "REVIEW_REQUIRED",
            "display_name": "기타",
            "metadata": {"structural_role": "PARAGRAPH_BODY", "canonical_concepts": []},
        },
    ]
    out = rank_generic_candidates(cands, intent=intent)
    assert out["validation"]["table_intent_prefers_table_structure"]


def test_template_only_lower_than_aligned_template_eval():
    intent = parse_generic_query_intent("결론 수정")
    cands = [
        {
            "node_id": "general_report_v1.conclusion",
            "status": "REVIEW_REQUIRED",
            "display_name": "결론",
            "metadata": {
                "structural_role": "TEMPLATE_SECTION",
                "canonical_concepts": ["CONCLUSION"],
                "evaluation_equivalent": True,
                "alignment_confidence": 0.9,
            },
        },
        {
            "node_id": "general_report_v1.background",
            "status": "REVIEW_REQUIRED",
            "display_name": "배경",
            "metadata": {
                "structural_role": "TEMPLATE_SECTION",
                "canonical_concepts": ["BACKGROUND"],
                "template_only": True,
            },
        },
    ]
    out = rank_generic_candidates(cands, intent=intent)
    assert out["ranking_results"]["ranked_node_ids"][0] == "general_report_v1.conclusion"
