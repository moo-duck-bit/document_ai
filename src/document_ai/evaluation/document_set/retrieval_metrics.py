# -*- coding: utf-8 -*-
"""Node retrieval metrics."""

from __future__ import annotations

from typing import Any


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def rank_nodes(preds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        preds,
        key=lambda x: (-float(x.get("score") or 0.0), str(x.get("node_id") or "")),
    )


def recall_at_k(
    gold_node_ids: set[str],
    ranked: list[dict[str, Any]],
    k: int,
    acceptable: set[str] | None = None,
) -> float:
    if not gold_node_ids:
        return 1.0 if not ranked else 0.0
    allowed = set(gold_node_ids) | (acceptable or set())
    top = {str(x.get("node_id")) for x in ranked[:k]}
    return 1.0 if top & allowed else 0.0


def mrr(
    gold_node_ids: set[str],
    ranked: list[dict[str, Any]],
    acceptable: set[str] | None = None,
) -> float:
    allowed = set(gold_node_ids) | (acceptable or set())
    for i, x in enumerate(ranked, start=1):
        if str(x.get("node_id")) in allowed:
            return 1.0 / i
    return 0.0


def compute_node_retrieval_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """cases: [{gold_ids, acceptable, ranked_preds}]"""
    top1, r3, r5, mrrs = [], [], [], []
    exact = alt = no_cand = 0
    n = len(cases)
    for c in cases:
        gold = set(c.get("gold_ids") or [])
        acc = set(c.get("acceptable") or [])
        ranked = rank_nodes(c.get("ranked_preds") or [])
        top1.append(recall_at_k(gold, ranked, 1, acc))
        r3.append(recall_at_k(gold, ranked, 3, acc))
        r5.append(recall_at_k(gold, ranked, 5, acc))
        mrrs.append(mrr(gold, ranked, acc))
        if not gold and not ranked:
            no_cand += 1
            exact += 1
        elif ranked and str(ranked[0].get("node_id")) in gold:
            exact += 1
        elif ranked and str(ranked[0].get("node_id")) in acc:
            alt += 1
    return {
        "top1_accuracy": _safe_div(sum(top1), n),
        "recall_at_3": _safe_div(sum(r3), n),
        "recall_at_5": _safe_div(sum(r5), n),
        "mrr": _safe_div(sum(mrrs), n),
        "exact_node_match_rate": _safe_div(exact, n),
        "acceptable_alternative_match_rate": _safe_div(alt, n),
        "no_candidate_accuracy": _safe_div(no_cand, n) if n else 0.0,
        "n_cases": n,
    }
