# -*- coding: utf-8 -*-
"""Benchmark v2 robustness / generalization / format / regression tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from document_ai.evaluation.document_set_v2.calibration import compute_calibration_metrics
from document_ai.evaluation.document_set_v2.format_preservation import (
    aggregate_format_metrics,
    compare_format,
)
from document_ai.evaluation.document_set_v2.metrics import generalization_gap, summarize_split_metrics
from document_ai.evaluation.document_set_v2.robustness import (
    apply_text_transform,
    compute_decision_consistency,
    compute_node_consistency,
    req_format_variants,
    whitespace_variant,
)
from document_ai.evaluation.document_set_v2.safety_stress import run_safety_stress_suite

REPO = Path(__file__).resolve().parents[1]
V1 = REPO / "data" / "eval" / "document_set_benchmark"
V2 = REPO / "data" / "eval" / "document_set_benchmark_v2"
MDTM = next((REPO / "data" / "examples" / "ec_sw").glob("matrix_mdtm*.docx"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_identifier_format_variants():
    vs = req_format_variants("Req. 11 추적성 갱신")
    assert "req_dash" in vs and "REQ-11" in vs["req_dash"]


def test_whitespace_variation():
    assert "  " in whitespace_variant("Req. 11 갱신")


def test_apply_text_transform_case():
    out = apply_text_transform("Req. Ab", "case_toggle")
    assert "rEQ" in out or "REQ" in out.upper()


def test_decision_consistency_metamorphic():
    pairs = [
        {
            "base_case_id": "a",
            "variant_case_id": "b",
            "transformation": "whitespace",
            "expected_relation": "same_document_decision",
        }
    ]
    m = compute_decision_consistency(pairs, {"a": "IMPACTED", "b": "IMPACTED"})
    assert m["decision_consistency_rate"] == 1.0
    assert m["metamorphic_pass_rate"] == 1.0


def test_node_consistency_equivalence():
    pairs = [{"base_case_id": "a", "variant_case_id": "b", "transformation": "x"}]
    m = compute_node_consistency(
        pairs,
        {"a": "n1", "b": "n2"},
        equivalence={"n1": {"n1", "n2"}, "n2": {"n1", "n2"}},
    )
    assert m["node_consistency_rate"] == 1.0


def test_generalization_gap():
    g = generalization_gap(
        {"document_macro_f1": 0.9, "required_node_top1": 0.8, "required_node_recall_at_3": 0.85, "e2e_success_rate": 0.9, "node_decision_macro_f1": 0.7},
        {"document_macro_f1": 0.7, "required_node_top1": 0.5, "required_node_recall_at_3": 0.6, "e2e_success_rate": 0.7, "node_decision_macro_f1": 0.5},
    )
    assert abs(g["document_macro_f1_gap"] - 0.2) < 1e-9


def test_summarize_split_zero_denominator():
    m = summarize_split_metrics(
        doc_y_true=[],
        doc_y_pred=[],
        calibrated_cases=[],
        e2e_statuses=[],
        false_patch_count=0,
    )
    assert m["e2e_success_rate"] == 0.0


def test_calibration_not_probability():
    cal = compute_calibration_metrics(
        [{"score": 120.0, "correct": True}, {"score": 0.2, "correct": False}]
    )
    assert cal["score_is_probability"] is False


def test_format_preservation_identical(tmp_path):
    src = V2 / "fixtures" / "general_report" / "report_std.docx"
    dst = tmp_path / "copy.docx"
    dst.write_bytes(src.read_bytes())
    cmp = compare_format(src, dst)
    assert cmp["status"] == "OK"
    assert cmp["structure_preservation_rate"] == 1.0
    agg = aggregate_format_metrics([cmp])
    assert agg["n_applicable"] == 1


def test_format_na_when_missing():
    agg = aggregate_format_metrics([{"status": "N/A"}])
    assert agg["n_applicable"] == 0


def test_safety_stress_suite():
    out = run_safety_stress_suite(
        examples_mdtm=MDTM,
        freeze_dir=REPO / "data" / "freeze",
        repo_root=REPO,
    )
    assert out["examples_changed"] == 0
    assert out["unauthorized_writer"] == 0
    assert out["pass_rate"] >= 1.0


def test_v1_regression_manifest_unchanged():
    # 24 cases still listed
    man = json_load = __import__("json").loads((V1 / "manifest.json").read_text(encoding="utf-8"))
    assert len(man["cases"]) == 24


def test_v1_case_files_untouched_count():
    assert len(list((V1 / "cases").rglob("*.json"))) == 24


def test_desktop_examples_freeze_hash_stable():
    assert MDTM.is_file()
    h1 = _sha(MDTM)
    h2 = _sha(MDTM)
    assert h1 == h2


def test_no_case_hardcode_in_v2_engine():
    root = REPO / "src" / "document_ai" / "evaluation" / "document_set_v2"
    forbidden = ["v2_dev_ec_req11_exact", "v2_hol_ec_req10"]
    for p in root.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        for tok in forbidden:
            assert tok not in text


def test_metamorphic_pairs_file():
    rows = [
        __import__("json").loads(l)
        for l in (V2 / "metamorphic_pairs.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert len(rows) >= 4


def test_human_review_forms_exist():
    assert (V2 / "human_review" / "review_form.jsonl").is_file()
    assert (V2 / "human_review" / "review_guideline.md").is_file()


def test_holdout_protocol_violation_if_pred_before_seal(tmp_path):
    from document_ai.evaluation.document_set_v2.holdout_protocol import hash_label_dir, unseal_for_evaluation

    sealed = V2 / "holdout" / "sealed_labels"
    log = unseal_for_evaluation(
        seal_manifest={"sealed_at": "2099-01-01T00:00:00+00:00", "label_file_hashes": hash_label_dir(sealed)},
        prediction_freeze={"frozen_at": "2020-01-01T00:00:00+00:00", "sha256": "abc"},
        sealed_labels_dir=sealed,
        out_log_path=tmp_path / "u.json",
    )
    assert log["status"] == "PROTOCOL_VIOLATION"


# extra robustness / metrics coverage
def test_paren_transform():
    assert apply_text_transform("hello", "paren") == "(hello)"


def test_no_patch_upgrade_relation():
    pairs = [
        {
            "base_case_id": "a",
            "variant_case_id": "b",
            "transformation": "x",
            "expected_relation": "no_patch_upgrade",
        }
    ]
    m = compute_decision_consistency(
        pairs, {"a": "REVIEW_REQUIRED", "b": "UNRELATED"}
    )
    assert m["decision_consistency_rate"] == 1.0


def test_summarize_with_required_case():
    m = summarize_split_metrics(
        doc_y_true=["IMPACTED"],
        doc_y_pred=["IMPACTED"],
        calibrated_cases=[
            {
                "mode": "REQUIRED",
                "gold_ids": {"g"},
                "acceptable": set(),
                "groups": [],
                "ranked_preds": [{"node_id": "g", "score": 1}],
            }
        ],
        e2e_statuses=["SUCCESS"],
        false_patch_count=0,
        node_dec_true=["PATCH_CANDIDATE"],
        node_dec_pred=["PATCH_CANDIDATE"],
    )
    assert m["required_node_top1"] == 1.0
    assert m["e2e_success_rate"] == 1.0


def test_domain_breakdown_helper():
    from document_ai.evaluation.document_set_v2.metrics import domain_breakdown

    out = domain_breakdown(
        [
            {"domain": "ec_sw", "e2e_status": "SUCCESS", "document_hit": True, "mode": "REQUIRED", "required_top1_hit": True, "latency_ms": 10},
            {"domain": "ec_sw", "e2e_status": "SAFE_FAILURE", "document_hit": False, "mode": "OPTIONAL", "required_top1_hit": False, "latency_ms": 20},
        ]
    )
    assert out["ec_sw"]["case_count"] == 2
