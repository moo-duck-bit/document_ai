# -*- coding: utf-8 -*-
"""PR-21: Generic Template Semantic Locator Engine tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from document_ai.document_parser.parser import run_document_structure_mapping_engine
from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.semantic_locator.locator import (
    load_generic_node_candidates,
    run_semantic_locator_engine,
    sample_locator_inputs,
)
from document_ai.semantic_locator.ranking import build_match_results, score_all_nodes
from document_ai.semantic_locator.rule_matcher import compute_rule_score
from document_ai.semantic_locator.schema import SemanticLocatorInput, SemanticMatchResult
from document_ai.semantic_locator.score_fusion import fuse_scores
from document_ai.semantic_locator.semantic_matcher import compute_semantic_score
from document_ai.semantic_locator.text_normalization import normalize_text, tokenize
from document_ai.semantic_locator.thresholds import DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from document_ai.semantic_locator.validation import validate_semantic_locator
from document_ai.template.generic_mapping import run_generic_document_template_pack
from document_ai.template.inventory import run_template_abstraction_layer

REPO = Path(__file__).resolve().parents[1]
FROZEN = [
    REPO / "data/user_scenarios/scenario-001",
    REPO / "data/trials/trial-001-mindrium-xa",
    REPO / "data/trials/trial-002-lockout-multireq",
]


def _by_id(pkg):
    return {r["locator_candidate_id"]: r for r in pkg["ranked_matches"]}


def test_01_exact_heading_path_match():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    r = _by_id(pkg)["LC-SAMPLE-001"]
    assert r["match_status"] == "MATCHED"
    assert r["template_node_id"] == "general_report_v1.methodology.data_sources"
    assert "HEADING_PATH_MATCH" in r["reason_codes"]


def test_02_execution_plan_schedule_match():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    r = _by_id(pkg)["LC-SAMPLE-002"]
    assert r["match_status"] == "MATCHED"
    assert r["template_node_id"] == "business_proposal_v1.execution_plan.schedule"


def test_03_results_heading_review():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    r = _by_id(pkg)["LC-SAMPLE-003"]
    assert r["match_status"] == "REVIEW"
    assert "AMBIGUOUS_TOP_MATCH" in r["reason_codes"] or r["ambiguity_status"] == "AMBIGUOUS"


def test_04_schedule_heading_review():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    r = _by_id(pkg)["LC-SAMPLE-004"]
    assert r["match_status"] == "REVIEW"


def test_05_unknown_section_unmapped():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    r = _by_id(pkg)["LC-SAMPLE-005"]
    assert r["match_status"] == "UNMAPPED"
    assert r["template_node_id"] is None


def test_06_normalize_korean():
    assert normalize_text("  데이터_출처 (내부)  ") == "데이터 출처"


def test_07_normalize_english():
    assert normalize_text("Data-Sources!!!") == "data sources"


def test_08_tokenize():
    assert "방법론" in tokenize("방법론 데이터 출처")


def test_09_exact_heading_text_match():
    nodes = load_generic_node_candidates(template_ids={"general_report_v1"})
    node = next(n for n in nodes if n.template_node_id.endswith(".methodology.data_sources"))
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-X",
        template_id="general_report_v1",
        heading_text="데이터 출처",
        section_name="데이터 출처",
        field_label="데이터 출처",
        heading_path=["방법론", "데이터 출처"],
    )
    score, reasons, _ = compute_rule_score(inp, node)
    assert score >= 0.8
    assert "HEADING_TEXT_MATCH" in reasons or "FIELD_LABEL_MATCH" in reasons


def test_10_field_label_match():
    nodes = load_generic_node_candidates(template_ids={"general_report_v1"})
    node = next(n for n in nodes if n.field_id == "data_sources")
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-L",
        template_id="general_report_v1",
        field_label="데이터 출처",
        heading_text="",
        heading_path=[],
    )
    _, reasons, comp = compute_rule_score(inp, node)
    assert "FIELD_LABEL_MATCH" in reasons
    assert comp["field_label"] >= 0.85


def test_11_token_similarity():
    nodes = load_generic_node_candidates(template_ids={"general_report_v1"})
    node = next(n for n in nodes if n.field_id == "data_sources")
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-T",
        candidate_text="methodology data sources approach",
        heading_text="data sources",
        heading_path=["methodology", "data sources"],
        template_id="general_report_v1",
    )
    score, _, comp = compute_semantic_score(inp, node)
    assert score > 0
    assert comp["token_overlap"] >= 0


def test_12_char_ngram_similarity():
    nodes = load_generic_node_candidates(template_ids={"business_proposal_v1"})
    node = next(
        n for n in nodes if n.template_node_id.endswith("execution_plan.schedule")
    )
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-N",
        heading_path=["수행 계획", "일정"],
        heading_text="일정",
        candidate_text="수행계획 일정",
        template_id="business_proposal_v1",
    )
    _, _, comp = compute_semantic_score(inp, node)
    assert comp["char_ngram_cosine"] > 0


def test_13_combined_score_weights():
    assert DEFAULT_WEIGHTS.rule_weight == 0.65
    assert DEFAULT_WEIGHTS.semantic_weight == 0.35
    assert fuse_scores(1.0, 0.0) == 0.65
    assert fuse_scores(0.0, 1.0) == 0.35


def test_14_deterministic_ranking():
    a = run_semantic_locator_engine()
    b = run_semantic_locator_engine()
    assert json.dumps(a["ranked_matches"], sort_keys=True) == json.dumps(
        b["ranked_matches"], sort_keys=True
    )
    assert json.dumps(a["match_results"], sort_keys=True) == json.dumps(
        b["match_results"], sort_keys=True
    )


def test_15_template_constrained_search():
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-C",
        template_id="general_report_v1",
        heading_path=["방법론", "데이터 출처"],
        heading_text="데이터 출처",
        field_label="데이터 출처",
    )
    nodes = load_generic_node_candidates()
    rows = score_all_nodes(
        inp, [n for n in nodes if n.template_id == "general_report_v1"]
    )
    assert all(r["node"].template_id == "general_report_v1" for r in rows)


def test_16_cross_template_search():
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-CROSS",
        template_id=None,
        heading_path=["방법론", "데이터 출처"],
        heading_text="데이터 출처",
        field_label="데이터 출처",
        candidate_text="방법론 데이터 출처",
    )
    results = build_match_results(inp, load_generic_node_candidates(), match_seq=99)
    assert results[0].rank == 1
    assert results[0].template_id in ("general_report_v1", "business_proposal_v1")


def test_17_requirement_id_null_ok():
    nodes = load_generic_node_candidates()
    assert all(n.source_requirement_id is None for n in nodes)
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    matched = [r for r in pkg["ranked_matches"] if r["match_status"] == "MATCHED"]
    assert matched
    assert "GENERIC_REQUIREMENT_ID_OPTIONAL" in matched[0]["reason_codes"]


def test_18_ambiguous_small_margin():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    r = _by_id(pkg)["LC-SAMPLE-003"]
    assert r["score_margin"] is not None
    assert r["score_margin"] < DEFAULT_THRESHOLDS.score_margin_min


def test_19_load_nodes_both_templates():
    nodes = load_generic_node_candidates()
    tids = {n.template_id for n in nodes}
    assert tids == {"general_report_v1", "business_proposal_v1"}
    assert len(nodes) > 10


def test_20_summary_fields():
    s = run_semantic_locator_engine(emit_all_ranks=False)["summary"]
    for k in (
        "input_count",
        "matched_count",
        "review_count",
        "unmapped_count",
        "invalid_count",
        "average_combined_score",
        "global_semantic_locator_status",
    ):
        assert k in s
    assert s["actual_docx_changed"] is False
    assert s["global_semantic_locator_status"] == "REVIEW"


def test_21_validation_valid():
    pkg = run_semantic_locator_engine()
    assert pkg["validation"]["status"] == "VALID"
    assert pkg["validation"]["invariants"]["no_llm"] is True
    assert pkg["validation"]["invariants"]["no_remote_embedding"] is True


def test_22_negative_unknown_template():
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-BAD-T",
        template_id="not_a_template",
        heading_text="x",
    )
    results = build_match_results(inp, load_generic_node_candidates(), match_seq=1)
    assert results[0].match_status == "INVALID"
    assert "TEMPLATE_NOT_FOUND" in results[0].reason_codes


def test_23_negative_invalid_input():
    inp = SemanticLocatorInput(document_id="", locator_candidate_id="")
    results = build_match_results(inp, load_generic_node_candidates(), match_seq=2)
    assert results[0].match_status == "INVALID"
    assert "INVALID_LOCATOR_INPUT" in results[0].reason_codes


def test_24_negative_invalid_node_ref_detected():
    nodes = load_generic_node_candidates(template_ids={"general_report_v1"})
    fake = SemanticMatchResult(
        semantic_match_id="SM-FAKE-001",
        document_id="d",
        locator_candidate_id="LC-SAMPLE-001",
        template_id="general_report_v1",
        template_node_id="general_report_v1.no.such",
        rule_score=0.9,
        semantic_score=0.9,
        combined_score=0.9,
        rank=1,
        match_status="MATCHED",
    )
    v = validate_semantic_locator(
        results=[fake],
        nodes=nodes,
        input_ids={"LC-SAMPLE-001"},
        summary=None,
    )
    assert any("invalid_node_ref" in i for i in v["issues"])


def test_25_negative_score_out_of_range():
    nodes = load_generic_node_candidates(template_ids={"general_report_v1"})
    bad = SemanticMatchResult(
        semantic_match_id="SM-BAD-001",
        document_id="d",
        locator_candidate_id="LC-SAMPLE-001",
        template_id="general_report_v1",
        template_node_id=nodes[0].template_node_id,
        rule_score=1.5,
        semantic_score=0.1,
        combined_score=0.5,
        rank=1,
        match_status="MATCHED",
    )
    v = validate_semantic_locator(
        results=[bad], nodes=nodes, input_ids={"LC-SAMPLE-001"}
    )
    assert any("score_out_of_range" in i for i in v["issues"])


def test_26_negative_duplicate_match_id():
    nodes = load_generic_node_candidates(template_ids={"general_report_v1"})
    r = SemanticMatchResult(
        semantic_match_id="SM-DUP",
        document_id="d",
        locator_candidate_id="LC-A",
        template_id="general_report_v1",
        template_node_id=nodes[0].template_node_id,
        rule_score=0.5,
        semantic_score=0.5,
        combined_score=0.5,
        rank=1,
        match_status="REVIEW",
    )
    v = validate_semantic_locator(
        results=[r, copy.deepcopy(r)], nodes=nodes, input_ids={"LC-A"}
    )
    assert "duplicate_semantic_match_id" in v["issues"]


def test_27_negative_broken_rank():
    nodes = load_generic_node_candidates(template_ids={"general_report_v1"})
    a = SemanticMatchResult(
        semantic_match_id="SM-R1",
        document_id="d",
        locator_candidate_id="LC-R",
        template_id="general_report_v1",
        template_node_id=nodes[0].template_node_id,
        rule_score=0.9,
        semantic_score=0.9,
        combined_score=0.9,
        rank=1,
        match_status="MATCHED",
    )
    b = SemanticMatchResult(
        semantic_match_id="SM-R3",
        document_id="d",
        locator_candidate_id="LC-R",
        template_id="general_report_v1",
        template_node_id=nodes[1].template_node_id,
        rule_score=0.8,
        semantic_score=0.8,
        combined_score=0.8,
        rank=3,
        match_status="REVIEW",
    )
    v = validate_semantic_locator(results=[a, b], nodes=nodes, input_ids={"LC-R"})
    assert any("broken_rank_sequence" in i for i in v["issues"])


def test_28_negative_summary_tamper():
    from document_ai.semantic_locator.ranking import build_match_results as bmr

    inputs = sample_locator_inputs()
    nodes = load_generic_node_candidates()
    all_r = []
    for i, inp in enumerate(inputs, start=1):
        all_r.extend([x for x in bmr(inp, nodes, match_seq=i) if x.rank == 1])
    pkg2 = run_semantic_locator_engine(emit_all_ranks=False)
    bad_summary = dict(pkg2["summary"])
    bad_summary["matched_count"] = 999
    v = validate_semantic_locator(
        results=all_r,
        nodes=nodes,
        input_ids={i.locator_candidate_id for i in inputs},
        summary=bad_summary,
    )
    assert any("summary_" in i for i in v["issues"])


def test_29_no_candidates():
    inp = SemanticLocatorInput(
        document_id="d",
        locator_candidate_id="LC-EMPTY",
        template_id="general_report_v1",
        heading_text="x",
    )
    results = build_match_results(inp, [], match_seq=7)
    assert results[0].match_status in ("UNMAPPED", "INVALID")
    assert (
        "NO_CANDIDATES" in results[0].reason_codes
        or "NODE_NOT_FOUND" in results[0].reason_codes
    )


def test_30_pr18_regression():
    items = [
        {
            "review_item_id": "CRI-RP-1",
            "patch_id": "RP-1",
            "document": "MDSR",
            "requirement_id": "Req. 105",
            "field": "criteria",
            "change_type": "UPDATE",
            "review_status": "READY",
            "acu_id": "ACU-001",
        }
    ]
    snap = copy.deepcopy(items)
    a = run_template_abstraction_layer(review_items=items)
    _ = run_semantic_locator_engine()
    b = run_template_abstraction_layer(review_items=items)
    assert items == snap
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_31_pr19_regression():
    a = run_generic_document_template_pack()
    _ = run_semantic_locator_engine()
    b = run_generic_document_template_pack()
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_32_pr20_regression():
    kwargs = {
        "markdown_texts": [
            {
                "text": "# T\n\n## A\n\nx\n",
                "document_id": "pr20",
                "document_type": "general_report",
            }
        ],
        "objects": [],
    }
    a = run_document_structure_mapping_engine(**kwargs)
    _ = run_semantic_locator_engine()
    b = run_document_structure_mapping_engine(**kwargs)
    assert a["summary"]["section_count"] == b["summary"]["section_count"]


def test_33_docx_flag_off_and_freeze():
    assert is_docx_activation_enabled(env={}) is False
    pkg = run_semantic_locator_engine()
    assert pkg["actual_docx_changed"] is False
    assert pkg["actual_generation_changed"] is False
    for p in FROZEN:
        assert p.exists()


def test_34_evidence_present():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    r = _by_id(pkg)["LC-SAMPLE-001"]
    ev = r["evidence"]
    assert "rule_components" in ev
    assert "semantic_components" in ev
    assert "matched_heading_path" in ev


def test_35_thresholds_module():
    assert DEFAULT_THRESHOLDS.matched_min == 0.80
    assert DEFAULT_THRESHOLDS.review_min == 0.55


def test_36_validation_vs_global_status_distinction():
    pkg = run_semantic_locator_engine(emit_all_ranks=False)
    assert pkg["validation"]["status"] == "VALID"
    assert pkg["summary"]["global_semantic_locator_status"] == "REVIEW"


def test_37_sample_inputs_count():
    assert len(sample_locator_inputs()) == 5
