"""Tests for RQ3 priority-1 holdout safety / sandbox ablation / impact quality."""

from __future__ import annotations

from pathlib import Path

from document_ai.eval.rq3_holdout_suite import (
    compute_impact_quality,
    run_priority1_suite,
    run_sandbox_ablation,
)


def test_sandbox_ablation_full_holds_and_no_gate_breaks():
    result = run_sandbox_ablation(n_intents=5)
    variants = result["variants"]
    assert variants["full"]["tnr_satisfied"] is True
    assert variants["no_gate"]["tnr_satisfied"] is False
    assert variants["no_copy_only"]["tnr_satisfied"] is False
    assert variants["no_closure"]["tnr_satisfied"] is False
    assert (result.get("copy_demo") or {}).get("source_unchanged") is True


def test_compute_impact_quality_basic():
    rows = [
        {
            "domain": "ec_sw",
            "gold_docs": ["MDTM_BASE"],
            "pred_impact_docs": ["MDTM_BASE"],
            "gold_nodes": ["n1"],
            "pred_ranked_nodes": ["n1", "n2"],
        },
        {
            "domain": "ec_sw",
            "gold_docs": [],
            "pred_impact_docs": [],
            "gold_nodes": [],
            "pred_ranked_nodes": [],
        },
    ]
    metrics = compute_impact_quality(rows)
    assert metrics["document"]["f1"] == 1.0
    assert metrics["required_node_recall_at_3"] == 1.0


def test_run_priority1_suite_writes_artifacts(tmp_path: Path):
    result = run_priority1_suite(out_dir=tmp_path)
    assert (tmp_path / "rq3_priority1.json").exists()
    assert (tmp_path / "rq3_priority1.md").exists()
    assert (tmp_path / "holdout_safety_scorecard.json").exists()
    assert result["holdout_safety"]["observed_tnr"]["tnr_satisfied"] is True
    assert result["holdout_safety"]["safety_scorecard"]["safety_status"] == "PASS"
    assert result["sandbox_ablation"]["variants"]["full"]["tnr_satisfied"] is True
    assert result["sandbox_ablation"]["variants"]["no_gate"]["tnr_satisfied"] is False
    assert "document" in result["impact_quality"]
