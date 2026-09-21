# -*- coding: utf-8 -*-
"""Projection into benchmark labels + official/proxy metrics + error analysis + audit tests (Cycle 6)."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.evaluation.business_proposal_gold import audit as audit_mod
from document_ai.evaluation.business_proposal_gold import error_analysis
from document_ai.evaluation.business_proposal_gold import official_metrics
from document_ai.evaluation.business_proposal_gold.project_to_benchmark import (
    gold_row_to_projection,
    project_gold_into_benchmark,
)


def _required_row(case_id="v2_dev_bp_budget", document_id="PROPOSAL_BASE"):
    return {
        "case_id": case_id,
        "document_id": document_id,
        "node_evaluation_mode": "REQUIRED",
        "primary_reference": {
            "reference_type": "TEMPLATE",
            "template_node_id": "business_proposal_v1.budget",
            "document_node_id": "table_00",
            "stable_node_id": None,
        },
        "acceptable_references": [{"reference_type": "PHYSICAL", "document_node_id": "heading_0004"}],
        "acceptable_groups": [["heading_0004", "table_00", "business_proposal_v1.budget"]],
        "expected_physical_node_type": "TABLE",
        "label_rationale": "unique matching table node",
        "label_confidence": 0.9,
    }


def _optional_row(case_id="v2_dev_bp_market_add"):
    return {
        "case_id": case_id,
        "document_id": "PROPOSAL_BASE",
        "node_evaluation_mode": "OPTIONAL",
        "primary_reference": {"reference_type": "VIRTUAL"},
        "acceptable_references": [],
        "acceptable_groups": [],
        "expected_physical_node_type": "NONE",
        "label_rationale": "no canonical section",
        "label_confidence": 0.7,
    }


# --- project_to_benchmark -----------------------------------------------------


def test_gold_row_to_projection_uses_template_as_primary():
    proj = gold_row_to_projection(_required_row(), now="2026-08-01T00:00:00+00:00")
    elig = proj["eligibility"]
    assert elig["primary_node_id"] == "business_proposal_v1.budget"
    assert "table_00" in elig["acceptable_node_ids"]
    assert elig["node_evaluation_mode"] == "REQUIRED"
    assert elig["domain"] == "business_proposal"


def test_gold_row_to_projection_required_produces_node_row():
    proj = gold_row_to_projection(_required_row(), now="2026-08-01T00:00:00+00:00")
    node = proj["node"]
    assert node is not None
    assert node["node_id"] == "table_00"
    assert node["gold_status"] == "REVIEW_REQUIRED"
    assert node["node_evaluation_mode"] == "REQUIRED"


def test_gold_row_to_projection_optional_no_node_row():
    proj = gold_row_to_projection(_optional_row(), now="2026-08-01T00:00:00+00:00")
    assert proj["node"] is None
    assert proj["eligibility"]["node_evaluation_mode"] == "OPTIONAL"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def test_project_gold_into_benchmark_preserves_non_bp_rows(tmp_path):
    bench = tmp_path / "bench"
    dev_labels = bench / "development" / "labels"
    hol_labels = bench / "holdout" / "sealed_labels"
    non_bp_row = {
        "case_id": "v2_dev_ec_req11",
        "domain": "ec_sw",
        "document_id": "MDTM",
        "node_evaluation_mode": "REQUIRED",
        "primary_node_id": "req_11",
        "acceptable_node_ids": [],
        "acceptable_node_groups": [],
    }
    _write_jsonl(dev_labels / "node_evaluation_eligibility.jsonl", [non_bp_row])
    _write_jsonl(hol_labels / "node_evaluation_eligibility.jsonl", [])

    gold_rows = [_required_row(case_id="v2_dev_bp_budget"), _optional_row(case_id="v2_dev_bp_market_add")]
    written = project_gold_into_benchmark(gold_rows, benchmark_root=bench)

    final_elig = json.loads(
        "[" + ",".join((dev_labels / "node_evaluation_eligibility.jsonl").read_text(encoding="utf-8").splitlines()) + "]"
    )
    case_ids = {r["case_id"] for r in final_elig}
    assert "v2_dev_ec_req11" in case_ids  # non-BP row preserved
    assert "v2_dev_bp_budget" in case_ids
    assert "v2_dev_bp_market_add" in case_ids
    assert written["holdout_reseal_status"] == "SEALED"


def test_project_gold_into_benchmark_splits_by_case_id_prefix(tmp_path):
    bench = tmp_path / "bench"
    gold_rows = [
        _required_row(case_id="v2_dev_bp_budget"),
        {**_required_row(case_id="v2_hol_bp_budget"), "document_id": "PROPOSAL_BASE"},
    ]
    project_gold_into_benchmark(gold_rows, benchmark_root=bench)
    dev_path = bench / "development" / "labels" / "node_evaluation_eligibility.jsonl"
    hol_path = bench / "holdout" / "sealed_labels" / "node_evaluation_eligibility.jsonl"
    dev_rows = [json.loads(l) for l in dev_path.read_text(encoding="utf-8").splitlines()]
    hol_rows = [json.loads(l) for l in hol_path.read_text(encoding="utf-8").splitlines()]
    assert {r["case_id"] for r in dev_rows} == {"v2_dev_bp_budget"}
    assert {r["case_id"] for r in hol_rows} == {"v2_hol_bp_budget"}


# --- official_metrics ---------------------------------------------------------


def test_official_metrics_zero_denominator():
    result = official_metrics.compute_official_business_proposal_metrics([])
    assert result["n_required"] == 0
    assert result["required_node_top1"] is None
    assert result["status"] == "NOT_APPLICABLE_ZERO_DENOMINATOR"


def test_official_metrics_filters_to_required_and_domain():
    cases = [
        {
            "case_id": "c1",
            "mode": "REQUIRED",
            "domain": "business_proposal",
            "gold_ids": {"table_00"},
            "acceptable": set(),
            "ranked_preds": [{"node_id": "table_00", "score": 0.9}],
        },
        {
            "case_id": "c2",
            "mode": "OPTIONAL",
            "domain": "business_proposal",
            "gold_ids": set(),
            "acceptable": set(),
            "ranked_preds": [],
        },
        {
            "case_id": "c3",
            "mode": "REQUIRED",
            "domain": "ec_sw",
            "gold_ids": {"req_11"},
            "acceptable": set(),
            "ranked_preds": [{"node_id": "req_11", "score": 0.9}],
        },
    ]
    result = official_metrics.compute_official_business_proposal_metrics(cases)
    assert result["n_required"] == 1
    assert result["required_node_top1"] == 1.0
    assert result["status"] == "OK"


def test_official_metrics_top1_miss():
    cases = [
        {
            "case_id": "c1",
            "mode": "REQUIRED",
            "domain": "business_proposal",
            "gold_ids": {"table_00"},
            "acceptable": set(),
            "ranked_preds": [{"node_id": "heading_0001", "score": 0.9}],
        }
    ]
    result = official_metrics.compute_official_business_proposal_metrics(cases)
    assert result["required_node_top1"] == 0.0
    assert result["per_case"][0]["top1_hit"] is False


def test_proxy_intent_grounding_zero_cases():
    result = official_metrics.compute_proxy_intent_grounding_metrics([])
    assert result["n_cases"] == 0
    assert result["status"] == "NOT_APPLICABLE_ZERO_DENOMINATOR"


def test_proxy_intent_grounding_hit1():
    cases = [
        {
            "case_id": "c1",
            "change_request": "예산 표 인건비 수정",
            "ranked_preds": [{"node_id": "business_proposal_v1.budget", "score": 0.9}],
        }
    ]
    result = official_metrics.compute_proxy_intent_grounding_metrics(cases)
    assert result["n_cases"] == 1
    assert result["intent_grounding_top1"] == 1.0
    assert "gold" not in result.get("note", "").lower() or "does not read" in result["note"].lower()


# --- error_analysis ------------------------------------------------------------


def test_classify_miss_correct():
    result = error_analysis.classify_miss(
        gold_ids={"table_00"},
        acceptable=set(),
        ranked_preds=[{"node_id": "table_00", "score": 1.0}],
        expected_physical_node_type="TABLE",
    )
    assert result == error_analysis.CORRECT


def test_classify_miss_no_prediction():
    result = error_analysis.classify_miss(
        gold_ids={"table_00"}, acceptable=set(), ranked_preds=[], expected_physical_node_type="TABLE"
    )
    assert result == error_analysis.NO_PREDICTION


def test_classify_miss_wrong_template_node():
    # Gold is template-only; a *different* template-style (non-physical) top-1 is
    # WRONG_TEMPLATE_NODE. A physical top-1 (e.g. table_00) against template-only
    # gold is a representation mismatch handled separately (OTHER_MISMATCH).
    result = error_analysis.classify_miss(
        gold_ids={"business_proposal_v1.budget"},
        acceptable=set(),
        ranked_preds=[{"node_id": "business_proposal_v1.schedule", "score": 0.9}],
        expected_physical_node_type="TABLE",
    )
    assert result == error_analysis.WRONG_TEMPLATE_NODE


def test_classify_miss_heading_instead_of_table():
    result = error_analysis.classify_miss(
        gold_ids={"table_00"},
        acceptable=set(),
        ranked_preds=[{"node_id": "heading_0004", "score": 0.9}],
        expected_physical_node_type="TABLE",
    )
    assert result == error_analysis.HEADING_INSTEAD_OF_TABLE


def test_build_error_report_counts():
    cases = [
        {
            "case_id": "c1",
            "mode": "REQUIRED",
            "gold_ids": {"table_00"},
            "acceptable": set(),
            "ranked_preds": [{"node_id": "table_00", "score": 0.9}],
        },
        {
            "case_id": "c2",
            "mode": "REQUIRED",
            "gold_ids": {"table_00"},
            "acceptable": set(),
            "ranked_preds": [],
        },
        {
            "case_id": "c3",
            "mode": "OPTIONAL",
            "gold_ids": set(),
            "acceptable": set(),
            "ranked_preds": [],
        },
    ]
    report = error_analysis.build_error_report(cases)
    assert report["n_cases"] == 2  # OPTIONAL excluded
    assert report["error_counts"][error_analysis.CORRECT] == 1
    assert report["error_counts"][error_analysis.NO_PREDICTION] == 1


# --- audit ---------------------------------------------------------------------


def test_audit_new_case_decision():
    gold_rows = [{"case_id": "v2_dev_bp_new", "document_id": "D1", "node_evaluation_mode": "REQUIRED"}]
    result = audit_mod.build_case_label_audit(old_eligibility_by_case={}, gold_rows=gold_rows)
    assert result["rows"][0]["decision"] == "NEW_CASE_REQUIRED"


def test_audit_promote_decision():
    old = {"v2_dev_bp_x": {"case_id": "v2_dev_bp_x", "node_evaluation_mode": "OPTIONAL"}}
    gold_rows = [{"case_id": "v2_dev_bp_x", "document_id": "D1", "node_evaluation_mode": "REQUIRED"}]
    result = audit_mod.build_case_label_audit(old_eligibility_by_case=old, gold_rows=gold_rows)
    assert result["rows"][0]["decision"] == "PROMOTE_TO_REQUIRED"


def test_audit_keep_decision():
    old = {"v2_dev_bp_x": {"case_id": "v2_dev_bp_x", "node_evaluation_mode": "REQUIRED"}}
    gold_rows = [{"case_id": "v2_dev_bp_x", "document_id": "D1", "node_evaluation_mode": "REQUIRED"}]
    result = audit_mod.build_case_label_audit(old_eligibility_by_case=old, gold_rows=gold_rows)
    assert result["rows"][0]["decision"] == "KEEP_REQUIRED"


def test_audit_demote_decision():
    old = {"v2_dev_bp_x": {"case_id": "v2_dev_bp_x", "node_evaluation_mode": "REQUIRED"}}
    gold_rows = [{"case_id": "v2_dev_bp_x", "document_id": "D1", "node_evaluation_mode": "OPTIONAL"}]
    result = audit_mod.build_case_label_audit(old_eligibility_by_case=old, gold_rows=gold_rows)
    assert result["rows"][0]["decision"] == "DEMOTE_TO_OPTIONAL"


def test_audit_by_decision_counts_sum_to_n_cases():
    old = {}
    gold_rows = [
        {"case_id": "a", "document_id": "D1", "node_evaluation_mode": "REQUIRED"},
        {"case_id": "b", "document_id": "D1", "node_evaluation_mode": "AMBIGUOUS"},
        {"case_id": "c", "document_id": "D1", "node_evaluation_mode": "NOT_APPLICABLE"},
    ]
    result = audit_mod.build_case_label_audit(old_eligibility_by_case=old, gold_rows=gold_rows)
    assert sum(result["by_decision"].values()) == 3
    assert result["n_cases"] == 3
