# -*- coding: utf-8 -*-
"""Score calibration analysis (scores are ranking scores, not probabilities)."""

from __future__ import annotations

from typing import Any


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def compute_calibration_metrics(
    rows: list[dict[str, Any]],
    *,
    bins: list[float] | None = None,
    high_confidence_threshold: float = 0.8,
) -> dict[str, Any]:
    """
    rows: [{score, correct: bool, predicted_status}]
    NOTE: scores may not be calibrated probabilities — reported explicitly.
    """
    edges = bins or [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 50.0, 150.0]
    # normalize display: map ranking scores >1 into upper bins
    bucket: dict[str, list[int]] = {}
    ece_num = 0.0
    ece_den = 0
    high_wrong = 0
    low_correct = 0
    for r in rows:
        score = float(r.get("score") or 0.0)
        # map tier scores (~10-120) into pseudo-confidence for binning report only
        conf = score
        if score > 1.0:
            conf = min(1.0, score / 130.0)
        correct = bool(r.get("correct"))
        # find bin
        label = "other"
        for i in range(len(edges) - 1):
            if edges[i] <= conf < edges[i + 1] or (i == len(edges) - 2 and conf <= edges[i + 1]):
                label = f"[{edges[i]},{edges[i+1]})"
                break
        bucket.setdefault(label, []).append(1 if correct else 0)
        if conf >= high_confidence_threshold and not correct:
            high_wrong += 1
        if conf < 0.4 and correct:
            low_correct += 1

    bin_stats = []
    for label, hits in sorted(bucket.items()):
        acc = _safe_div(sum(hits), len(hits))
        # expected conf midpoint from label is approximate
        bin_stats.append({"bin": label, "n": len(hits), "accuracy": acc})
        ece_num += abs(acc - 0.5) * len(hits)  # crude if no true conf; documented
        ece_den += len(hits)

    return {
        "score_is_probability": False,
        "note": "Node ranking final_score / overlap is not a calibrated probability.",
        "bins": bin_stats,
        "expected_calibration_error_proxy": _safe_div(ece_num, ece_den),
        "high_confidence_error_count": high_wrong,
        "low_confidence_correct_count": low_correct,
        "n": len(rows),
        "high_confidence_threshold": high_confidence_threshold,
    }
