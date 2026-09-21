# -*- coding: utf-8 -*-
"""Official Business Proposal node metrics (gold-based), computed AFTER labels
are projected — separate from the prediction-only proxy intent-grounding
metric (see below). Uses the existing (unchanged) retrieval-metric primitives;
this module does not alter ranking / matching logic anywhere.
"""

from __future__ import annotations

from typing import Any

from document_ai.evaluation.document_set.retrieval_metrics import mrr, rank_nodes, recall_at_k


def _safe_div(n: float, d: float) -> float | None:
    return (float(n) / float(d)) if d else None


def compute_official_business_proposal_metrics(
    calibrated_cases: list[dict[str, Any]],
    *,
    case_domain_by_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    """calibrated_cases: same shape evaluator.py already builds
    (case_id, mode, gold_ids, acceptable, groups, ranked_preds, ...).

    Filters to domain == 'business_proposal' AND mode == 'REQUIRED'. Returns
    N/A (``None``) fields when the REQUIRED denominator is zero, instead of a
    misleading 0.0.
    """
    domain_by_id = case_domain_by_id or {}
    required = [
        c
        for c in calibrated_cases
        if c.get("mode") == "REQUIRED"
        and (domain_by_id.get(c.get("case_id"), c.get("domain")) == "business_proposal")
    ]
    n = len(required)
    if n == 0:
        return {
            "n_required": 0,
            "required_node_top1": None,
            "required_node_recall_at_3": None,
            "required_node_recall_at_5": None,
            "required_node_mrr": None,
            "status": "NOT_APPLICABLE_ZERO_DENOMINATOR",
            "note": "No BUSINESS_PROPOSAL REQUIRED cases found — labels may not be projected yet.",
        }

    top1 = r3 = r5 = mrrs = 0.0
    per_case: list[dict[str, Any]] = []
    for c in required:
        gold = set(c.get("gold_ids") or [])
        acc = set(c.get("acceptable") or [])
        ranked = rank_nodes(c.get("ranked_preds") or [])
        t1 = recall_at_k(gold, ranked, 1, acc)
        t3 = recall_at_k(gold, ranked, 3, acc)
        t5 = recall_at_k(gold, ranked, 5, acc)
        m = mrr(gold, ranked, acc)
        top1 += t1
        r3 += t3
        r5 += t5
        mrrs += m
        per_case.append(
            {
                "case_id": c.get("case_id"),
                "top1_hit": bool(t1),
                "recall_at_3": t3,
                "recall_at_5": t5,
                "reciprocal_rank": m,
                "top1_prediction": (ranked[0].get("node_id") if ranked else None),
            }
        )

    return {
        "n_required": n,
        "required_node_top1": _safe_div(top1, n),
        "required_node_recall_at_3": _safe_div(r3, n),
        "required_node_recall_at_5": _safe_div(r5, n),
        "required_node_mrr": _safe_div(mrrs, n),
        "status": "OK",
        "per_case": per_case,
    }


def compute_proxy_intent_grounding_metrics(
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prediction-only proxy metric: CR -> preferred template mapping vs. Top-1/@3
    prediction. Does NOT read gold. ``cases``: list of
    {case_id, change_request, ranked_preds}.
    """
    from document_ai.domain_packs.business_proposal.query_intent import (
        parse_business_proposal_query_intent,
    )

    n = len(cases)
    if n == 0:
        return {
            "n_cases": 0,
            "intent_grounding_top1": None,
            "intent_grounding_recall_at_3": None,
            "status": "NOT_APPLICABLE_ZERO_DENOMINATOR",
        }
    top1 = r3 = 0.0
    per_case = []
    for c in cases:
        intent = parse_business_proposal_query_intent(c.get("change_request") or "")
        target = intent.preferred_template_node_id
        ranked = rank_nodes(c.get("ranked_preds") or [])
        top_ids = [str(x.get("node_id")) for x in ranked]
        hit1 = bool(target and top_ids[:1] and top_ids[0] == target)
        hit3 = bool(target and target in top_ids[:3])
        top1 += float(hit1)
        r3 += float(hit3)
        per_case.append({"case_id": c.get("case_id"), "preferred_template_node_id": target, "hit1": hit1, "hit3": hit3})
    return {
        "n_cases": n,
        "intent_grounding_top1": _safe_div(top1, n),
        "intent_grounding_recall_at_3": _safe_div(r3, n),
        "status": "OK",
        "per_case": per_case,
        "note": "Prediction-only proxy; does not read gold labels.",
    }
