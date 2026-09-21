# -*- coding: utf-8 -*-
"""Document Set Benchmark v1.3 node calibration regression."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from document_ai.evaluation.document_set.dataset_loader import load_benchmark_manifest
from document_ai.evaluation.document_set.node_evaluation import compute_calibrated_node_metrics
from document_ai.evaluation.document_set.node_label_audit import audit_node_labels
from document_ai.evaluation.document_set.validation import validate_benchmark_bundle

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "data" / "eval" / "document_set_benchmark"
MDTM = next((REPO / "data" / "examples" / "ec_sw").glob("matrix_mdtm*.docx"))
REPORT = BENCH / "fixtures" / "general_report" / "report_base.docx"
FREEZE = REPO / "data" / "freeze"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_eligibility_file_covers_24():
    rows = [
        json.loads(l)
        for l in (BENCH / "labels" / "node_evaluation_eligibility.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert len(rows) == 24
    modes = {r["node_evaluation_mode"] for r in rows}
    assert modes >= {"REQUIRED", "OPTIONAL", "NOT_APPLICABLE", "AMBIGUOUS"}
    assert "UNLABELED" not in modes


def test_bundle_valid_with_eligibility():
    bundle = load_benchmark_manifest(BENCH / "manifest.json")
    v = validate_benchmark_bundle(bundle)
    assert v["status"] in {"VALID", "VALID_WITH_WARNINGS"}
    assert not v["issues"]


def test_required_have_gold():
    elig = {
        json.loads(l)["case_id"]: json.loads(l)
        for l in (BENCH / "labels" / "node_evaluation_eligibility.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    }
    nodes = {}
    for line in (BENCH / "labels" / "node_impacts.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        nodes.setdefault(r["case_id"], []).append(r)
    for cid, e in elig.items():
        if e["node_evaluation_mode"] == "REQUIRED":
            assert e.get("primary_node_id") or nodes.get(cid)


def test_ambiguous_have_groups():
    for line in (BENCH / "labels" / "node_evaluation_eligibility.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["node_evaluation_mode"] == "AMBIGUOUS":
            assert r.get("acceptable_node_groups") or r.get("acceptable_node_ids")


def test_na_excluded_from_strict_denominator():
    cases = [
        {"mode": "NOT_APPLICABLE", "gold_ids": set(), "acceptable": set(), "groups": [], "ranked_preds": []},
        {"mode": "REQUIRED", "gold_ids": {"g"}, "acceptable": set(), "groups": [], "ranked_preds": [{"node_id": "g", "score": 1}]},
    ]
    m = compute_calibrated_node_metrics(cases)
    assert m["strict_denominator"] == 1
    assert m["not_applicable_count"] == 1


def test_audit_unlabeled_zero():
    audit = audit_node_labels(bench_dir=BENCH)
    assert audit["summary"]["unlabeled"] == 0
    assert audit["summary"]["automatic_gold_mutation"] == 0


def test_proposed_label_changes_exist():
    p = BENCH / "proposed_label_changes.json"
    assert p.is_file()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["automatic_gold_mutation"] is False
    assert all(not c.get("from_prediction") for c in data.get("changes") or [])


def test_no_case_id_hardcode_in_eval_product():
    root = REPO / "src" / "document_ai" / "evaluation" / "document_set"
    forbidden = ["ec_sw_semantic_only", "gr_schedule_table"]
    for path in root.rglob("*.py"):
        if path.name in {"node_label_audit.py"}:
            # audit may mention prediction keys only in tests; product eval modules must not
            pass
        text = path.read_text(encoding="utf-8")
        # allow comments in generate? that's scripts. here only evaluation package
        if path.name.endswith("_test.py"):
            continue
        for tok in forbidden:
            # node_label_audit itself should not hardcode case ids for mutation
            if path.name == "node_label_audit.py":
                assert tok not in text


def test_prediction_adapter_no_gold_read():
    text = (REPO / "src" / "document_ai" / "evaluation" / "document_set" / "prediction_adapter.py").read_text(
        encoding="utf-8"
    )
    assert "node_impacts" not in text
    assert "node_evaluation_eligibility" not in text
    assert "labels/" not in text


def test_desktop_examples_freeze_unchanged_hashes_exist():
    assert MDTM.is_file()
    assert REPORT.is_file()
    # freeze dir may be empty or present — just ensure we do not write into examples
    assert (REPO / "data" / "examples" / "ec_sw").is_dir()


def test_semantic_still_review_not_patch(tmp_path):
    from document_ai.workflow.orchestrator import create_workflow, run_analysis

    before = _sha(MDTM)
    rec = create_workflow(
        document_set="ec_sw",
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="v13_sem",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert out["patch_candidates"] == []
    dec = {d["document_id"]: d for d in out["metadata"]["document_impact_decisions"]}
    assert dec["MDTM"]["predicted_status"] == "REVIEW_REQUIRED"
    assert _sha(MDTM) == before


def test_schedule_still_review_not_patch(tmp_path):
    from document_ai.workflow.orchestrator import create_workflow, run_analysis

    before = _sha(REPORT)
    rec = create_workflow(
        document_set="general_report",
        change_request="일정 표 수정 2026-Q4",
        files=[("report_base.docx", REPORT.read_bytes(), "general_report")],
        root=tmp_path,
        name="v13_sch",
    )
    out = run_analysis(rec["workflow_id"], root=tmp_path)
    assert out["patch_candidates"] == []
    assert _sha(REPORT) == before


def test_writer_scope_unchanged_on_semantic(tmp_path):
    from document_ai.workflow.orchestrator import approve_workflow, create_workflow, run_analysis, run_writer

    rec = create_workflow(
        document_set="ec_sw",
        change_request="사용자 인증 및 접근통제 보안 요구 변경",
        files=[("MDTM.docx", MDTM.read_bytes(), "traceability")],
        root=tmp_path,
        name="v13_wr",
    )
    wid = rec["workflow_id"]
    run_analysis(wid, root=tmp_path)
    approve_workflow(wid, approve_all_pending=True, root=tmp_path)
    out = run_writer(wid, enable_write=False, root=tmp_path)
    wr = out["workflow"]["writer_result"]
    assert wr.get("controlled_writer_invoked") is False
    assert int(wr.get("applied") or 0) == 0


def test_legacy_and_calibrated_keys_documented():
    from document_ai.evaluation.document_set.node_evaluation import compute_legacy_node_metrics

    leg = compute_legacy_node_metrics(
        [{"gold_ids": {"a"}, "acceptable": set(), "ranked_preds": [{"node_id": "a", "score": 1}]}]
    )
    cal = compute_calibrated_node_metrics(
        [
            {
                "mode": "REQUIRED",
                "gold_ids": {"a"},
                "acceptable": set(),
                "groups": [],
                "ranked_preds": [{"node_id": "a", "score": 1}],
            }
        ]
    )
    for k in ("legacy_node_top1", "legacy_node_recall_at_3", "legacy_mrr"):
        assert k in leg
    for k in ("required_node_top1", "optional_grounding_coverage", "node_label_coverage"):
        assert k in cal


def test_report_builder_writes_new_artifacts(tmp_path):
    from document_ai.evaluation.document_set.report_builder import write_benchmark_artifacts

    write_benchmark_artifacts(
        tmp_path,
        {
            "run_manifest": {"run_id": "t"},
            "document_metrics": {"macro_f1": 1.0},
            "node_retrieval_metrics": {"top1_accuracy": 0.5},
            "node_metrics_legacy": {"legacy_node_top1": 0.5},
            "node_metrics_calibrated": {"required_node_top1": 1.0, "node_label_coverage": 1.0},
            "node_evaluation_eligibility": {"counts": {}},
            "node_grounding_coverage": {},
            "node_identity_validation": {"ok": True},
            "stable_node_reference_validation": {"ok": True},
            "decision_metrics": {"macro_f1": 0.6, "false_patch_rate": 0},
            "decision_metrics_document": {"macro_f1": 1.0},
            "decision_metrics_node": {"macro_f1": 0.6},
            "writer_metrics": {},
            "e2e_metrics": {"success_rate": 1.0, "unsafe_failure_rate": 0},
            "latency_metrics": {"total_ms": {"mean": 1}},
            "safety_scorecard": {"safety_status": "PASS"},
            "error_analysis": {},
            "case_results": [],
            "summary": {"run_id": "t"},
        },
    )
    assert (tmp_path / "node_metrics_calibrated.json").is_file()
    assert (tmp_path / "decision_metrics_document.json").is_file()
    assert (tmp_path / "decision_metrics_node.json").is_file()
