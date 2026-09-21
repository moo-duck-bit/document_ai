# -*- coding: utf-8 -*-
from document_ai.domain_packs.generic.target_existence import decide_target_existence


def test_exists_exact_from_doc_nodes():
    t = decide_target_existence(
        document_id="D",
        requested_concepts=set(),
        document_node_hits=[{"node_id": "paragraph_0001"}],
    )
    assert t.target_status == "EXISTS_EXACT"
    assert t.target_exists is True


def test_exists_semantic_heading_concepts():
    t = decide_target_existence(
        document_id="D",
        requested_concepts={"SCHEDULE"},
        document_heading_concepts={"SCHEDULE", "TABLE"},
    )
    assert t.target_status == "EXISTS_SEMANTIC"


def test_missing_addable_references():
    t = decide_target_existence(
        document_id="D",
        requested_concepts=set(),
        cr_tokens={"참고문헌"},
        template_section_hits=[
            {"status": "REVIEW_REQUIRED", "node_id": "general_report_v1.references"}
        ],
    )
    assert t.target_status == "MISSING_ADDABLE"
    assert t.virtual_target is True
    assert t.writer_supported is False


def test_unrelated_no_evidence():
    t = decide_target_existence(
        document_id="D",
        requested_concepts={"AUTHENTICATION"},
        document_heading_concepts={"SCHEDULE"},
        cr_tokens={"로그인"},
        document_heading_tokens={"일정"},
    )
    assert t.target_status == "UNRELATED"


def test_schedule_document_grounded():
    t = decide_target_existence(
        document_id="D",
        requested_concepts={"SCHEDULE"},
        schedule_document_grounded=True,
    )
    assert t.target_exists is True


def test_ambiguous_token_overlap():
    t = decide_target_existence(
        document_id="D",
        requested_concepts=set(),
        cr_tokens={"방법론", "데이터"},
        document_heading_tokens={"방법론", "결과", "데이터"},
    )
    assert t.target_status == "EXISTS_SEMANTIC"
