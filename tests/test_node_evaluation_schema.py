# -*- coding: utf-8 -*-
"""Node evaluation eligibility schema & validation."""

from __future__ import annotations

from document_ai.evaluation.document_set.node_evaluation import (
    EXCLUDED_FROM_STRICT,
    STRICT_MODES,
    compute_calibrated_node_metrics,
    validate_eligibility_row,
)
from document_ai.evaluation.document_set.validation import validate_benchmark_bundle


def test_required_mode_included_in_strict():
    assert "REQUIRED" in STRICT_MODES
    assert "REQUIRED" not in EXCLUDED_FROM_STRICT


def test_optional_excluded_from_strict():
    assert "OPTIONAL" in EXCLUDED_FROM_STRICT


def test_not_applicable_excluded_from_strict():
    assert "NOT_APPLICABLE" in EXCLUDED_FROM_STRICT


def test_unlabeled_excluded_from_strict():
    assert "UNLABELED" in EXCLUDED_FROM_STRICT


def test_ambiguous_requires_group():
    issues = validate_eligibility_row(
        {"node_evaluation_mode": "AMBIGUOUS", "acceptable_node_groups": [], "acceptable_node_ids": []}
    )
    assert any("AMBIGUOUS_missing_group" in i for i in issues)


def test_ambiguous_ok_with_group():
    issues = validate_eligibility_row(
        {
            "node_evaluation_mode": "AMBIGUOUS",
            "acceptable_node_groups": [["a", "b"]],
        }
    )
    assert not issues


def test_required_missing_gold():
    issues = validate_eligibility_row({"node_evaluation_mode": "REQUIRED"})
    assert any("REQUIRED_missing_gold" in i for i in issues)


def test_required_ok_with_primary():
    issues = validate_eligibility_row(
        {"node_evaluation_mode": "REQUIRED", "primary_node_id": "n1"}
    )
    assert not issues


def test_invalid_mode():
    issues = validate_eligibility_row({"node_evaluation_mode": "WEIRD"})
    assert any("invalid_mode" in i for i in issues)


def test_strict_metrics_exclude_optional_na():
    cases = [
        {"mode": "REQUIRED", "gold_ids": {"g1"}, "acceptable": set(), "groups": [], "ranked_preds": [{"node_id": "g1", "score": 1}]},
        {"mode": "OPTIONAL", "gold_ids": set(), "acceptable": set(), "groups": [], "ranked_preds": [{"node_id": "x", "score": 1}], "specific_node_grounding": True},
        {"mode": "NOT_APPLICABLE", "gold_ids": set(), "acceptable": set(), "groups": [], "ranked_preds": []},
    ]
    m = compute_calibrated_node_metrics(cases)
    assert m["n_required"] == 1
    assert m["strict_denominator"] == 1
    assert m["n_optional"] == 1
    assert m["not_applicable_count"] == 1
    assert m["required_node_top1"] == 1.0


def test_unlabeled_warning_in_bundle():
    class C:
        case_id = "c1"

    bundle = {
        "cases": [C()],
        "gold": {
            "document_impacts": [{"case_id": "c1"}],
            "node_impacts": [],
            "node_evaluation_eligibility": [
                {"case_id": "c1", "node_evaluation_mode": "UNLABELED"}
            ],
        },
    }
    v = validate_benchmark_bundle(bundle)
    assert v["status"] in {"VALID", "VALID_WITH_WARNINGS"}
    assert any("unlabeled" in w for w in v["warnings"])


def test_required_without_gold_invalid_bundle():
    class C:
        case_id = "c1"

    bundle = {
        "cases": [C()],
        "gold": {
            "document_impacts": [{"case_id": "c1"}],
            "node_impacts": [],
            "node_evaluation_eligibility": [
                {"case_id": "c1", "node_evaluation_mode": "REQUIRED"}
            ],
        },
    }
    v = validate_benchmark_bundle(bundle)
    assert v["status"] == "INVALID"
    assert any("REQUIRED_without_gold" in i for i in v["issues"])
