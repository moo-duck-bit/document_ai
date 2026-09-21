# -*- coding: utf-8 -*-
"""Node evaluation eligibility, stable references, calibrated retrieval metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.evaluation.document_set.retrieval_metrics import (
    mrr,
    rank_nodes,
    recall_at_k,
)

NodeEvaluationMode = Literal[
    "REQUIRED",
    "OPTIONAL",
    "NOT_APPLICABLE",
    "UNLABELED",
    "AMBIGUOUS",
]

STRICT_MODES = frozenset({"REQUIRED"})
AMBIGUOUS_MODES = frozenset({"AMBIGUOUS"})
OPTIONAL_MODES = frozenset({"OPTIONAL"})
EXCLUDED_FROM_STRICT = frozenset({"OPTIONAL", "NOT_APPLICABLE", "UNLABELED"})


@dataclass
class StableNodeReference:
    document_id: str
    node_type: str | None = None
    section_id: str | None = None
    source_locator: dict[str, Any] = field(default_factory=dict)
    identifier_values: list[str] = field(default_factory=list)
    normalized_text_hash: str | None = None
    template_node_id: str | None = None
    fallback_match_policy: list[str] = field(
        default_factory=lambda: [
            "EXACT_NODE_ID",
            "STABLE_LOCATOR",
            "IDENTIFIER_MATCH",
            "TEXT_HASH_MATCH",
            "ACCEPTABLE_GROUP",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def match_stable_reference(
    *,
    predicted_node_id: str,
    predicted_meta: dict[str, Any] | None,
    gold_node_id: str | None,
    acceptable_node_ids: list[str] | None = None,
    acceptable_groups: list[list[str]] | None = None,
    stable_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Match prediction against gold using ordered fallback policies (no free semantic match)."""
    pred = str(predicted_node_id or "")
    meta = predicted_meta or {}
    acc = set(acceptable_node_ids or [])
    policies = list((stable_ref or {}).get("fallback_match_policy") or [
        "EXACT_NODE_ID",
        "STABLE_NODE_ID",
        "STABLE_LOCATOR",
        "IDENTIFIER_MATCH",
        "TEXT_HASH_MATCH",
        "ACCEPTABLE_GROUP",
    ])

    for policy in policies:
        if policy == "EXACT_NODE_ID":
            if gold_node_id and pred == gold_node_id:
                return {"matched": True, "policy": policy}
            if pred in acc:
                return {"matched": True, "policy": policy}
        elif policy == "STABLE_NODE_ID":
            pred_sid = meta.get("stable_node_id")
            gold_sid = (stable_ref or {}).get("stable_node_id")
            if pred_sid and gold_sid and pred_sid == gold_sid:
                return {"matched": True, "policy": policy}
            if pred_sid and pred_sid in acc:
                return {"matched": True, "policy": policy}
        elif policy == "STABLE_LOCATOR":
            if not stable_ref:
                continue
            # wrong document reject
            if stable_ref.get("document_id") and meta.get("document_id"):
                if str(meta.get("document_id")) != str(stable_ref.get("document_id")):
                    continue
            if stable_ref.get("node_type") and meta.get("node_type"):
                if str(meta.get("node_type")) != str(stable_ref.get("node_type")):
                    continue
            loc = stable_ref.get("source_locator") or {}
            pred_loc = meta.get("source_locator") or {}
            if loc and pred_loc and all(pred_loc.get(k) == v for k, v in loc.items()):
                return {"matched": True, "policy": policy}
            if stable_ref.get("section_id") and meta.get("section_id") == stable_ref.get("section_id"):
                return {"matched": True, "policy": policy}
            if stable_ref.get("template_node_id") and pred == stable_ref.get("template_node_id"):
                return {"matched": True, "policy": policy}
        elif policy == "IDENTIFIER_MATCH":
            gold_ids = set(stable_ref.get("identifier_values") or []) if stable_ref else set()
            pred_ids = set(meta.get("matched_identifiers") or meta.get("identifier_values") or [])
            if gold_ids and pred_ids and gold_ids & pred_ids:
                return {"matched": True, "policy": policy}
        elif policy == "TEXT_HASH_MATCH":
            if not stable_ref or not stable_ref.get("normalized_text_hash"):
                continue
            if meta.get("normalized_text_hash") == stable_ref.get("normalized_text_hash"):
                return {"matched": True, "policy": policy}
        elif policy == "ACCEPTABLE_GROUP":
            for group in acceptable_groups or []:
                if pred in group or (gold_node_id and gold_node_id in group and pred in group):
                    return {"matched": True, "policy": policy}
                if pred in group:
                    return {"matched": True, "policy": policy}
    return {"matched": False, "policy": None}


def group_hit_at_k(
    ranked: list[dict[str, Any]],
    groups: list[list[str]],
    k: int,
    *,
    alignments: list[dict[str, Any]] | None = None,
    equivalence_groups: list[dict[str, Any]] | None = None,
) -> float:
    if not groups:
        return 0.0
    from document_ai.template.node_alignment import expand_acceptable_groups_with_alignments

    expanded = expand_acceptable_groups_with_alignments(
        groups, alignments or [], equivalence_groups
    )
    top = {str(x.get("node_id")) for x in ranked[:k]}
    for g in expanded:
        if top & set(g):
            return 1.0
    return 0.0


def compute_legacy_node_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """All cases (legacy behavior including empty-gold pitfalls)."""
    from document_ai.evaluation.document_set.retrieval_metrics import compute_node_retrieval_metrics

    m = compute_node_retrieval_metrics(cases)
    return {
        "legacy_node_top1": m["top1_accuracy"],
        "legacy_node_recall_at_3": m["recall_at_3"],
        "legacy_node_recall_at_5": m["recall_at_5"],
        "legacy_mrr": m["mrr"],
        "exact_node_match_rate": m["exact_node_match_rate"],
        "acceptable_alternative_match_rate": m["acceptable_alternative_match_rate"],
        "no_candidate_accuracy": m["no_candidate_accuracy"],
        "n_cases": m["n_cases"],
    }


def compute_calibrated_node_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """
    cases entries:
      case_id, mode, gold_ids, acceptable, groups, ranked_preds,
      specific_node_grounding (optional bool)
    """
    required = [c for c in cases if c.get("mode") == "REQUIRED"]
    ambiguous = [c for c in cases if c.get("mode") == "AMBIGUOUS"]
    optional = [c for c in cases if c.get("mode") == "OPTIONAL"]
    na = [c for c in cases if c.get("mode") == "NOT_APPLICABLE"]
    unlabeled = [c for c in cases if c.get("mode") == "UNLABELED"]

    def _required_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "required_node_top1": 0.0,
                "required_node_recall_at_3": 0.0,
                "required_node_recall_at_5": 0.0,
                "required_node_mrr": 0.0,
                "exact_node_match_rate": 0.0,
                "acceptable_alternative_match_rate": 0.0,
                "n_required": 0,
                "zero_denominator": True,
            }
        top1, r3, r5, mrrs = [], [], [], []
        exact = alt = 0
        for c in rows:
            gold = set(c.get("gold_ids") or [])
            acc = set(c.get("acceptable") or [])
            ranked = rank_nodes(c.get("ranked_preds") or [])
            # REQUIRED must have gold; empty gold is label error — score 0
            if not gold:
                top1.append(0.0)
                r3.append(0.0)
                r5.append(0.0)
                mrrs.append(0.0)
                continue
            top1.append(recall_at_k(gold, ranked, 1, acc))
            r3.append(recall_at_k(gold, ranked, 3, acc))
            r5.append(recall_at_k(gold, ranked, 5, acc))
            mrrs.append(mrr(gold, ranked, acc))
            if ranked and str(ranked[0].get("node_id")) in gold:
                exact += 1
            elif ranked and str(ranked[0].get("node_id")) in acc:
                alt += 1
        n = len(rows)
        return {
            "required_node_top1": _safe_div(sum(top1), n),
            "required_node_recall_at_3": _safe_div(sum(r3), n),
            "required_node_recall_at_5": _safe_div(sum(r5), n),
            "required_node_mrr": _safe_div(sum(mrrs), n),
            "exact_node_match_rate": _safe_div(exact, n),
            "acceptable_alternative_match_rate": _safe_div(alt, n),
            "n_required": n,
            "zero_denominator": False,
        }

    req_m = _required_block(required)

    # Ambiguous
    g1: list[float] = []
    g3: list[float] = []
    g5: list[float] = []
    best_ranks: list[float] = []
    for c in ambiguous:
        groups = list(c.get("groups") or [])
        if not groups and c.get("acceptable"):
            groups = [list(c.get("acceptable") or [])]
        ranked = rank_nodes(c.get("ranked_preds") or [])
        alignments = list(c.get("alignments") or [])
        equiv = list(c.get("equivalence_groups") or [])
        g1.append(group_hit_at_k(ranked, groups, 1, alignments=alignments, equivalence_groups=equiv))
        g3.append(group_hit_at_k(ranked, groups, 3, alignments=alignments, equivalence_groups=equiv))
        g5.append(group_hit_at_k(ranked, groups, 5, alignments=alignments, equivalence_groups=equiv))
        allowed = set()
        for g in groups:
            allowed.update(g)
        allowed |= set(c.get("acceptable") or [])
        from document_ai.template.node_alignment import expand_acceptable_groups_with_alignments

        for eg in expand_acceptable_groups_with_alignments(groups or [list(allowed)], alignments, equiv):
            allowed.update(eg)
        rank = None
        for i, x in enumerate(ranked, start=1):
            if str(x.get("node_id")) in allowed:
                rank = i
                break
        best_ranks.append(1.0 / rank if rank else 0.0)
    n_amb = len(ambiguous)
    amb_m = {
        "ambiguous_group_hit_at_1": _safe_div(sum(g1), n_amb) if n_amb else 0.0,
        "ambiguous_group_recall_at_3": _safe_div(sum(g3), n_amb) if n_amb else 0.0,
        "ambiguous_group_recall_at_5": _safe_div(sum(g5), n_amb) if n_amb else 0.0,
        "ambiguous_group_mrr": _safe_div(sum(best_ranks), n_amb) if n_amb else 0.0,
        "n_ambiguous": n_amb,
    }

    # Optional grounding
    grounded = 0
    specific = 0
    review_without_node = 0
    for c in optional:
        ranked = rank_nodes(c.get("ranked_preds") or [])
        if c.get("specific_node_grounding") or ranked:
            grounded += 1
        if c.get("specific_node_grounding"):
            specific += 1
        if not ranked and not c.get("specific_node_grounding"):
            review_without_node += 1
    n_opt = len(optional)
    opt_m = {
        "optional_grounding_coverage": _safe_div(grounded, n_opt) if n_opt else 0.0,
        "optional_evidence_precision": _safe_div(specific, grounded) if grounded else 0.0,
        "specific_node_evidence_rate": _safe_div(specific, n_opt) if n_opt else 0.0,
        "review_without_node_rate": _safe_div(review_without_node, n_opt) if n_opt else 0.0,
        "n_optional": n_opt,
    }

    total = len(cases) or 1
    labeled = total - len(unlabeled)
    coverage = {
        "node_label_coverage": _safe_div(labeled, total),
        "required_case_coverage": _safe_div(len(required), total),
        "optional_case_coverage": _safe_div(len(optional), total),
        "ambiguous_case_count": len(ambiguous),
        "not_applicable_count": len(na),
        "unlabeled_case_count": len(unlabeled),
        "n_total": len(cases),
        "strict_denominator": len(required),
    }

    return {
        **req_m,
        **amb_m,
        **opt_m,
        **coverage,
    }


def validate_eligibility_row(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    mode = row.get("node_evaluation_mode")
    if mode not in {
        "REQUIRED",
        "OPTIONAL",
        "NOT_APPLICABLE",
        "UNLABELED",
        "AMBIGUOUS",
    }:
        issues.append(f"invalid_mode:{mode}")
    if mode == "REQUIRED" and not (row.get("primary_node_id") or row.get("gold_node_ids")):
        issues.append("REQUIRED_missing_gold_node")
    if mode == "AMBIGUOUS" and not (
        row.get("acceptable_node_groups") or row.get("acceptable_node_ids")
    ):
        issues.append("AMBIGUOUS_missing_group")
    return issues
