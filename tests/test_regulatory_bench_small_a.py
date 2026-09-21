"""Tests for Small-A regulatory_bench: demo_safe, materialize, pipeline, multi-case."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_ai.eval.regulatory_bench.hidden_ids import read_node_map
from document_ai.eval.regulatory_bench.materialize import materialize_case, sha256_file
from document_ai.eval.regulatory_bench.pipeline import run_pipeline_case
from document_ai.eval.regulatory_bench.runner import build_demo_safe_artifacts, run_case
from document_ai.eval.regulatory_bench.scorer import score_case
from document_ai.eval.regulatory_bench.types import ABLATION_MU_MAP, MU_KEYS, mu_is_zero, zero_mu

CASE_000 = Path("data/eval/regulatory_bench/case_000")
CASE_001 = Path("data/eval/regulatory_bench/case_001")
CASE_002 = Path("data/eval/regulatory_bench/case_002")
CASE_003 = Path("data/eval/regulatory_bench/case_003")
CASE_004 = Path("data/eval/regulatory_bench/case_004")
CASE_005 = Path("data/eval/regulatory_bench/case_005")
CASES = [CASE_000, CASE_001, CASE_002]
FACTORY_CASES = [CASE_003, CASE_004, CASE_005]
ALL_CASES = CASES + FACTORY_CASES


def test_mu_keys_frozen():
    assert MU_KEYS == (
        "false_patch",
        "unsafe_write",
        "original_broken",
        "unapproved_write",
    )
    assert mu_is_zero(zero_mu())
    assert ABLATION_MU_MAP["no_closure"] == ("false_patch",)
    assert "unapproved_write" in ABLATION_MU_MAP["no_gate"]


def test_demo_safe_run_case_mu_zero_and_perfect_primary(tmp_path: Path):
    assert CASE_000.is_dir()
    out = tmp_path / "run"
    result = run_case(CASE_000, mode="demo_safe", out_dir=out, recall_k=3)
    score = result["score"]
    assert score["mu_zero"] is True
    assert score["primary"]["doc_f1"] == 1.0
    assert score["primary"]["node_recall_at_3"] == 1.0
    assert score["primary"]["cell_f1"] == 1.0
    assert (out / "score.json").is_file()
    assert (out / "artifacts.json").is_file()


def test_false_patch_when_touching_forbidden_node():
    artifacts = build_demo_safe_artifacts(
        __import__(
            "document_ai.eval.regulatory_bench.case_loader", fromlist=["load_case"]
        ).load_case(CASE_000)
    )
    artifacts["patch_diff"].append(
        {
            "node_id": "REQ_001_DESC",
            "document_id": "MDSR_v1",
            "after": "tampered",
            "touched": True,
        }
    )
    score = score_case(CASE_000, artifacts)
    assert score["mu"]["false_patch"] >= 1
    assert score["mu_zero"] is False


def test_unapproved_write_without_approval():
    artifacts = build_demo_safe_artifacts(
        __import__(
            "document_ai.eval.regulatory_bench.case_loader", fromlist=["load_case"]
        ).load_case(CASE_000)
    )
    artifacts["approval_log"] = {"approved": False, "status": "PENDING"}
    score = score_case(CASE_000, artifacts)
    assert score["mu"]["unapproved_write"] >= 1
    assert score["mu_zero"] is False


def test_original_broken_on_fingerprint_drift():
    artifacts = build_demo_safe_artifacts(
        __import__(
            "document_ai.eval.regulatory_bench.case_loader", fromlist=["load_case"]
        ).load_case(CASE_000)
    )
    artifacts["fingerprints"]["before"] = {"input/MDSR_v1.docx": "a" * 64}
    artifacts["fingerprints"]["after_originals"] = {"input/MDSR_v1.docx": "b" * 64}
    score = score_case(CASE_000, artifacts)
    assert score["mu"]["original_broken"] >= 1
    assert score["mu_zero"] is False


def test_materialize_embeds_hidden_node_ids(tmp_path: Path):
    # Materialize into the real case dir (idempotent) and verify tags.
    manifest = materialize_case(CASE_000, force=True)
    mdsr_nodes = read_node_map(manifest["mdsr"])
    mddr_nodes = read_node_map(manifest["mddr"])
    assert "REQ_007_DESC" in mdsr_nodes
    assert "REQ_001_DESC" in mdsr_nodes
    assert "TRACE_ROW_REQ_001" in mdsr_nodes
    assert "DI_012_PARAM" in mddr_nodes
    assert "DI_012_NOTIFY" in mddr_nodes
    assert "DI_001_PARAM" in mddr_nodes
    # Fingerprints file uses real digests
    fp = Path(manifest["fingerprints"]).read_text(encoding="utf-8")
    assert "PLACEHOLDER" not in fp
    assert sha256_file(Path(manifest["mdsr"])) in fp


@pytest.mark.parametrize("case_dir", CASES, ids=[p.name for p in CASES])
def test_pipeline_mode_mu_zero_and_originals_unchanged(case_dir: Path, tmp_path: Path):
    assert case_dir.is_dir()
    materialize_case(case_dir, force=True)
    mdsr = case_dir / "input" / "MDSR_v1.docx"
    mddr = case_dir / "input" / "MDDR_v1.docx"
    before = (sha256_file(mdsr), sha256_file(mddr))

    out = tmp_path / case_dir.name
    result = run_case(case_dir, mode="pipeline", out_dir=out, approve=True)
    assert result["mu_zero"] is True
    assert result["primary"]["doc_f1"] == 1.0
    assert result["primary"]["node_recall_at_3"] == 1.0
    assert result["primary"]["cell_f1"] == 1.0
    assert (out / "artifacts.json").is_file()
    assert (out / "work" / "MDSR_v1.docx").is_file()

    after = (sha256_file(mdsr), sha256_file(mddr))
    assert after == before, "pipeline must not mutate originals"


def test_pipeline_without_approval_blocks_writes(tmp_path: Path):
    """Gate closed → no patch_diff / no copy mutation; μ stays 0 (no unapproved write occurred)."""
    materialize_case(CASE_000, force=True)
    arts = run_pipeline_case(CASE_000, out_dir=tmp_path / "noappr", approve=False)
    assert arts["approval_log"]["approved"] is False
    assert arts["patch_diff"] == []
    assert arts["applied_node_ids"] == []
    score = score_case(CASE_000, arts)
    assert score["mu"]["unapproved_write"] == 0
    assert score["mu_zero"] is True


@pytest.mark.parametrize("case_dir", ALL_CASES, ids=[p.name for p in ALL_CASES])
def test_live_mode_mu_zero_and_originals_unchanged(case_dir: Path, tmp_path: Path):
    """Live compute_impact path: μ=0, originals byte-stable, copies under work/."""
    assert case_dir.is_dir()
    materialize_case(case_dir, force=True)
    mdsr = case_dir / "input" / "MDSR_v1.docx"
    mddr = case_dir / "input" / "MDDR_v1.docx"
    before = (sha256_file(mdsr), sha256_file(mddr))

    out = tmp_path / f"live_{case_dir.name}"
    result = run_case(case_dir, mode="live", out_dir=out, approve=True)
    assert result["mu_zero"] is True
    assert result["primary"]["doc_f1"] == 1.0
    assert result["primary"]["node_recall_at_3"] == 1.0
    # cell_f1 from rule cell_fill (no gold after-text); frequency rules should match gold for T2.
    assert result["primary"]["cell_f1"] == 1.0
    arts = (out / "artifacts.json").read_text(encoding="utf-8")
    assert '"mode": "live"' in arts
    assert '"patch_values_from": "change_request_frequency_rules"' in arts
    assert "gold_expected" not in arts.split('"patch_values_from"')[1][:80]
    assert (out / "work" / "MDSR_v1.docx").is_file()
    assert before == (sha256_file(mdsr), sha256_file(mddr))


def test_live_without_approval_blocks_writes(tmp_path: Path):
    from document_ai.eval.regulatory_bench.live import run_live_case

    materialize_case(CASE_000, force=True)
    arts = run_live_case(CASE_000, out_dir=tmp_path / "live_noappr", approve=False)
    assert arts["approval_log"]["approved"] is False
    assert arts["patch_diff"] == []
    score = score_case(CASE_000, arts)
    assert score["mu"]["unapproved_write"] == 0
    assert score["mu_zero"] is True


def test_factory_cases_exist_with_docx():
    for case_dir in FACTORY_CASES:
        assert case_dir.is_dir(), case_dir
        assert (case_dir / "input" / "MDSR_v1.docx").is_file()
        assert (case_dir / "input" / "MDDR_v1.docx").is_file()
        assert (case_dir / "gold" / "expected_patch.json").is_file()


def test_bench_has_about_24_t2_cases():
    from document_ai.eval.regulatory_bench.case_factory import list_target_case_ids

    root = Path("data/eval/regulatory_bench")
    targets = list_target_case_ids()
    assert len(targets) >= 24
    present = [c for c in targets if (root / c / "meta.json").exists()]
    assert len(present) >= 24
    # Spot-check a late factory case is materialized
    assert (root / "case_023" / "input" / "MDSR_v1.docx").is_file()


def test_cell_fill_parses_frequency_and_rewrites():
    from document_ai.eval.regulatory_bench.cell_fill import (
        build_filled_patches,
        fill_cell_after,
        parse_target_frequency,
    )

    freq = parse_target_frequency("입력 주기를 매일에서 주 4회로 바꿔 주세요.")
    assert freq is not None
    assert freq["n_per_week"] == 4
    after = fill_cell_after("사용자는 일기를 매일 입력할 수 있어야 한다.", freq, node_id="REQ_007_DESC")
    assert "주 4회" in after
    patches = build_filled_patches(
        change_text="매일에서 주 3회로",
        predicted_nodes=["REQ_007_DESC", "DI_012_PARAM", "DI_012_NOTIFY"],
        node_texts={
            "REQ_007_DESC": "사용자는 수면일기를 매일 입력할 수 있어야 한다.",
            "DI_012_PARAM": "diary_input_frequency=daily",
            "DI_012_NOTIFY": "매일 21:00 입력 알림",
        },
    )
    by = {p["node_id"]: p["after"] for p in patches}
    assert by["DI_012_PARAM"] == "diary_input_frequency=3_per_week"
    assert "주 3회" in by["DI_012_NOTIFY"]


def test_consistency_stub_and_ablation_sandbox():
    from document_ai.eval.regulatory_bench.ablation import run_ablation_suite
    from document_ai.eval.regulatory_bench.consistency_stub import run_consistency_stub

    cons = run_consistency_stub(CASE_000)
    assert cons["full_ledger_port"] is False
    assert cons["consistency_ok"] is True
    abl = run_ablation_suite(CASE_000)
    assert abl["suite"].startswith("sandbox_ablation")
    by = {r["variant"]: r for r in abl["rows"]}
    assert by["full"]["mu_zero"] is True
    assert by["no_gate"]["expected_hit"] is True
    assert by["no_copy_only"]["expected_hit"] is True
    assert by["no_closure"]["expected_hit"] is True


def test_scorecard_export_safety_first(tmp_path: Path):
    from document_ai.eval.regulatory_bench.scorecard import run_scorecard

    # Keep export smoke small: only case_000 via a temp cases root symlink/copy is heavy;
    # run on real root but demo_safe only and trust per_case filter.
    result = run_scorecard(modes=["demo_safe"], out_dir=tmp_path / "reports")
    paths = result["paths"]
    assert Path(paths["json"]).is_file()
    assert Path(paths["csv"]).is_file()
    assert Path(paths["summary_csv"]).is_file()
    summary = result["scorecard"]["summary"]
    assert summary["safety_first_order"][0] == "mu_zero_rate"
    assert "demo_safe" in summary["modes"]
    assert summary["modes"]["demo_safe"]["mu_zero_rate"] == 1.0


def test_doc_closure_unit_req7_expands_param_and_notify():
    from document_ai.eval.regulatory_bench.doc_closure import close_changed_reqs_to_nodes

    mdsr = {
        "REQ_001_DESC": {"text": "login"},
        "REQ_007_DESC": {"text": "사용자는 일기를 매일 입력"},
        "TRACE_ROW_REQ_001": {"text": "Req. 1 → DI-1"},
        "TRACE_ROW_REQ_007": {"text": "Req. 7 → DI-12"},
    }
    mddr = {
        "DI_001_PARAM": {"text": "auth=password"},
        "DI_012_PARAM": {"text": "diary_input_frequency=daily"},
        "DI_012_NOTIFY": {"text": "매일 알림"},
    }
    pred = close_changed_reqs_to_nodes({"Req. 7"}, mdsr_map=mdsr, mddr_map=mddr)
    assert pred == ["REQ_007_DESC", "DI_012_PARAM", "DI_012_NOTIFY"]
    # Req.1 must not pull DI-12
    pred1 = close_changed_reqs_to_nodes({"Req. 1"}, mdsr_map=mdsr, mddr_map=mddr)
    assert "DI_012_PARAM" not in pred1
    assert "DI_001_PARAM" in pred1


def test_live_closure_source_is_document_native(tmp_path: Path):
    from document_ai.eval.regulatory_bench.live import run_live_case

    materialize_case(CASE_000, force=True)
    arts = run_live_case(CASE_000, out_dir=tmp_path / "live_native", approve=True)
    assert "gold_topology" not in str(arts.get("closure_source"))
    assert "doc" in str(arts.get("closure_source"))
    assert arts.get("patch_values_from") != "gold_expected"
    # predicted should include design cells without gold topology walk
    assert "REQ_007_DESC" in arts["predicted_impact_nodes"]
    assert "DI_012_PARAM" in arts["predicted_impact_nodes"]
