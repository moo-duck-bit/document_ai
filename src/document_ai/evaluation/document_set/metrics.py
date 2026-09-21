# -*- coding: utf-8 -*-
"""Core classification metrics helpers."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def precision_recall_f1(y_true: list[str], y_pred: list[str], positive: Iterable[str]) -> dict[str, float]:
    pos = set(positive)
    tp = sum(1 for t, p in zip(y_true, y_pred) if t in pos and p in pos)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t not in pos and p in pos)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t in pos and p not in pos)
    prec = _safe_div(tp, tp + fp)
    rec = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * prec * rec, prec + rec) if (prec + rec) else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def accuracy(y_true: list[str], y_pred: list[str]) -> float:
    if not y_true:
        return 0.0
    return sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)


def confusion_matrix(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, Any]:
    matrix = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return matrix


def macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    scores = []
    for lab in labels:
        pr = precision_recall_f1(y_true, y_pred, positive=[lab])
        scores.append(pr["f1"])
    return sum(scores) / len(scores) if scores else 0.0
