"""Tests for dual-mode DocumentAgent orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.orchestrator.document_agent import DocumentAgent, checkpoint_summary, run_document_agent


def test_document_agent_new_mode(tmp_path: Path):
    case = tmp_path / "agent_case"
    case.mkdir()
    src = Path("data/cases/hospital_reservation/input.json")
    (case / "input.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    agent = DocumentAgent(force_form_fill=True)
    result = agent.run(case, mode="new")
    assert result["mode"] == "new"
    assert result["result"]["ok"] is True
    assert (case / "requirements.json").exists()


def test_run_document_agent_ablation_variant(tmp_path: Path):
    case = tmp_path / "ablation_case"
    case.mkdir()
    (case / "input.json").write_text(
        json.dumps(
            {
                "case_id": "ablation_case",
                "facts": {"product_name": "X", "product_code": "X", "author_org": "Org"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = run_document_agent(case, mode="new", ablation_variant="no_gate")
    assert out["tnr_spec"]["allow_unapproved_write"] is True


def test_checkpoint_summary():
    summary = checkpoint_summary({"documents": [{"fingerprint": "fp1"}]})
    assert summary["baseline_fingerprint"] == "fp1"
    assert summary["tnr"]["tnr_satisfied"] is True
