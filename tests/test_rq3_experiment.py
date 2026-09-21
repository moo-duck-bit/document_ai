"""Tests for RQ3 Document-TNR experiment runner."""

from __future__ import annotations

from pathlib import Path

from document_ai.eval.rq3_experiment import (
    assess_holdout_writer_expectations,
    assess_pilot_evidence,
    build_ablation_table,
    run_rq3_experiment,
)
from document_ai.safety.document_tnr import (
    counterfactual_mu_for_variant,
    document_tnr_definition,
)


def test_document_tnr_definition_has_components():
    defn = document_tnr_definition()
    assert defn["name"] == "Document-TNR"
    assert "false_patch" in defn["components"]
    assert "new" in defn["modes"] and "change" in defn["modes"]


def test_counterfactual_no_gate_breaks_tnr():
    mu = counterfactual_mu_for_variant("no_gate", gated_session_count=5, sessions_with_impact=3)
    assert mu["unapproved_write"] == 5
    assert mu["unsafe_write"] == 5


def test_assess_pilot_and_holdout_evidence():
    pilot = assess_pilot_evidence()
    assert pilot.get("observed_tnr", {}).get("tnr_satisfied") is True
    holdout = assess_holdout_writer_expectations()
    assert holdout.get("all_gated") is True
    assert holdout.get("case_count", 0) >= 20


def test_build_ablation_table_full_vs_no_gate():
    observed = {
        "mu": {"false_patch": 0, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0},
        "tnr_satisfied": True,
        "total_violations": 0,
    }
    table = build_ablation_table(
        gated_session_count=4,
        sessions_with_impact=4,
        originals_in_scope=4,
        observed_full_tnr=observed,
        closure_delta=2,
    )
    assert table["full"]["tnr_satisfied"] is True
    assert table["no_gate"]["tnr_satisfied"] is False
    assert table["no_copy_only"]["tnr_satisfied"] is False
    assert table["no_closure"]["closure_nodes_missed"] == 2


def test_run_rq3_experiment_writes_artifacts(tmp_path: Path):
    result = run_rq3_experiment(out_dir=tmp_path)
    assert (tmp_path / "rq3_experiment.json").exists()
    assert (tmp_path / "rq3_experiment.md").exists()
    assert result["pilot"]["observed_tnr"]["tnr_satisfied"] is True
    assert result["ablation"]["full"]["tnr_satisfied"] is True
    assert result["ablation"]["no_gate"]["tnr_satisfied"] is False
    assert "hospital_reservation" in result["field_f1_secondary"]["by_case"]
