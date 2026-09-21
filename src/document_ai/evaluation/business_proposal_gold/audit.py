# -*- coding: utf-8 -*-
"""Case labeling audit table: old (pre-Cycle6) mode vs. new sealed gold mode."""

from __future__ import annotations

from typing import Any

DECISION_TAXONOMY = frozenset(
    {
        "NEW_CASE_REQUIRED",
        "NEW_CASE_AMBIGUOUS",
        "NEW_CASE_OPTIONAL",
        "NEW_CASE_NOT_APPLICABLE",
        "PROMOTE_TO_REQUIRED",
        "PROMOTE_TO_AMBIGUOUS",
        "DEMOTE_TO_OPTIONAL",
        "DEMOTE_TO_NOT_APPLICABLE",
        "KEEP_NOT_APPLICABLE",
        "KEEP_OPTIONAL",
        "KEEP_REQUIRED",
        "KEEP_AMBIGUOUS",
        "NO_CHANGE",
    }
)


def _decision(old_mode: str | None, new_mode: str) -> str:
    if old_mode is None or old_mode == "UNLABELED":
        return f"NEW_CASE_{new_mode}"
    if old_mode == new_mode:
        return f"KEEP_{new_mode}"
    rank = {"NOT_APPLICABLE": 0, "OPTIONAL": 1, "AMBIGUOUS": 2, "REQUIRED": 3}
    if rank.get(new_mode, 0) > rank.get(old_mode, 0):
        if new_mode == "REQUIRED":
            return "PROMOTE_TO_REQUIRED"
        if new_mode == "AMBIGUOUS":
            return "PROMOTE_TO_AMBIGUOUS"
        return f"PROMOTE_TO_{new_mode}"
    if new_mode == "OPTIONAL":
        return "DEMOTE_TO_OPTIONAL"
    if new_mode == "NOT_APPLICABLE":
        return "DEMOTE_TO_NOT_APPLICABLE"
    return "NO_CHANGE"


def build_case_label_audit(
    *,
    old_eligibility_by_case: dict[str, dict[str, Any]],
    gold_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    decision_counts: dict[str, int] = {}
    for gold in gold_rows:
        cid = gold["case_id"]
        old = old_eligibility_by_case.get(cid)
        old_mode = old.get("node_evaluation_mode") if old else None
        new_mode = gold["node_evaluation_mode"]
        decision = _decision(old_mode, new_mode)
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        rows.append(
            {
                "case_id": cid,
                "document_id": gold.get("document_id"),
                "old_mode": old_mode or "UNLABELED",
                "new_mode": new_mode,
                "decision": decision,
                "expected_physical_node_type": gold.get("expected_physical_node_type"),
                "expected_template_node_id": gold.get("expected_template_node_id"),
                "label_confidence": gold.get("label_confidence"),
                "rationale_excerpt": (gold.get("label_rationale") or "")[:200],
            }
        )
    by_mode: dict[str, int] = {}
    for r in rows:
        by_mode[r["new_mode"]] = by_mode.get(r["new_mode"], 0) + 1
    return {
        "n_cases": len(rows),
        "by_new_mode": by_mode,
        "by_decision": decision_counts,
        "rows": sorted(rows, key=lambda r: r["case_id"]),
    }
