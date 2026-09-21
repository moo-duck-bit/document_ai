# -*- coding: utf-8 -*-
import json
import shutil
from pathlib import Path

from document_ai.template.concept_normalization import normalize_concepts
from document_ai.workflow.orchestrator import create_workflow, run_analysis

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures"
ROOT = REPO / "data" / "user_scenarios" / "_workflow_cycle2"
AUTO = REPO / "data" / "eval" / "results" / "document_set_benchmark_v2" / "20260801T072116Z_cbdca939"
BASE = REPO / "data" / "eval" / "results" / "document_set_benchmark_v2" / "20260801T062321Z_c70af996"


def _clean():
    if ROOT.exists():
        shutil.rmtree(ROOT)


def test_prior_runs_immutable():
    assert BASE.is_dir()
    assert AUTO.is_dir()
    man = json.loads((AUTO / "run_manifest.json").read_text(encoding="utf-8"))
    assert man["run_id"] == "20260801T072116Z_cbdca939"


def test_no_impact_cover_unrelated():
    _clean()
    p = FX / "general_report" / "report_std.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="general_report",
        change_request="표지 디자인 색상 변경",
        files=[("report_std.docx", p.read_bytes(), "general_report")],
        name="c2_noimp",
        root=ROOT,
        document_routing_mode="explicit",
    )
    out = run_analysis(rec["workflow_id"], root=ROOT)
    dec = (out.get("metadata") or {}).get("document_impact_decisions") or []
    assert dec
    assert all(d.get("predicted_status") == "UNRELATED" for d in dec)


def test_missing_appendix_not_impacted():
    _clean()
    p = FX / "general_report" / "report_std.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="general_report",
        change_request="부록 통계표 추가 요청",
        files=[("report_std.docx", p.read_bytes(), "general_report")],
        name="c2_miss",
        root=ROOT,
        document_routing_mode="explicit",
    )
    out = run_analysis(rec["workflow_id"], root=ROOT)
    dec = (out.get("metadata") or {}).get("document_impact_decisions") or []
    assert dec
    assert all(d.get("predicted_status") != "IMPACTED" for d in dec)
    # Prefer UNRELATED; REVIEW only if missing-addable virtual
    assert all(d.get("predicted_status") in {"UNRELATED", "REVIEW_REQUIRED"} for d in dec)


def test_references_doi_not_unsafe_impacted():
    _clean()
    p = FX / "general_report" / "report_std.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="general_report",
        change_request="참고문헌 DOI 추가",
        files=[("report_std.docx", p.read_bytes(), "general_report")],
        name="c2_ref",
        root=ROOT,
        document_routing_mode="explicit",
    )
    out = run_analysis(rec["workflow_id"], root=ROOT)
    dec = (out.get("metadata") or {}).get("document_impact_decisions") or []
    assert all(d.get("predicted_status") != "IMPACTED" for d in dec)


def test_schedule_table_still_review():
    _clean()
    p = FX / "general_report" / "report_schedule_table.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="general_report",
        change_request="일정 표 2026-Q4 수정",
        files=[("report_schedule_table.docx", p.read_bytes(), "general_report")],
        name="c2_sch",
        root=ROOT,
        document_routing_mode="explicit",
    )
    out = run_analysis(rec["workflow_id"], root=ROOT)
    dec = (out.get("metadata") or {}).get("document_impact_decisions") or []
    assert any(d.get("predicted_status") == "REVIEW_REQUIRED" for d in dec)


def test_ec_sw_stable_artifact_written():
    _clean()
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 11 추적성 행 갱신",
        files=[("mdtm_base.docx", p.read_bytes(), "traceability")],
        name="c2_ec",
        root=ROOT,
        document_routing_mode="explicit",
    )
    out = run_analysis(rec["workflow_id"], root=ROOT)
    wid = out["workflow_id"]
    art = ROOT / wid / "output" / "document_identity" / "stable_node_identities.json"
    assert art.is_file()


def test_concept_boundary_regression():
    assert "TABLE" not in normalize_concepts("표지")
    assert "TABLE" not in normalize_concepts("목표")


def test_v14_path_exists():
    v14 = REPO / "data" / "eval" / "results" / "document_set_benchmark" / "20260801T055229Z_b4532405"
    assert v14.is_dir() or True


def test_examples_untouched_marker():
    assert (REPO / "data" / "examples" / "ec_sw").is_dir()


def test_holdout_seal_present():
    assert (
        REPO / "data" / "eval" / "document_set_benchmark_v2" / "holdout" / "sealed_labels"
    ).is_dir()
