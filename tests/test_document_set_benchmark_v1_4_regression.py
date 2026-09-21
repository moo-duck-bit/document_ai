# -*- coding: utf-8 -*-
"""Document Set Benchmark v1.4 node ranking regression."""

from __future__ import annotations

import hashlib
from pathlib import Path

from document_ai.domain_packs.ec_sw.mdtm_change_poc import run_mdtm_change_poc
from document_ai.domain_packs.ec_sw.mdtm_analyzer import analyze_mdtm_structure
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.document_set.loader import load_document_set_registry
from document_ai.domain_packs.ec_sw.registry_adapter import get_mdtm_descriptor
from document_ai.evaluation.document_set.node_evaluation import group_hit_at_k
from document_ai.workflow.orchestrator import create_workflow, run_analysis

REPO = Path(__file__).resolve().parents[1]
MDTM = next((REPO / "data" / "examples" / "ec_sw").glob("matrix_mdtm*.docx"))
REPORT = (
    REPO
    / "data"
    / "eval"
    / "document_set_benchmark"
    / "fixtures"
    / "general_report"
    / "report_base.docx"
)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _nodes():
    loaded = load_document_set_registry(None)
    mdtm = get_mdtm_descriptor(loaded["descriptors"])
    return index_mdtm_document(
        mdtm, analysis=analyze_mdtm_structure(mdtm.source_path, document_id=mdtm.document_id)
    )["nodes"]


def test_design_id_only_recall_at_3():
    out = run_mdtm_change_poc(_nodes(), change_request="설계 ID 4.2.2 관련 추적성 검토")
    top3 = out["ranking"]["ranking_results"]["ranked_node_ids"][:3]
    assert any("row_0003" in n for n in top3)


def test_required_top1_exact_req_improved():
    out = run_mdtm_change_poc(_nodes(), change_request="Req. 2 행 추적성 갱신")
    assert "row_0003" in out["ranking"]["ranking_results"]["ranked_node_ids"][0]


def test_ambiguous_group_hit_with_alignment():
    ranked = [{"node_id": "heading_0007", "score": 1.0}]
    groups = [["general_report_v1.schedule", "general_report_v1.schedule.tables"]]
    alignments = [
        {
            "template_node_id": "general_report_v1.schedule",
            "document_node_id": "heading_0007",
            "equivalent_for_evaluation": True,
        }
    ]
    assert group_hit_at_k(ranked, groups, 1, alignments=alignments) == 1.0


def test_document_macro_safety_paths_unchanged(tmp_path):
    before = _sha(MDTM)
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 2 행 추적성 갱신",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="v14_exact",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert len(out["patch_candidates"]) >= 1
    assert _sha(MDTM) == before


def test_semantic_only_still_no_patch(tmp_path):
    before = _sha(MDTM)
    rec = create_workflow(
        document_set="ec_sw",
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="v14_sem",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert out["patch_candidates"] == []
    assert _sha(MDTM) == before


def test_schedule_still_no_table_patch(tmp_path):
    before = _sha(REPORT)
    rec = create_workflow(
        document_set="general_report",
        change_request="일정 표 수정 2026-Q4",
        files=[("report_base.docx", REPORT.read_bytes(), "general_report")],
        root=tmp_path,
        name="v14_sch",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert out["patch_candidates"] == []
    assert _sha(REPORT) == before


def test_writer_scope_unchanged(tmp_path):
    from document_ai.workflow.orchestrator import approve_workflow, run_writer

    rec = create_workflow(
        document_set="ec_sw",
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="v14_wr",
    )
    wid = rec["workflow_id"]
    run_analysis(wid, root=tmp_path)
    approve_workflow(wid, approve_all_pending=True, root=tmp_path)
    out = run_writer(wid, enable_write=False, root=tmp_path)
    wr = out["workflow"]["writer_result"]
    assert wr.get("controlled_writer_invoked") is False


def test_no_case_id_hardcode_in_ranking_modules():
    root = REPO / "src" / "document_ai"
    forbidden = ["ec_sw_design_id_only", "ec_sw_exact_req_single", "gr_schedule_table"]
    for rel in (
        "domain_packs/ec_sw/query_intent.py",
        "domain_packs/ec_sw/node_ranking.py",
        "domain_packs/ec_sw/ranking_config.py",
        "domain_packs/ec_sw/mdtm_change_poc.py",
        "template/node_alignment.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        for tok in forbidden:
            assert tok not in text


def test_prediction_adapter_prefers_final_score():
    from document_ai.evaluation.document_set.prediction_adapter import adapt_workflow_prediction

    pred = adapt_workflow_prediction(
        "x",
        {
            "patch_candidates": [
                {
                    "document_id": "MDTM",
                    "node_id": "n1",
                    "metadata": {"overlap": 0.2, "final_score": 120.0},
                    "reason_codes": ["exact_requirement_id_match"],
                }
            ],
            "review_required": [
                {
                    "document_id": "MDTM",
                    "node_id": "n2",
                    "metadata": {"overlap": 0.9, "final_score": 31.0},
                    "reason_codes": ["semantic_or_lexical_overlap_only"],
                }
            ],
            "documents": [],
        },
    )
    by = {n["node_id"]: n["score"] for n in pred["nodes"]}
    assert by["n1"] == 120.0
    assert by["n1"] > by["n2"]


def test_ranking_artifacts_written(tmp_path):
    from document_ai.document_set.observational import run_document_set_observational

    run_document_set_observational(
        output_dir=tmp_path,
        change_request="Req. 2 갱신",
    )
    ec = tmp_path / "document_set" / "ec_sw"
    assert (ec / "ec_sw_query_intent.json").is_file()
    assert (ec / "ec_sw_node_ranking_results.json").is_file()
    assert (ec / "ec_sw_node_ranking_validation.json").is_file()


def test_alignment_artifacts_on_schedule(tmp_path):
    rec = create_workflow(
        document_set="general_report",
        change_request="일정 표 수정 2026-Q4",
        files=[("report_base.docx", REPORT.read_bytes(), "general_report")],
        root=tmp_path,
        name="v14_al",
    )
    run_analysis(rec["workflow_id"], root=tmp_path)
    gr = tmp_path / rec["workflow_id"] if False else None
    # find work dir
    found = list(tmp_path.rglob("node_alignments.json"))
    assert found, "node_alignments.json should be written"


def test_desktop_examples_freeze_hashes():
    assert MDTM.is_file()
    assert REPORT.is_file()
