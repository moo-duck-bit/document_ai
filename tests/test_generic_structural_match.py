# -*- coding: utf-8 -*-
from document_ai.domain_packs.generic.query_intent import parse_generic_query_intent
from document_ai.domain_packs.generic.structural_match import (
    promote_aligned_template_candidates,
    rank_generic_candidates,
    score_structural_match,
)


def _cand(nid, *, role, display="", concepts=None, status="REVIEW_REQUIRED", **meta):
    return {
        "node_id": nid,
        "status": status,
        "display_name": display or nid,
        "metadata": {
            "structural_role": role,
            "canonical_concepts": concepts or [],
            "physical": role not in {"TEMPLATE_SECTION", "VIRTUAL_TARGET"},
            "writer_executable": False,
            **meta,
        },
    }


def test_exact_paragraph_can_beat_heading_when_more_specific():
    intent = parse_generic_query_intent("결론 본문을 수정한다")
    cands = [
        _cand("heading_0001", role="DOCUMENT_HEADING", display="결론", concepts=["CONCLUSION"]),
        _cand(
            "paragraph_0007",
            role="PARAGRAPH_BODY",
            display="결론 본문 상세 내용",
            concepts=["CONCLUSION"],
            content_specificity=0.9,
            direct_match=True,
            parent_context_match=0.8,
            alignment_confidence=0.9,
            evaluation_equivalent=True,
        ),
    ]
    out = rank_generic_candidates(cands, intent=intent)
    assert out["ranking_results"]["ranked_node_ids"][0] in {"paragraph_0007", "heading_0001"}


def test_heading_beats_document_context():
    intent = parse_generic_query_intent("결과 섹션 검토")
    cands = [
        _cand("ctx", role="DOCUMENT_CONTEXT", display="문서", concepts=[]),
        _cand("heading_0002", role="DOCUMENT_HEADING", display="결과", concepts=["RESULTS"]),
    ]
    out = rank_generic_candidates(cands, intent=intent)
    assert out["ranking_results"]["ranked_node_ids"][0] == "heading_0002"


def test_schedule_table_beats_unrelated_paragraph():
    intent = parse_generic_query_intent("일정 표를 수정한다")
    cands = [
        _cand("paragraph_0001", role="PARAGRAPH_BODY", display="배경 설명", concepts=["BACKGROUND"]),
        _cand(
            "table_00",
            role="TABLE",
            display="일정 표",
            concepts=["SCHEDULE", "TABLE"],
            evidence_type="TABLE_STRUCTURE",
        ),
    ]
    out = rank_generic_candidates(cands, intent=intent)
    assert out["ranking_results"]["ranked_node_ids"][0] == "table_00"


def test_budget_table_beats_generic_section():
    intent = parse_generic_query_intent("예산 표를 업데이트")
    cands = [
        _cand("paragraph_0000", role="PARAGRAPH_BODY", display="개요", concepts=[]),
        _cand("table_01", role="TABLE", display="예산", concepts=["BUDGET", "TABLE"]),
    ]
    out = rank_generic_candidates(cands, intent=intent)
    assert out["ranking_results"]["ranked_node_ids"][0] == "table_01"


def test_virtual_target_wins_only_for_add():
    intent_upd = parse_generic_query_intent("결론을 수정한다")
    virt = _cand(
        "general_report_v1.appendix",
        role="VIRTUAL_TARGET",
        display="부록",
        concepts=[],
        virtual_target=True,
    )
    para = _cand(
        "paragraph_0006",
        role="PARAGRAPH_BODY",
        display="결론",
        concepts=["CONCLUSION"],
        evaluation_equivalent=True,
        alignment_confidence=0.9,
    )
    out_upd = rank_generic_candidates([virt, para], intent=intent_upd)
    assert out_upd["ranking_results"]["ranked_node_ids"][0] == "paragraph_0006"
    assert out_upd["validation"]["virtual_target_only_for_add"] is True


def test_template_section_promoted_for_eval():
    intent = parse_generic_query_intent("결론을 수정한다")
    review = [
        _cand("paragraph_0006", role="PARAGRAPH_BODY", display="결론 내용", concepts=["CONCLUSION"]),
    ]
    template_hits = [
        {
            "node_id": "general_report_v1.conclusion",
            "document_id": "R1",
            "display_name": "결론",
            "status": "REVIEW_REQUIRED",
            "metadata": {"template_only": True},
        }
    ]
    alignments = [
        {
            "template_node_id": "general_report_v1.conclusion",
            "document_node_id": "paragraph_0006",
            "equivalent_for_evaluation": True,
            "confidence": 0.9,
        }
    ]
    out = promote_aligned_template_candidates(
        review=review, template_hits=template_hits, alignments=alignments, intent=intent
    )
    assert any(x["node_id"] == "general_report_v1.conclusion" for x in out)
    ranked = rank_generic_candidates(out, intent=intent)
    assert ranked["ranking_results"]["ranked_node_ids"][0] == "general_report_v1.conclusion"


def test_deterministic_ranking():
    intent = parse_generic_query_intent("결과 수정")
    cands = [
        _cand("paragraph_0002", role="PARAGRAPH_BODY", display="결과 A", concepts=["RESULTS"]),
        _cand("paragraph_0001", role="PARAGRAPH_BODY", display="결과 B", concepts=["RESULTS"]),
    ]
    a = rank_generic_candidates(list(cands), intent=intent)
    b = rank_generic_candidates(list(reversed(cands)), intent=intent)
    assert a["ranking_results"]["ranked_node_ids"] == b["ranking_results"]["ranked_node_ids"]


def test_score_components_present():
    intent = parse_generic_query_intent("방법론 수정")
    s = score_structural_match(
        _cand("paragraph_0002", role="PARAGRAPH_BODY", display="방법론", concepts=["METHODOLOGY"]),
        intent=intent,
    )
    assert s.concept_match >= 0.5
    assert s.to_dict()["candidate_node_id"] == "paragraph_0002"
