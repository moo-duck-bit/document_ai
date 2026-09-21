# -*- coding: utf-8 -*-
"""Calibrated vs legacy node retrieval metrics."""

from __future__ import annotations

from document_ai.evaluation.document_set.node_evaluation import (
    compute_calibrated_node_metrics,
    compute_legacy_node_metrics,
    group_hit_at_k,
)


def _case(mode, gold, ranked, *, acceptable=None, groups=None, grounding=None):
    return {
        "case_id": "x",
        "mode": mode,
        "gold_ids": set(gold),
        "acceptable": set(acceptable or []),
        "groups": groups or [],
        "ranked_preds": [{"node_id": n, "score": 10 - i} for i, n in enumerate(ranked)],
        "specific_node_grounding": grounding,
    }


def test_required_top1():
    m = compute_calibrated_node_metrics(
        [_case("REQUIRED", ["g"], ["g", "x"])]
    )
    assert m["required_node_top1"] == 1.0


def test_required_recall_at_3():
    m = compute_calibrated_node_metrics(
        [_case("REQUIRED", ["g"], ["a", "b", "g"])]
    )
    assert m["required_node_top1"] == 0.0
    assert m["required_node_recall_at_3"] == 1.0


def test_required_recall_at_5():
    m = compute_calibrated_node_metrics(
        [_case("REQUIRED", ["g"], ["a", "b", "c", "d", "g"])]
    )
    assert m["required_node_recall_at_5"] == 1.0
    assert m["required_node_recall_at_3"] == 0.0


def test_required_mrr():
    m = compute_calibrated_node_metrics(
        [_case("REQUIRED", ["g"], ["a", "g"])]
    )
    assert m["required_node_mrr"] == 0.5


def test_ambiguous_group_hit():
    m = compute_calibrated_node_metrics(
        [
            _case(
                "AMBIGUOUS",
                [],
                ["s1"],
                groups=[["s1", "s2"]],
                acceptable=["s1"],
            )
        ]
    )
    assert m["ambiguous_group_hit_at_1"] == 1.0


def test_group_hit_at_k_helper():
    ranked = [{"node_id": "a"}, {"node_id": "b"}]
    assert group_hit_at_k(ranked, [["b", "c"]], 1) == 0.0
    assert group_hit_at_k(ranked, [["b", "c"]], 2) == 1.0


def test_optional_grounding_coverage():
    m = compute_calibrated_node_metrics(
        [
            _case("OPTIONAL", [], ["n1"], grounding=True),
            _case("OPTIONAL", [], [], grounding=False),
        ]
    )
    assert m["optional_grounding_coverage"] == 0.5
    assert m["n_optional"] == 2


def test_label_coverage():
    m = compute_calibrated_node_metrics(
        [
            _case("REQUIRED", ["g"], ["g"]),
            _case("UNLABELED", [], []),
            _case("NOT_APPLICABLE", [], []),
        ]
    )
    assert m["node_label_coverage"] == 2 / 3
    assert m["unlabeled_case_count"] == 1


def test_zero_denominator_policy():
    m = compute_calibrated_node_metrics([])
    assert m["required_node_top1"] == 0.0
    assert m["n_required"] == 0
    assert m.get("zero_denominator") is True


def test_optional_not_in_required_denominator():
    m = compute_calibrated_node_metrics(
        [
            _case("OPTIONAL", [], ["wrong"], grounding=True),
            _case("REQUIRED", ["g"], ["g"]),
        ]
    )
    assert m["strict_denominator"] == 1
    assert m["required_node_top1"] == 1.0


def test_legacy_penalizes_empty_gold_with_preds():
    legacy_cases = [
        {"gold_ids": set(), "acceptable": set(), "ranked_preds": [{"node_id": "x", "score": 1}]}
    ]
    leg = compute_legacy_node_metrics(legacy_cases)
    assert leg["legacy_node_top1"] == 0.0


def test_empty_gold_empty_pred_legacy_ok():
    leg = compute_legacy_node_metrics(
        [{"gold_ids": set(), "acceptable": set(), "ranked_preds": []}]
    )
    assert leg["legacy_node_top1"] == 1.0


def test_acceptable_alternative_counts_required():
    m = compute_calibrated_node_metrics(
        [_case("REQUIRED", ["g"], ["alt"], acceptable=["alt"])]
    )
    assert m["required_node_top1"] == 1.0
    assert m["acceptable_alternative_match_rate"] == 1.0
