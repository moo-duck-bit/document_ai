# -*- coding: utf-8 -*-
"""Decision quality metrics including False Patch Rate."""

from __future__ import annotations

from typing import Any

from document_ai.evaluation.document_set.metrics import (
    accuracy,
    confusion_matrix,
    macro_f1,
    precision_recall_f1,
)

LABELS = ["PATCH_CANDIDATE", "REVIEW_REQUIRED", "UNRELATED"]


def compute_decision_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    false_patch = sum(
        1 for t, p in zip(y_true, y_pred) if t != "PATCH_CANDIDATE" and p == "PATCH_CANDIDATE"
    )
    false_review = sum(
        1 for t, p in zip(y_true, y_pred) if t != "REVIEW_REQUIRED" and p == "REVIEW_REQUIRED"
    )
    miss = sum(
        1 for t, p in zip(y_true, y_pred) if t == "PATCH_CANDIDATE" and p != "PATCH_CANDIDATE"
    )
    n = len(y_true) or 1
    return {
        "precision_patch": precision_recall_f1(y_true, y_pred, ["PATCH_CANDIDATE"])["precision"],
        "recall_patch": precision_recall_f1(y_true, y_pred, ["PATCH_CANDIDATE"])["recall"],
        "accuracy": accuracy(y_true, y_pred),
        "macro_f1": macro_f1(y_true, y_pred, LABELS),
        "confusion_matrix": confusion_matrix(y_true, y_pred, LABELS),
        "false_patch_rate": false_patch / n,
        "false_review_rate": false_review / n,
        "miss_rate": miss / n,
        "false_patch_count": false_patch,
        "n": len(y_true),
    }
