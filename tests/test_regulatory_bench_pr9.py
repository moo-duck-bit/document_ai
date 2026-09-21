"""PR9: sealed holdout, paper tables, ablation CLI, field F1, failure-mode cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.eval.regulatory_bench.ablation_table import run_ablation_mu_table
from document_ai.eval.regulatory_bench.field_f1_secondary import score_structured_field_f1
from document_ai.eval.regulatory_bench.holdout import build_holdout_split
from document_ai.eval.regulatory_bench.paper_tables import build_safety_first_tables
from document_ai.eval.regulatory_bench.runner import run_case
from document_ai.eval.regulatory_bench.scorecard import build_scorecard
from document_ai.form_fill.llm import OptionalEnvFreeTextLLM, get_free_text_llm
from document_ai.safety.document_tnr import mu_pilot_key_alignment

CASE_000 = Path("data/eval/regulatory_bench/case_000")
CASE_024 = Path("data/eval/regulatory_bench/case_024")
CASE_025 = Path("data/eval/regulatory_bench/case_025")
CASE_026 = Path("data/eval/regulatory_bench/case_026")


def _tiny_cases_root(tmp_path: Path, ids: list[str]) -> Path:
    root = tmp_path / "cases"
    root.mkdir()
    for cid in ids:
        src = Path("data/eval/regulatory_bench") / cid
        (root / cid).symlink_to(src.resolve())
    return root


def test_sealed_holdout_is_deterministic():
    a = build_holdout_split()
    b = build_holdout_split()
    assert a["seed"] == b["seed"]
    assert a["holdout_case_ids"] == b["holdout_case_ids"]
    assert a["n_holdout"] >= 4
    assert a["n_dev"] >= 1


def test_paper_tables_safety_first_order(tmp_path: Path):
    root = _tiny_cases_root(tmp_path, ["case_000", "case_001", "case_002", "case_003", "case_004"])
    sc = build_scorecard(
        cases_root=root,
        modes=["demo_safe"],
        include_ablation=False,
        include_consistency=False,
        include_field_f1=True,
    )
    payload = build_safety_first_tables(cases_root=root, modes=["demo_safe"], scorecard=sc)
    tables = payload["tables"]
    assert tables["safety_first_order"][0] == "mu_zero_rate"
    assert "holdout" in tables["splits"]
    assert tables["splits"]["full"]["demo_safe"]["mu_zero_rate"] == 1.0
    # field_f1 secondary present when scorecard includes it
    assert tables["splits"]["full"]["demo_safe"]["mean_field_f1"] == 1.0


def test_ablation_table_one_shot_sandbox(tmp_path: Path):
    root = _tiny_cases_root(tmp_path, ["case_000"])
    result = run_ablation_mu_table(cases_root=root, out_dir=tmp_path / "out")
    variants = result["summary"]["variants"]
    assert variants["full"]["mu_zero_rate"] == 1.0
    assert variants["full"]["mean_mu_sum"] == 0.0
    # Clean one-primary-term map for RQ3 (no double-count bleed across μ keys).
    assert variants["no_gate"]["mu_zero_rate"] == 0.0
    assert variants["no_gate"]["mean_mu_sum"] == 2.0
    assert variants["no_gate"]["mean_unapproved_write"] == 1.0
    assert variants["no_gate"]["mean_unsafe_write"] == 1.0
    assert variants["no_gate"]["mean_original_broken"] == 0.0
    assert variants["no_gate"]["mean_false_patch"] == 0.0
    assert variants["no_copy_only"]["mean_mu_sum"] == 1.0
    assert variants["no_copy_only"]["mean_original_broken"] == 1.0
    assert variants["no_copy_only"]["mean_unsafe_write"] == 0.0
    assert variants["no_closure"]["mean_mu_sum"] == 1.0
    assert variants["no_closure"]["mean_false_patch"] == 1.0
    assert variants["no_closure"]["mean_unsafe_write"] == 0.0
    assert variants["no_gate"]["expected_hit_rate"] == 1.0
    assert variants["no_copy_only"]["expected_hit_rate"] == 1.0
    assert variants["no_closure"]["expected_hit_rate"] == 1.0
    assert "sandbox" in (result["summary"].get("disclaimer") or "").lower()
    assert Path(result["paths"]["md"]).is_file()
    assert Path(result["paths"]["csv"]).is_file()


def test_www_short_paper_freeze_snapshot_present():
    freeze = Path("data/eval/www_short_paper_freeze")
    assert (freeze / "SNAPSHOT.md").is_file()
    paper = json.loads((freeze / "reports" / "paper_safety_first.json").read_text(encoding="utf-8"))
    holdout_live = paper["splits"]["holdout"]["live"]
    assert holdout_live["mu_zero_rate"] == 1.0
    assert holdout_live["mean_mu_sum"] == 0.0
    abl = json.loads((freeze / "reports" / "sandbox_ablation_mu.json").read_text(encoding="utf-8"))
    assert abl["summary"]["variants"]["full"]["mean_mu_sum"] == 0.0
    assert abl["summary"]["variants"]["no_gate"]["mean_mu_sum"] == 2.0
    pilot = json.loads((freeze / "pilot_mu_table.json").read_text(encoding="utf-8"))
    assert pilot["pilot"]["mu_zero"] is True
    assert all(v == 0 for v in pilot["pilot"]["mu"].values())
    for name in (
        "fig_pipeline.png",
        "fig_ablation_bar.png",
        "fig11_walkthrough.png",
    ):
        assert (freeze / "figures" / name).is_file()


def test_field_f1_secondary_structured_cells():
    result = run_case(CASE_000, mode="demo_safe")
    arts = json.loads(Path(result["artifacts_path"]).read_text(encoding="utf-8"))
    ff = score_structured_field_f1(CASE_000, arts)
    assert ff["field_f1"] == 1.0
    assert ff["field_count"] >= 1
    assert ff["role"] == "secondary_usability"
    # free_text-only notify may be excluded; PARAM must be present
    ids = {f["node_id"] for f in ff["fields"]}
    assert "DI_012_PARAM" in ids


@pytest.mark.parametrize("case_dir", [CASE_024, CASE_025, CASE_026], ids=["conflict", "bait", "multi"])
def test_failure_mode_cases_demo_safe_mu_zero(case_dir: Path):
    assert case_dir.is_dir()
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("failure_mode")
    assert "failure_mode" in (meta.get("tags") or [])
    result = run_case(case_dir, mode="demo_safe")
    assert result["mu_zero"] is True


def test_multi_req_case_has_extra_impact_node():
    impact = json.loads((CASE_026 / "gold" / "impact_nodes.json").read_text(encoding="utf-8"))
    ids = [n["node_id"] for n in impact["impact_nodes"]]
    assert "REQ_006_DESC" in ids
    assert "REQ_007_DESC" in ids


def test_free_text_llm_skips_structured_and_defaults_stub(monkeypatch):
    monkeypatch.delenv("DOCUMENT_AI_FREE_TEXT_LLM", raising=False)
    llm = get_free_text_llm()
    assert isinstance(llm, OptionalEnvFreeTextLLM)
    assert llm.enabled is False
    out = llm.generate(
        "fill amount",
        context={"field_kind": "structured", "fallback_text": "RULE_ONLY"},
    )
    assert out == "RULE_ONLY"
    out2 = llm.generate(
        "Write product overview narrative",
        context={"free_text_hints": {"system_overview": "HINT_OK"}},
    )
    assert out2 == "HINT_OK"


def test_mu_pilot_key_alignment_covers_four_terms():
    payload = mu_pilot_key_alignment()
    assert payload["mu_keys"] == [
        "false_patch",
        "unsafe_write",
        "original_broken",
        "unapproved_write",
    ]
    for key in payload["mu_keys"]:
        assert key in payload["pilot_to_mu"]
        assert payload["pilot_to_mu"][key]
