# -*- coding: utf-8 -*-
"""Document-set benchmark E2E / CLI tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from document_ai.cli import main
from document_ai.evaluation.document_set.evaluator import run_benchmark
from document_ai.evaluation.document_set.prediction_adapter import adapt_workflow_prediction

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data" / "eval" / "document_set_benchmark" / "manifest.json"
MDTM_EXAMPLE = next((REPO / "data" / "examples" / "ec_sw").glob("matrix_mdtm*.docx"))
MDTM_FIX = REPO / "data" / "eval" / "document_set_benchmark" / "fixtures" / "ec_sw" / "MDTM.docx"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def freeze_hashes():
    paths = [MDTM_EXAMPLE]
    if MDTM_FIX.exists():
        paths.append(MDTM_FIX)
    return {str(p): _sha(p) for p in paths}


def test_prediction_adapter_status_map():
    pred = adapt_workflow_prediction(
        "c1",
        {
            "state": "COMPLETED",
            "documents": [{"document_id": "MDTM"}],
            "impacted_documents": ["MDTM"],
            "patch_candidates": [
                {
                    "document_id": "MDTM",
                    "node_id": "n1",
                    "item_id": "i1",
                    "status": "PATCH_CANDIDATE",
                    "metadata": {"overlap": 1.0},
                }
            ],
            "review_required": [],
            "writer_result": {"applied": 0, "controlled_writer_invoked": False, "enable_write": False},
        },
    )
    assert pred["nodes"][0]["predicted_status"] == "PATCH_CANDIDATE"
    assert pred["documents"][0]["predicted_status"] == "IMPACTED"


def test_benchmark_smoke_ec_sw(tmp_path, freeze_hashes):
    out = tmp_path / "results"
    payload = run_benchmark(
        manifest_path=MANIFEST,
        domains=["ec_sw"],
        case_ids=["ec_sw_no_impact", "ec_sw_exact_req_single"],
        output_dir=out,
        repeat=1,
        fail_on_unsafe=False,
        work_root=tmp_path / "wf",
    )
    assert payload["summary"]["run_id"]
    run_dir = Path(payload["output_dir"])
    assert (run_dir / "BENCHMARK_REPORT.md").is_file()
    assert (run_dir / "benchmark_summary.json").is_file()
    assert (out / "latest.json").is_file()
    for p, h in freeze_hashes.items():
        assert _sha(Path(p)) == h


def test_benchmark_smoke_general_report(tmp_path):
    payload = run_benchmark(
        manifest_path=MANIFEST,
        domains=["general_report"],
        case_ids=["gr_no_impact", "gr_methodology_source"],
        output_dir=tmp_path / "results",
        work_root=tmp_path / "wf",
    )
    assert payload["e2e_metrics"]["n"] == 2


def test_e2e_status_values(tmp_path):
    payload = run_benchmark(
        manifest_path=MANIFEST,
        case_ids=["ec_sw_no_impact", "ec_sw_exact_req_single", "gr_no_impact"],
        output_dir=tmp_path / "results",
        work_root=tmp_path / "wf",
    )
    statuses = {r["e2e_status"] for r in payload["case_results"]}
    assert statuses <= {"SUCCESS", "PARTIAL", "SAFE_FAILURE", "UNSAFE_FAILURE", "INVALID"}


def test_run_dir_immutable_no_overwrite(tmp_path):
    out = tmp_path / "results"
    p1 = run_benchmark(
        manifest_path=MANIFEST,
        case_ids=["gr_no_impact"],
        output_dir=out,
        work_root=tmp_path / "wf1",
    )
    # forge collision by creating same run_id dir is hard; ensure second run different id
    p2 = run_benchmark(
        manifest_path=MANIFEST,
        case_ids=["gr_no_impact"],
        output_dir=out,
        work_root=tmp_path / "wf2",
    )
    assert p1["summary"]["run_id"] != p2["summary"]["run_id"]


def test_cli_exit_0(tmp_path):
    code = main(
        [
            "eval-document-set",
            "--manifest",
            str(MANIFEST),
            "--case-ids",
            "gr_no_impact",
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ]
    )
    assert code == 0


def test_cli_exit_3_invalid_dataset(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text(json.dumps({"cases": []}), encoding="utf-8")
    # empty cases still loads; create invalid domain case
    base = tmp_path / "b"
    (base / "cases").mkdir(parents=True)
    (base / "labels").mkdir()
    (base / "fixtures").mkdir()
    (base / "fixtures" / "a.txt").write_text("x", encoding="utf-8")
    case = {
        "case_id": "x",
        "domain": "nope",
        "document_set_id": "ec_sw",
        "change_request": "x",
        "input_documents": [{"path": "fixtures/a.txt", "filename": "a.txt"}],
    }
    (base / "cases" / "x.json").write_text(json.dumps(case), encoding="utf-8")
    for name in ("document_impacts", "node_impacts", "patch_expectations", "writer_expectations"):
        (base / "labels" / f"{name}.jsonl").write_text("", encoding="utf-8")
    man = base / "manifest.json"
    man.write_text(json.dumps({"cases": ["cases/x.json"]}), encoding="utf-8")
    code = main(["eval-document-set", "--manifest", str(man), "--output-dir", str(tmp_path / "o")])
    assert code == 3


def test_examples_unchanged_after_benchmark(tmp_path, freeze_hashes):
    before = dict(freeze_hashes)
    run_benchmark(
        manifest_path=MANIFEST,
        case_ids=["ec_sw_exact_req_single"],
        output_dir=tmp_path / "results",
        work_root=tmp_path / "wf",
    )
    for p, h in before.items():
        assert _sha(Path(p)) == h


def test_no_scenario_hardcode_in_evaluator():
    src = (REPO / "src" / "document_ai" / "evaluation" / "document_set" / "evaluator.py").read_text(
        encoding="utf-8"
    )
    assert "ec_sw_exact_req_single" not in src
    assert "gr_methodology_source" not in src
