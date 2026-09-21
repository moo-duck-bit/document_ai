# -*- coding: utf-8 -*-
"""PR-21: Rank candidates and assign MATCHED / REVIEW / UNMAPPED / INVALID."""

from __future__ import annotations

from typing import Any

from document_ai.semantic_locator.rule_matcher import compute_rule_score
from document_ai.semantic_locator.schema import (
    SemanticLocatorInput,
    SemanticMatchResult,
    TemplateNodeCandidate,
)
from document_ai.semantic_locator.score_fusion import fuse_scores
from document_ai.semantic_locator.semantic_matcher import compute_semantic_score
from document_ai.semantic_locator.thresholds import (
    DEFAULT_THRESHOLDS,
    GENERIC_TEMPLATE_IDS,
    MatchThresholds,
)


def _round(x: float, digits: int) -> float:
    return round(float(x), digits)


def score_all_nodes(
    inp: SemanticLocatorInput,
    nodes: list[TemplateNodeCandidate],
    *,
    thresholds: MatchThresholds | None = None,
) -> list[dict[str, Any]]:
    """Score every node; return sorted rows (combined desc, node_id asc)."""
    th = thresholds or DEFAULT_THRESHOLDS
    rows: list[dict[str, Any]] = []
    for node in nodes:
        rule, rule_reasons, rule_comp = compute_rule_score(inp, node)
        sem, sem_reasons, sem_comp = compute_semantic_score(inp, node)
        combined = fuse_scores(rule, sem)
        reasons = []
        for r in rule_reasons + sem_reasons:
            if r not in reasons:
                reasons.append(r)
        if node.source_requirement_id is None:
            reasons.append("GENERIC_REQUIREMENT_ID_OPTIONAL")
        rows.append(
            {
                "node": node,
                "rule_score": rule,
                "semantic_score": sem,
                "combined_score": combined,
                "reason_codes": reasons,
                "evidence": {
                    "matched_heading_path": list(
                        (node.locator_hints or {}).get("heading_path") or []
                    ),
                    "matched_heading_text": inp.heading_text,
                    "matched_field_label": (node.locator_hints or {}).get("field_label")
                    or node.display_name,
                    "normalized_candidate_text": sem_comp.get(
                        "normalized_candidate_text"
                    ),
                    "normalized_template_text": sem_comp.get(
                        "normalized_template_text"
                    ),
                    "rule_components": rule_comp,
                    "semantic_components": {
                        k: v
                        for k, v in sem_comp.items()
                        if k
                        not in (
                            "normalized_candidate_text",
                            "normalized_template_text",
                        )
                    },
                },
            }
        )
    rows.sort(
        key=lambda r: (-r["combined_score"], r["node"].template_node_id),
    )
    return rows


def decide_status(
    rows: list[dict[str, Any]],
    *,
    inp: SemanticLocatorInput,
    thresholds: MatchThresholds | None = None,
    template_ids_evaluated: list[str] | None = None,
) -> tuple[str, str, list[str], float | None, float | None, float | None]:
    """
    Returns:
      match_status, ambiguity_status, extra_reasons, top1, top2, margin
    """
    th = thresholds or DEFAULT_THRESHOLDS
    extra: list[str] = []
    if not rows:
        return "UNMAPPED", "CLEAR", ["NO_CANDIDATES", "LOW_SCORE"], None, None, None

    top1 = float(rows[0]["combined_score"])
    top2 = float(rows[1]["combined_score"]) if len(rows) > 1 else None
    margin = _round(top1 - top2, th.round_digits) if top2 is not None else None

    # Field evidence: path exact or label/exact
    rule_comp = rows[0]["evidence"].get("rule_components") or {}
    has_strong_rule = (
        rule_comp.get("heading_path_exact", 0) >= 1.0
        or rule_comp.get("exact_text", 0) >= 1.0
        or rule_comp.get("field_label", 0) >= 0.85
    )
    weak_field = (
        rule_comp.get("heading_path_exact", 0) < 1.0
        and rule_comp.get("field_label", 0) < 0.5
        and rule_comp.get("exact_text", 0) < 0.5
    )

    # Same heading matches many fields
    heading = (inp.heading_text or inp.section_name or "").strip()
    same_heading_hits = 0
    if heading:
        for r in rows[:8]:
            rc = r["evidence"].get("rule_components") or {}
            if rc.get("heading_text", 0) >= 0.55:
                same_heading_hits += 1

    # Template ambiguity when searching across templates
    tids = template_ids_evaluated or sorted(
        {r["node"].template_id for r in rows}
    )
    cross_template = len(tids) > 1 and not inp.template_id
    if cross_template and len(rows) >= 2:
        t1 = rows[0]["node"].template_id
        t2 = rows[1]["node"].template_id
        if t1 != t2 and margin is not None and margin < th.score_margin_min:
            extra.append("AMBIGUOUS_TOP_MATCH")

    ambiguous = False
    if margin is not None and margin < th.score_margin_min and top1 >= th.review_min:
        ambiguous = True
        extra.append("AMBIGUOUS_TOP_MATCH")
    if same_heading_hits >= 3 and weak_field:
        ambiguous = True
        extra.append("AMBIGUOUS_TOP_MATCH")
    if top1 >= th.matched_min and not has_strong_rule and weak_field:
        # high semantic but weak rule → REVIEW
        ambiguous = True
        extra.append("AMBIGUOUS_TOP_MATCH")

    if top1 < th.review_min:
        extra.append("LOW_SCORE")
        return "UNMAPPED", "CLEAR", extra, top1, top2, margin

    if ambiguous or (top1 >= th.review_min and top1 < th.matched_min):
        return "REVIEW", "AMBIGUOUS" if ambiguous else "CLEAR", extra, top1, top2, margin

    # MATCHED requires score + margin
    if top1 >= th.matched_min and (
        margin is None or margin >= th.score_margin_min or has_strong_rule
    ):
        if has_strong_rule or (margin is not None and margin >= th.score_margin_min):
            return "MATCHED", "CLEAR", extra, top1, top2, margin
        return "REVIEW", "AMBIGUOUS", extra + ["AMBIGUOUS_TOP_MATCH"], top1, top2, margin

    return "REVIEW", "CLEAR", extra, top1, top2, margin


def build_match_results(
    inp: SemanticLocatorInput,
    nodes: list[TemplateNodeCandidate],
    *,
    match_seq: int,
    thresholds: MatchThresholds | None = None,
    known_template_ids: set[str] | None = None,
) -> list[SemanticMatchResult]:
    """Build ranked SemanticMatchResult list for one locator input."""
    th = thresholds or DEFAULT_THRESHOLDS
    known = known_template_ids or set(GENERIC_TEMPLATE_IDS)

    # Invalid input
    if not inp.locator_candidate_id or not inp.document_id:
        return [
            SemanticMatchResult(
                semantic_match_id=f"SM-{match_seq:04d}-001",
                document_id=inp.document_id or "",
                locator_candidate_id=inp.locator_candidate_id or "",
                template_id=inp.template_id,
                template_node_id=None,
                rule_score=0.0,
                semantic_score=0.0,
                combined_score=0.0,
                rank=1,
                match_status="INVALID",
                reason_codes=["INVALID_LOCATOR_INPUT"],
                evidence={},
                candidate_count=0,
            )
        ]

    if inp.template_id and inp.template_id not in known:
        return [
            SemanticMatchResult(
                semantic_match_id=f"SM-{match_seq:04d}-001",
                document_id=inp.document_id,
                locator_candidate_id=inp.locator_candidate_id,
                template_id=inp.template_id,
                template_node_id=None,
                rule_score=0.0,
                semantic_score=0.0,
                combined_score=0.0,
                rank=1,
                match_status="INVALID",
                reason_codes=["TEMPLATE_NOT_FOUND"],
                evidence={},
                candidate_count=0,
            )
        ]

    scoped = nodes
    if inp.template_id:
        scoped = [n for n in nodes if n.template_id == inp.template_id]
        if not scoped:
            return [
                SemanticMatchResult(
                    semantic_match_id=f"SM-{match_seq:04d}-001",
                    document_id=inp.document_id,
                    locator_candidate_id=inp.locator_candidate_id,
                    template_id=inp.template_id,
                    template_node_id=None,
                    rule_score=0.0,
                    semantic_score=0.0,
                    combined_score=0.0,
                    rank=1,
                    match_status="INVALID",
                    reason_codes=["NODE_NOT_FOUND", "TEMPLATE_MISMATCH"],
                    evidence={},
                    candidate_count=0,
                )
            ]

    rows = score_all_nodes(inp, scoped, thresholds=th)
    status, amb, extra, top1, top2, margin = decide_status(
        rows,
        inp=inp,
        thresholds=th,
        template_ids_evaluated=sorted({n.template_id for n in scoped}),
    )

    results: list[SemanticMatchResult] = []
    # Emit top-N (all scored) with ranks; primary decision on rank 1
    for i, row in enumerate(rows, start=1):
        node: TemplateNodeCandidate = row["node"]
        reasons = list(row["reason_codes"])
        if i == 1:
            for r in extra:
                if r not in reasons:
                    reasons.append(r)
            row_status = status
            row_amb = amb
        else:
            # alternatives stay as REVIEW evidence only if top is MATCHED/REVIEW
            row_status = "REVIEW" if status in ("MATCHED", "REVIEW") else status
            if status == "UNMAPPED":
                row_status = "UNMAPPED"
            row_amb = amb
            if "AMBIGUOUS_TOP_MATCH" not in reasons and amb == "AMBIGUOUS":
                reasons.append("AMBIGUOUS_TOP_MATCH")

        evidence = dict(row["evidence"])
        evidence["top_alternatives"] = [
            {
                "template_node_id": r["node"].template_node_id,
                "combined_score": r["combined_score"],
                "template_id": r["node"].template_id,
            }
            for r in rows[:5]
            if r["node"].template_node_id != node.template_node_id
        ][:3]

        results.append(
            SemanticMatchResult(
                semantic_match_id=f"SM-{match_seq:04d}-{i:03d}",
                document_id=inp.document_id,
                locator_candidate_id=inp.locator_candidate_id,
                template_id=node.template_id,
                template_node_id=node.template_node_id,
                rule_score=row["rule_score"],
                semantic_score=row["semantic_score"],
                combined_score=row["combined_score"],
                rank=i,
                match_status=row_status if i == 1 else (
                    "REVIEW" if row["combined_score"] >= th.review_min else "UNMAPPED"
                ),
                reason_codes=reasons,
                evidence=evidence,
                ambiguity_status=row_amb if i == 1 else "CLEAR",
                score_margin=margin if i == 1 else None,
                top_1_score=top1 if i == 1 else None,
                top_2_score=top2 if i == 1 else None,
                candidate_count=len(rows),
            )
        )

    # If no rows (empty scoped already handled), UNMAPPED
    if not results:
        results.append(
            SemanticMatchResult(
                semantic_match_id=f"SM-{match_seq:04d}-001",
                document_id=inp.document_id,
                locator_candidate_id=inp.locator_candidate_id,
                template_id=inp.template_id,
                template_node_id=None,
                rule_score=0.0,
                semantic_score=0.0,
                combined_score=0.0,
                rank=1,
                match_status="UNMAPPED",
                reason_codes=["NO_CANDIDATES", "LOW_SCORE"],
                evidence={},
                candidate_count=0,
            )
        )

    # Fix: for rank>1 we should not mark as MATCHED; already handled.
    # Re-apply primary status only on rank 1
    if results:
        results[0].match_status = status
        results[0].ambiguity_status = amb
        if status == "UNMAPPED" and (top1 is None or top1 < th.review_min):
            # Keep best-effort evidence but clear definitive binding
            results[0].template_node_id = None
            results[0].template_id = inp.template_id
            results = [results[0]]

    return results
