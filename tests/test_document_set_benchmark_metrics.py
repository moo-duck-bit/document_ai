# -*- coding: utf-8 -*-
"""Benchmark metrics unit tests."""

from __future__ import annotations

from document_ai.evaluation.document_set.decision_metrics import compute_decision_metrics
from document_ai.evaluation.document_set.error_analysis import classify_case_errors, summarize_errors
from document_ai.evaluation.document_set.latency import summarize_latencies, validate_non_negative
from document_ai.evaluation.document_set.metrics import (
    accuracy,
    confusion_matrix,
    macro_f1,
    precision_recall_f1,
)
from document_ai.evaluation.document_set.retrieval_metrics import (
    compute_node_retrieval_metrics,
    mrr,
    rank_nodes,
    recall_at_k,
)
from document_ai.evaluation.document_set.safety_metrics import build_safety_scorecard
from document_ai.evaluation.document_set.writer_metrics import compute_writer_metrics


def test_binary_precision_recall_f1():
    y_true = ["IMPACTED", "UNRELATED", "IMPACTED", "UNRELATED"]
    y_pred = ["IMPACTED", "UNRELATED", "UNRELATED", "IMPACTED"]
    m = precision_recall_f1(y_true, y_pred, positive=["IMPACTED", "REVIEW_REQUIRED"])
    assert 0.0 <= m["precision"] <= 1.0
    assert 0.0 <= m["recall"] <= 1.0
    assert 0.0 <= m["f1"] <= 1.0


def test_macro_f1_multiclass():
    y_true = ["IMPACTED", "REVIEW_REQUIRED", "UNRELATED"]
    y_pred = ["IMPACTED", "REVIEW_REQUIRED", "UNRELATED"]
    assert macro_f1(y_true, y_pred, ["IMPACTED", "REVIEW_REQUIRED", "UNRELATED"]) == 1.0


def test_confusion_matrix_counts():
    y_true = ["A", "A", "B"]
    y_pred = ["A", "B", "B"]
    cm = confusion_matrix(y_true, y_pred, ["A", "B"])
    assert cm["A"]["A"] == 1
    assert cm["A"]["B"] == 1
    assert cm["B"]["B"] == 1
    assert sum(sum(r.values()) for r in cm.values()) == 3


def test_accuracy():
    assert accuracy(["X", "Y"], ["X", "Y"]) == 1.0
    assert accuracy([], []) == 0.0


def test_recall_at_k_and_mrr():
    ranked = [{"node_id": "n2", "score": 0.9}, {"node_id": "n1", "score": 0.8}]
    ranked = rank_nodes(ranked)
    assert recall_at_k({"n1"}, ranked, 1) == 0.0
    assert recall_at_k({"n1"}, ranked, 2) == 1.0
    assert mrr({"n1"}, ranked) == 0.5


def test_acceptable_alternative_match():
    ranked = [{"node_id": "alt", "score": 1.0}]
    assert recall_at_k({"gold"}, ranked, 1, acceptable={"alt"}) == 1.0


def test_node_retrieval_aggregate():
    m = compute_node_retrieval_metrics(
        [
            {
                "gold_ids": {"a"},
                "acceptable": set(),
                "ranked_preds": [{"node_id": "a", "score": 1.0}],
            },
            {
                "gold_ids": {"b"},
                "acceptable": {"c"},
                "ranked_preds": [{"node_id": "c", "score": 1.0}],
            },
        ]
    )
    assert m["top1_accuracy"] == 1.0
    assert m["recall_at_3"] == 1.0


def test_false_patch_rate():
    y_true = ["UNRELATED", "REVIEW_REQUIRED", "PATCH_CANDIDATE"]
    y_pred = ["PATCH_CANDIDATE", "PATCH_CANDIDATE", "PATCH_CANDIDATE"]
    d = compute_decision_metrics(y_true, y_pred)
    assert d["false_patch_count"] == 2
    assert abs(d["false_patch_rate"] - 2 / 3) < 1e-9


def test_false_review_rate():
    y_true = ["UNRELATED", "PATCH_CANDIDATE"]
    y_pred = ["REVIEW_REQUIRED", "REVIEW_REQUIRED"]
    d = compute_decision_metrics(y_true, y_pred)
    assert d["false_review_rate"] == 1.0


def test_writer_success_and_preservation():
    rows = [
        {
            "gold_should_write": True,
            "pred_attempted": True,
            "pred_applied": True,
            "pred_blocked": False,
            "original_unchanged": True,
            "unauthorized_write": False,
            "rollback_ok": True,
        },
        {
            "gold_should_write": False,
            "pred_attempted": True,
            "pred_applied": False,
            "pred_blocked": True,
            "original_unchanged": True,
            "unauthorized_write": False,
            "rollback_ok": True,
        },
    ]
    m = compute_writer_metrics(rows)
    assert m["apply_success_rate"] == 1.0
    assert m["original_preservation_rate"] == 1.0
    assert m["block_correctness"] == 1.0
    assert m["rollback_success_rate"] == 1.0


def test_latency_percentiles():
    s = summarize_latencies([10, 20, 30, 40, 100])
    assert s["min"] == 10
    assert s["max"] == 100
    assert s["median"] == 30
    assert s["p95"] >= s["median"]


def test_latency_non_negative():
    assert validate_non_negative({"total_ms": 1}) == []
    assert validate_non_negative({"total_ms": -1})


def test_safety_pass():
    card = build_safety_scorecard({})
    assert card["safety_status"] == "PASS"
    assert card["pass"] is True


def test_safety_original_mutation_invalid():
    card = build_safety_scorecard({"source_original_changed_count": 1})
    assert card["safety_status"] == "INVALID"


def test_safety_unauthorized_writer_invalid():
    card = build_safety_scorecard({"unauthorized_writer_attempt_count": 1})
    assert card["safety_status"] == "INVALID"


def test_safety_false_patch_review():
    card = build_safety_scorecard({"false_patch_count": 2})
    assert card["safety_status"] == "REVIEW"


def test_error_taxonomy():
    errs = classify_case_errors(
        "c1",
        [{"document_id": "D", "gold_status": "IMPACTED"}],
        [{"document_id": "D", "predicted_status": "UNRELATED"}],
        [{"node_id": "n1", "gold_status": "PATCH_CANDIDATE"}],
        [{"node_id": "n2", "predicted_status": "PATCH_CANDIDATE"}],
    )
    classes = {e["error_class"] for e in errs}
    assert "DOCUMENT_MISSED" in classes
    s = summarize_errors(errs)
    assert s["total_errors"] >= 1
    assert s["most_frequent"]


def test_tie_rank_deterministic():
    a = rank_nodes([{"node_id": "b", "score": 1.0}, {"node_id": "a", "score": 1.0}])
    b = rank_nodes([{"node_id": "a", "score": 1.0}, {"node_id": "b", "score": 1.0}])
    assert [x["node_id"] for x in a] == [x["node_id"] for x in b] == ["a", "b"]
