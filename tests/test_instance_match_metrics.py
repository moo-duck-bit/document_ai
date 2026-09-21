# -*- coding: utf-8 -*-
"""Instance match metric calibration tests."""


def _compute_instance_metrics(cases):
    """Mirror evaluator duplicate-only denominator logic."""
    dup_n = exact = base_only = review = wrong = na = 0
    for c in cases:
        size = int(c.get("duplicate_group_size") or 1)
        if size <= 1:
            na += 1
            continue
        dup_n += 1
        status = c.get("match_status")
        if status == "EXACT_INSTANCE":
            exact += 1
        elif status == "BASE_ONLY":
            base_only += 1
        elif status == "CORRECT_REVIEW":
            review += 1
        else:
            wrong += 1
    return {
        "duplicate_cases": dup_n,
        "exact_instance_match": (exact / dup_n) if dup_n else None,
        "base_only_match": (base_only / dup_n) if dup_n else None,
        "correct_review": (review / dup_n) if dup_n else None,
        "wrong_instance": (wrong / dup_n) if dup_n else None,
        "not_applicable": na,
        "metric_denominator": dup_n if dup_n else "N/A",
    }


def test_single_instance_na_for_duplicate_metric():
    m = _compute_instance_metrics([{"duplicate_group_size": 1, "match_status": "EXACT_INSTANCE"}])
    assert m["metric_denominator"] == "N/A"
    assert m["exact_instance_match"] is None
    assert m["not_applicable"] == 1


def test_duplicate_exact_instance():
    m = _compute_instance_metrics(
        [
            {"duplicate_group_size": 2, "match_status": "EXACT_INSTANCE"},
            {"duplicate_group_size": 2, "match_status": "EXACT_INSTANCE"},
        ]
    )
    assert m["exact_instance_match"] == 1.0
    assert m["metric_denominator"] == 2


def test_duplicate_base_only():
    m = _compute_instance_metrics([{"duplicate_group_size": 3, "match_status": "BASE_ONLY"}])
    assert m["base_only_match"] == 1.0


def test_correct_review():
    m = _compute_instance_metrics([{"duplicate_group_size": 2, "match_status": "CORRECT_REVIEW"}])
    assert m["correct_review"] == 1.0


def test_wrong_instance():
    m = _compute_instance_metrics([{"duplicate_group_size": 2, "match_status": "WRONG_INSTANCE"}])
    assert m["wrong_instance"] == 1.0


def test_zero_denominator_na():
    m = _compute_instance_metrics([])
    assert m["metric_denominator"] == "N/A"


def test_aggregate_consistency_mixed():
    m = _compute_instance_metrics(
        [
            {"duplicate_group_size": 1, "match_status": "EXACT_INSTANCE"},
            {"duplicate_group_size": 2, "match_status": "EXACT_INSTANCE"},
            {"duplicate_group_size": 2, "match_status": "BASE_ONLY"},
        ]
    )
    assert m["duplicate_cases"] == 2
    assert m["not_applicable"] == 1
    assert m["exact_instance_match"] == 0.5
