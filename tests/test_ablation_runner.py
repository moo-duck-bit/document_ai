"""Tests for Document-TNR ablation runner."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.eval.ablation_runner import (
    evaluate_tnr_scorecards,
    run_ablation_suite,
    run_closure_ablation,
    tnr_from_scorecard_file,
)


def test_run_closure_ablation_jm_collection():
    case = Path("data/cases/jm_collection")
    if not (case / "requirements.json").exists():
        return
    result = run_closure_ablation(case, {"Req. 6"})
    assert "with_closure" in result
    assert "without_closure" in result
    assert result["with_closure"]["apply_closure"] is True


def test_tnr_from_scorecard_file(tmp_path: Path):
    scorecard = tmp_path / "scorecard.json"
    scorecard.write_text(
        json.dumps(
            {
                "false_patch_count": 0,
                "unsafe_auto_patch_count": 0,
                "source_original_changed_count": 0,
                "writer_without_approval_count": 0,
            }
        ),
        encoding="utf-8",
    )
    result = tnr_from_scorecard_file(scorecard)
    assert result["tnr_satisfied"] is True


def test_tnr_from_pilot_scorecard():
    path = Path("data/pilot/results/pilot_run_01/safety_scorecard.json")
    if not path.exists():
        return
    result = tnr_from_scorecard_file(path)
    assert "mu" in result
    assert result["tnr_satisfied"] is True


def test_evaluate_tnr_scorecards_batch(tmp_path: Path):
    good = tmp_path / "a_scorecard.json"
    bad = tmp_path / "b_scorecard.json"
    good.write_text(
        json.dumps({"false_patch_count": 0, "source_original_changed_count": 0}),
        encoding="utf-8",
    )
    bad.write_text(
        json.dumps({"false_patch_count": 2, "source_original_changed_count": 0}),
        encoding="utf-8",
    )
    result = evaluate_tnr_scorecards(tmp_path)
    assert result["scorecard_count"] == 2
    assert result["tnr_satisfied_count"] == 1
    assert result["tnr_rate"] == 0.5


def test_change_mode_ablation_jm_collection():
    case = Path("data/cases/jm_collection")
    change = case / "changes" / "req_change.json"
    if not change.exists():
        return
    result = run_ablation_suite(case, mode="change", change=change)
    assert result["mode"] == "change"
    assert "full" in result["variants"]
    assert result["variants"]["full"].get("pipeline_ok") is True
    assert "closure_ablation" in result
    assert "Req. 6" in result["closure_ablation"]["req_ids"]
