# -*- coding: utf-8 -*-
"""Tests for paper-blocking modules: Field F1, Document-TNR, C1, dual-mode, ablation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.document_set.dependency_graph import (
    DependencyGraph,
    build_graph_from_relation_hints,
    build_graph_from_req_design_links,
    closure,
    selective_sets,
)
from document_ai.document_set.schema import DocumentNode, RelationHint
from document_ai.eval.field_f1 import (
    evaluate_case_field_f1,
    evaluate_many,
    exact_match_f1,
    load_golden_jsonl,
    set_f1,
)
from document_ai.evaluation.ablation import (
    AblationCase,
    demo_cases_from_hospital,
    run_ablation_suite,
    run_variant,
)
from document_ai.orchestrator.document_agent import DocumentAgent
from document_ai.safety.document_tnr import (
    SeverityBundle,
    contract_summary,
    evaluate_r3_prime,
    not_worse,
    severity_from_safety_card,
)

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "data" / "cases"
GOLDEN = REPO / "data" / "eval" / "golden_fields.jsonl"


def test_golden_fields_jsonl_exists_and_loads():
    assert GOLDEN.exists()
    rows = load_golden_jsonl(GOLDEN)
    assert len(rows) >= 16
    assert {r["case_id"] for r in rows} >= {"hospital_reservation", "inventory_mgmt"}


def test_exact_match_and_set_f1():
    m = exact_match_f1(
        {"product_name": "A", "product_code": "X"},
        {"product_name": "A", "product_code": "X"},
    )
    assert m["f1"] == 1.0
    m2 = exact_match_f1({"product_name": "A"}, {"product_name": "B", "product_code": "X"})
    assert m2["f1"] < 1.0
    s = set_f1({"Req. 1", "Req. 2"}, {"Req. 1", "Req. 2", "Req. 3"})
    assert s["recall"] == pytest.approx(2 / 3, rel=1e-3)


def test_field_f1_hospital_reservation():
    case = CASES / "hospital_reservation"
    if not (case / "input.json").exists():
        pytest.skip("hospital_reservation missing")
    result = evaluate_case_field_f1(case, golden_rows=load_golden_jsonl(GOLDEN))
    assert result["n_golden_fact_rows"] >= 5
    assert result["fact_f1"]["f1"] >= 0.9
    assert result["passed"] is True


def test_field_f1_macro_two_cases():
    dirs = [CASES / "hospital_reservation", CASES / "inventory_mgmt"]
    dirs = [d for d in dirs if (d / "input.json").exists()]
    if len(dirs) < 2:
        pytest.skip("need two cases")
    report = evaluate_many(dirs, golden_jsonl=GOLDEN)
    assert report["macro_field_f1"] >= 0.9
    assert report["failed"] == 0


def test_document_tnr_severity_mapping_and_r3():
    card = {
        "false_patch_count": 1,
        "unsafe_auto_patch_count": 0,
        "source_original_changed_count": 0,
        "writer_without_approval_count": 2,
    }
    mu = severity_from_safety_card(card)
    assert mu.false_patch == 1
    assert mu.unapproved_write == 2
    assert not_worse(SeverityBundle(), SeverityBundle(false_patch=1))

    commit = evaluate_r3_prime(
        mu_pre=SeverityBundle(),
        mu_post=SeverityBundle(),
        approved=True,
        closure_ok=True,
        copy_only=True,
    )
    assert commit["decision"] == "COMMIT_POST"

    abort = evaluate_r3_prime(
        mu_pre=SeverityBundle(),
        mu_post=SeverityBundle(unapproved_write=1),
        approved=False,
        closure_ok=True,
        copy_only=True,
    )
    assert abort["decision"] == "ABORT_TO_PRE"

    salvage = evaluate_r3_prime(
        mu_pre=SeverityBundle(),
        mu_post=SeverityBundle(false_patch=1),
        mu_salvage=SeverityBundle(),
        approved=True,
        closure_ok=True,
        copy_only=True,
    )
    assert salvage["decision"] == "COMMIT_SALVAGE"
    assert "Document-TNR" == contract_summary()["name"]


def test_c1_closure_expands_dependents():
    g = build_graph_from_req_design_links(
        requirement_ids=["Req. 1", "Req. 2"],
        design_items=[
            {"design_id": "D-1", "req_id": "Req. 1"},
            {"design_id": "D-2", "req_id": "Req. 2"},
        ],
        test_rows=[{"test_id": "T-1", "req_ids": ["Req. 1"]}],
    )
    R = closure(g, ["Req. 1"])
    assert "Req. 1" in R
    assert "D-1" in R
    assert "T-1" in R
    assert "D-2" not in R

    sel = selective_sets(g, ["Req. 1"])
    assert sel["closure_applied"] is True
    assert sel["salvage_ratio"] < 1.0


def test_c1_from_relation_hints():
    nodes = [
        DocumentNode(
            node_id="ROW-1",
            document_id="MDTM",
            document_type="MDTM",
            document_role="traceability",
            node_type="TABLE_ROW",
            display_name="row1",
        )
    ]
    hints = [
        RelationHint(
            relation_hint_id="RH-1",
            source_node_id="ROW-1",
            relation_type="TRACE_ROW_CONTAINS",
            target_identifiers=[{"type": "requirement", "value": "Req. 11"}],
        )
    ]
    g = build_graph_from_relation_hints(nodes, hints)
    assert ("ROW-1", "Req. 11") in g.edges
    assert "ROW-1" in closure(g, ["Req. 11"])


def test_ablation_baseline_safer_than_removed_gates():
    cases = demo_cases_from_hospital(CASES / "hospital_reservation")
    suite = run_ablation_suite(cases)
    baseline = suite["summary"]["baseline"]
    no_gate = suite["summary"]["no_gate"]
    no_copy = suite["summary"]["no_copy_only"]
    no_closure = suite["summary"]["no_closure"]

    assert baseline["safe_rate"] == 1.0
    assert baseline["original_preservation_rate"] == 1.0
    assert no_gate["unapproved_write_rate"] > 0
    assert no_copy["original_preservation_rate"] < 1.0
    assert no_closure["false_patch_rate"] > 0
    # no_gate / no_copy_only must abort rather than commit a worse state
    assert no_gate["abort_rate"] == 1.0
    assert no_copy["abort_rate"] == 1.0


def test_dual_mode_new_copy_only_preserves_original(tmp_path: Path):
    src = CASES / "hospital_reservation"
    if not (src / "input.json").exists():
        pytest.skip("hospital_reservation missing")
    # lightweight: only need input.json for gate-blocked path
    case = tmp_path / "mini_case"
    case.mkdir()
    (case / "input.json").write_text(
        (src / "input.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    agent = DocumentAgent(work_root=tmp_path / "work", use_retrieval=False)
    blocked = agent.run(mode="new", case_dir=case, approved=False, enable_write=True)
    assert blocked["decision"] == "ABORT_TO_PRE"
    assert blocked["original_preserved"] is True

    # approved but we skip full harness by using empty requirements — still copy_only
    # Use gate path only to avoid long generate in CI if payloads missing
    out = agent.run(mode="new", case_dir=case, approved=True, enable_write=False)
    assert out["original_preserved"] is True


def test_dual_mode_change_without_docs_still_tnr(tmp_path: Path):
    agent = DocumentAgent(work_root=tmp_path / "work")
    report = agent.run(
        mode="change",
        change_request="Req. 1 update",
        document_set="ec_sw",
        approved=False,
        enable_write=True,
        copy_only=True,
        root=tmp_path / "pilot_root",
    )
    assert report["mode"] == "change"
    assert report["decision"] == "ABORT_TO_PRE"
    assert report["tnr"]["document_tnr_ok"] is True
