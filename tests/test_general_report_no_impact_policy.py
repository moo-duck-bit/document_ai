# -*- coding: utf-8 -*-
from document_ai.domain_packs.generic.no_impact_policy import ImpactEvidence, decide_no_impact
from document_ai.domain_packs.generic.target_existence import decide_target_existence


def test_unrelated_request_unrelated():
    t = decide_target_existence(
        document_id="D1",
        requested_concepts={"AUTHENTICATION"},
        document_heading_concepts={"SCHEDULE"},
        cr_tokens={"인증"},
        document_heading_tokens={"일정"},
    )
    d = decide_no_impact(document_id="D1", evidences=[], target=t)
    assert d.status == "UNRELATED"


def test_document_presence_only_unrelated():
    ev = [ImpactEvidence(evidence_type="DOCUMENT_PRESENCE", evidence_value="x.docx")]
    d = decide_no_impact(document_id="D1", evidences=ev, target=None)
    assert d.status == "UNRELATED"
    assert d.validation["no_presence_only_impacted"]


def test_template_compatibility_only_unrelated():
    ev = [ImpactEvidence(evidence_type="TEMPLATE_COMPATIBILITY", evidence_value="general_report")]
    d = decide_no_impact(document_id="D1", evidences=ev, target=None)
    assert d.status == "UNRELATED"
    assert d.validation["no_template_compatibility_only_impacted"]


def test_exact_section_review_or_impacted():
    ev = [
        ImpactEvidence(
            evidence_type="EXACT_HEADING_MATCH",
            evidence_value="방법론",
            node_id="paragraph_0003",
            supports_impacted=True,
            supports_review=True,
        )
    ]
    t = decide_target_existence(
        document_id="D1",
        requested_concepts=set(),
        document_node_hits=[{"node_id": "paragraph_0003", "status": "REVIEW_REQUIRED"}],
    )
    d = decide_no_impact(document_id="D1", evidences=ev, target=t)
    assert d.status in {"IMPACTED", "REVIEW_REQUIRED"}
    assert d.substantive_evidence_count >= 1


def test_semantic_section_review_no_patch():
    ev = [
        ImpactEvidence(
            evidence_type="SEMANTIC_SECTION_MATCH",
            evidence_value="results",
            node_id="paragraph_0001",
            supports_review=True,
        )
    ]
    t = decide_target_existence(
        document_id="D1",
        requested_concepts={"TABLE"},
        document_heading_concepts={"TABLE"},
    )
    d = decide_no_impact(document_id="D1", evidences=ev, target=t)
    assert d.status == "REVIEW_REQUIRED"


def test_missing_addable_review():
    t = decide_target_existence(
        document_id="D1",
        requested_concepts=set(),
        cr_tokens={"참고문헌", "doi"},
        template_section_hits=[
            {
                "status": "REVIEW_REQUIRED",
                "node_id": "general_report_v1.references",
                "display_name": "참고문헌",
            }
        ],
    )
    assert t.target_status == "MISSING_ADDABLE"
    d = decide_no_impact(document_id="D1", evidences=[], target=t)
    # Writer-unsupported ADD → document stays UNRELATED (safe); virtual target recorded
    assert d.status == "UNRELATED"
    assert d.virtual_targets
    assert d.virtual_targets[0]["writer_supported"] is False
    assert d.virtual_targets[0]["human_review_required"] is True


def test_missing_unsupported_not_impacted():
    t = decide_target_existence(
        document_id="D1",
        requested_concepts={"TABLE"},
        template_section_hits=[
            {"status": "REVIEW_REQUIRED", "node_id": "general_report_v1.unknown_zz", "display_name": "x"}
        ],
    )
    assert t.target_status == "MISSING_UNSUPPORTED"
    d = decide_no_impact(document_id="D1", evidences=[], target=t)
    assert d.status == "UNRELATED"
    assert d.validation["missing_unsupported_not_impacted"]


def test_no_impact_no_writer_candidate_flag():
    t = decide_target_existence(document_id="D1", requested_concepts=set(), cr_tokens={"표지", "색상"})
    d = decide_no_impact(
        document_id="D1",
        evidences=[ImpactEvidence(evidence_type="DOCUMENT_PRESENCE", evidence_value="a")],
        target=t,
    )
    assert d.status == "UNRELATED"
    assert not any(v.get("writer_supported") for v in d.virtual_targets)


def test_generic_fallback_does_not_impact():
    ev = [
        ImpactEvidence(evidence_type="DOCUMENT_PRESENCE", evidence_value="a"),
        ImpactEvidence(evidence_type="TEMPLATE_COMPATIBILITY", evidence_value="gr"),
        ImpactEvidence(evidence_type="DOCUMENT_LEVEL_CONCEPT_MATCH", evidence_value="schedule"),
    ]
    d = decide_no_impact(document_id="D1", evidences=ev, target=None)
    assert d.status != "IMPACTED"


def test_표지_not_table_concept():
    from document_ai.template.concept_normalization import normalize_concepts

    assert "TABLE" not in normalize_concepts("표지 디자인 색상 변경")
    assert "TABLE" not in normalize_concepts("목표 설정")
    assert "TABLE" in normalize_concepts("통계표 추가") or "TABLE" in normalize_concepts("일정표 수정")
