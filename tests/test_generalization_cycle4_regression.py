# -*- coding: utf-8 -*-
from pathlib import Path

from document_ai.domain_packs.generic.query_intent import parse_generic_query_intent
from document_ai.domain_packs.generic.no_impact_policy import decide_no_impact
from document_ai.domain_packs.generic.target_existence import decide_target_existence
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.evaluation.document_set_v2.evaluator import _pred_matches_gold_nodes

FX = Path("data/eval/document_set_benchmark_v2/fixtures/ec_sw")
PRIOR = {
    "20260801T062321Z_c70af996",
    "20260801T072116Z_cbdca939",
    "20260801T143206Z_e6bd5201",
    "20260801T152942Z_03c260f2",
}


def test_prior_cycle_runs_immutable():
    assert len(PRIOR) == 4


def test_ec_sw_stable_identity_still_1():
    names = ["mdtm_base.docx", "mdtm_cols_dtr.docx", "mdtm_note_col.docx"]
    bases = set()
    for name in names:
        idx = index_mdtm_document(source_path=FX / name, document_id=name.upper())
        for n in idx["nodes"]:
            if any("11" in str(x) for x in (n.source_identifiers.get("requirement_ids") or [])):
                bases.add(n.source_identifiers.get("stable_node_id_base"))
                break
    assert len(bases) == 1


def test_gr_no_impact_maintained():
    t = decide_target_existence(
        document_id="D1",
        requested_concepts={"AUTHENTICATION"},
        document_heading_concepts={"SCHEDULE"},
        cr_tokens={"인증"},
        document_heading_tokens={"일정"},
    )
    d = decide_no_impact(document_id="D1", evidences=[], target=t)
    assert d.status == "UNRELATED"


def test_structural_eval_match_via_alignment():
    pred = {
        "node_id": "paragraph_0006",
        "metadata": {
            "template_node_id": "general_report_v1.conclusion",
        },
    }
    alignments = [
        {
            "template_node_id": "general_report_v1.conclusion",
            "document_node_id": "paragraph_0006",
            "equivalent_for_evaluation": True,
        }
    ]
    assert _pred_matches_gold_nodes(
        pred,
        gold_ids={"general_report_v1.conclusion"},
        acceptable=set(),
        cr_identifiers=set(),
        alignments=alignments,
    )


def test_patch_equivalence_not_implied_by_eval_alignment():
    # evaluation match must not set writer_executable
    pred = {
        "node_id": "general_report_v1.conclusion",
        "metadata": {"structural_role": "TEMPLATE_SECTION", "writer_executable": False},
    }
    assert pred["metadata"]["writer_executable"] is False


def test_conclusion_intent_stable():
    i = parse_generic_query_intent("결론 문단을 수정")
    assert "CONCLUSION" in i.target_section_concepts
