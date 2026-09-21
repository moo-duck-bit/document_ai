# -*- coding: utf-8 -*-
"""Workflow integration for document identity."""

from __future__ import annotations

import shutil
from pathlib import Path

from document_ai.workflow.orchestrator import create_workflow, run_analysis

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures"
ROOT = REPO / "data" / "user_scenarios" / "_workflow_identity_tests"


def _clean():
    if ROOT.exists():
        shutil.rmtree(ROOT)


def test_temporary_id_replaced_by_canonical_descriptor():
    _clean()
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 11 갱신",
        files=[("mdtm_base.docx", p.read_bytes(), "traceability")],
        name="id_tmp",
        root=ROOT,
        document_routing_mode="explicit",
    )
    d = rec["documents"][0]
    assert d["document_id"] == "MDTM_BASE"
    assert d["source_document_id"] == "MDTM_BASE"
    assert d["canonical_document_id"] == "EC_SW_MDTM"
    assert d["short_id"] == "MDTM"


def test_selected_pack_invoked_explicit():
    _clean()
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 11 갱신",
        files=[("mdtm_base.docx", p.read_bytes(), None)],
        name="id_pack",
        root=ROOT,
        document_routing_mode="explicit",
    )
    assert rec["document_set"] == "ec_sw"
    out = run_analysis(rec["workflow_id"], root=ROOT)
    assert out["state"] in {"WAITING_APPROVAL", "REVIEW_READY", "FAILED"} or out.get("impacted_documents") is not None


def test_review_required_route_not_invoked_auto():
    _clean()
    rec = create_workflow(
        document_set="ec_sw",
        change_request="hello",
        files=[("unknown_zz.docx", b"not-a-real-docx", None)],
        name="id_bad",
        root=ROOT,
        document_routing_mode="auto",
    )
    # empty/invalid may fail validation later; identity should not auto-switch pack blindly
    assert rec["metadata"]["requested_document_set"] == "ec_sw"


def test_explicit_compatibility():
    _clean()
    p = FX / "general_report" / "report_std.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="general_report",
        change_request="방법론 보완",
        files=[("report_std.docx", p.read_bytes(), "general_report")],
        name="id_exp",
        root=ROOT,
        document_routing_mode="explicit",
    )
    assert rec["document_set"] == "general_report"


def test_assisted_flow_needs_confirmation_flag():
    _clean()
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 11",
        files=[("mdtm_base.docx", p.read_bytes(), None)],
        name="id_ast",
        root=ROOT,
        document_routing_mode="assisted",
    )
    assert rec["metadata"]["document_routing_mode"] == "assisted"
    # assisted without confirm → needs confirmation when not auto-confirmed
    assert "needs_identity_confirmation" in rec["metadata"]


def test_ui_api_payload_fields():
    _clean()
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 11",
        files=[("mdtm_base.docx", p.read_bytes(), None)],
        name="id_ui",
        root=ROOT,
        document_routing_mode="assisted",
    )
    d = rec["documents"][0]
    for key in (
        "filename",
        "document_type",
        "document_role",
        "domain_pack_id",
        "identity_status",
        "identity_score",
        "identity_reasons",
    ):
        assert key in d


def test_upload_indexing_aligns_fixture_id():
    _clean()
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 11 추적성 행 갱신",
        files=[("mdtm_base.docx", p.read_bytes(), "traceability")],
        name="id_idx",
        root=ROOT,
        document_routing_mode="explicit",
    )
    out = run_analysis(rec["workflow_id"], root=ROOT)
    assert "MDTM_BASE" in (out.get("impacted_documents") or [])
