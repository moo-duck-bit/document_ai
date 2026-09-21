# -*- coding: utf-8 -*-
"""Benchmark v1.2 safe-recall regression (no case-id hardcoding in product code)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from document_ai.evaluation.document_set.prediction_adapter import adapt_workflow_prediction
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


def test_semantic_only_document_review_not_missed(tmp_path):
    before = _sha(MDTM)
    rec = create_workflow(
        document_set="ec_sw",
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="sem_reg",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    dec = {d["document_id"]: d for d in out["metadata"]["document_impact_decisions"]}
    assert dec["MDTM"]["predicted_status"] == "REVIEW_REQUIRED"
    assert out["patch_candidates"] == []
    pred = adapt_workflow_prediction(
        "x",
        {**out, "document_impact_decisions": out["metadata"]["document_impact_decisions"]},
    )
    assert any(
        d["document_id"] == "MDTM" and d["predicted_status"] == "REVIEW_REQUIRED"
        for d in pred["documents"]
    )
    assert pred["patches"] == []
    assert _sha(MDTM) == before


def test_schedule_table_document_review_not_missed(tmp_path):
    before = _sha(REPORT)
    rec = create_workflow(
        document_set="general_report",
        change_request="일정 표 수정 2026-Q4",
        files=[("report_base.docx", REPORT.read_bytes(), "general_report")],
        root=tmp_path,
        name="sch_reg",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert out["patch_candidates"] == []
    dec = {d["document_id"]: d for d in out["metadata"]["document_impact_decisions"]}
    assert dec["REPORT_BASE"]["predicted_status"] == "REVIEW_REQUIRED"
    assert _sha(REPORT) == before


def test_exact_req_still_patch(tmp_path):
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 2 행 추적성 갱신",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="exact_reg",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert len(out["patch_candidates"]) >= 1
    assert "MDTM" in out["impacted_documents"]


def test_no_product_case_id_hardcode():
    root = REPO / "src" / "document_ai"
    forbidden = ["ec_sw_semantic_only", "gr_schedule_table"]
    for rel in (
        "domain_packs/ec_sw/semantic_evidence.py",
        "document_set/schedule_table_retrieval.py",
        "template/concept_normalization.py",
        "workflow/analysis.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        for tok in forbidden:
            assert tok not in text


def test_writer_not_expanded_on_semantic(tmp_path):
    from document_ai.workflow.orchestrator import approve_workflow, run_writer

    rec = create_workflow(
        document_set="ec_sw",
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="wr",
    )
    wid = rec["workflow_id"]
    run_analysis(wid, root=tmp_path)
    approve_workflow(wid, approve_all_pending=True, root=tmp_path)
    out = run_writer(wid, enable_write=False, root=tmp_path)
    wr = out["workflow"]["writer_result"]
    assert wr.get("controlled_writer_invoked") is False
    assert int(wr.get("applied") or 0) == 0


def test_semantic_artifacts_written(tmp_path):
    rec = create_workflow(
        document_set="ec_sw",
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="sem_art",
    )
    run_analysis(rec["workflow_id"], root=tmp_path)
    ec = tmp_path / rec["workflow_id"] / "output" / "document_set" / "ec_sw"
    assert (ec / "ec_sw_semantic_review_evidence.json").is_file()
    assert (ec / "ec_sw_semantic_review_validation.json").is_file()


def test_schedule_artifacts_written(tmp_path):
    rec = create_workflow(
        document_set="general_report",
        change_request="일정 표 수정 2026-Q4",
        files=[("report_base.docx", REPORT.read_bytes(), "general_report")],
        root=tmp_path,
        name="sch_art",
    )
    run_analysis(rec["workflow_id"], root=tmp_path)
    gr = tmp_path / rec["workflow_id"] / "output" / "document_set" / "general_report"
    assert (gr / "general_report_schedule_review.json").is_file()
    assert (gr / "general_report_retrieval_validation.json").is_file()


def test_gr_no_impact_stays_unrelated(tmp_path):
    rec = create_workflow(
        document_set="general_report",
        change_request="사무실 화분 배치 변경 XYZABC",
        files=[("report_base.docx", REPORT.read_bytes(), "general_report")],
        root=tmp_path,
        name="noi",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert out["impacted_documents"] == []
    assert out["patch_candidates"] == []


def test_prediction_adapter_no_gold_read():
    import inspect
    from document_ai.evaluation.document_set import prediction_adapter as pa

    src = inspect.getsource(pa)
    assert "document_impacts.jsonl" not in src
    assert "load_benchmark_manifest" not in src
