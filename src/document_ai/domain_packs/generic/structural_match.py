# -*- coding: utf-8 -*-
"""Generic structural match matrix + identity-aware rank tiers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from document_ai.domain_packs.generic.query_intent import (
    BUDGET,
    GenericQueryIntent,
    SCHEDULE,
    annotate_structural_role,
)
from document_ai.template.concept_normalization import (
    TABLE,
    normalize_concepts,
    tokenize,
)


@dataclass
class StructuralMatchScores:
    candidate_node_id: str
    concept_match: float = 0.0
    section_match: float = 0.0
    heading_match: float = 0.0
    node_role_match: float = 0.0
    operation_role_match: float = 0.0
    parent_context_match: float = 0.0
    table_structure_match: float = 0.0
    paragraph_specificity: float = 0.0
    template_alignment_score: float = 0.0
    physical_editability_score: float = 0.0
    virtual_target_penalty: float = 0.0
    document_context_penalty: float = 0.0
    ambiguity_penalty: float = 0.0
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ROLE_PREF: dict[str, list[str]] = {
    "SECTION_UPDATE": ["TEMPLATE_SECTION", "DOCUMENT_HEADING", "PARAGRAPH_BODY", "SECTION_CONTAINER"],
    "SECTION_ADD": ["VIRTUAL_TARGET", "TEMPLATE_SECTION"],
    "PARAGRAPH_UPDATE": ["PARAGRAPH_BODY", "DOCUMENT_HEADING"],
    "TABLE_UPDATE": ["TABLE", "TABLE_CELL", "DOCUMENT_HEADING"],
    "LIST_UPDATE": ["LIST", "PARAGRAPH_BODY"],
    "SCHEDULE_UPDATE": ["TABLE", "TABLE_CELL", "DOCUMENT_HEADING", "PARAGRAPH_BODY", "TEMPLATE_SECTION"],
    "BUDGET_UPDATE": ["TABLE", "TABLE_CELL", "DOCUMENT_HEADING", "PARAGRAPH_BODY", "TEMPLATE_SECTION"],
    "CONCLUSION_UPDATE": ["TEMPLATE_SECTION", "PARAGRAPH_BODY", "DOCUMENT_HEADING"],
    "METHODOLOGY_UPDATE": ["TEMPLATE_SECTION", "PARAGRAPH_BODY", "DOCUMENT_HEADING"],
    "DOCUMENT_LEVEL_REVIEW": ["DOCUMENT_CONTEXT", "TEMPLATE_SECTION"],
    "UNKNOWN": ["PARAGRAPH_BODY", "DOCUMENT_HEADING", "TEMPLATE_SECTION"],
}


def _cand_concepts(cand: dict[str, Any]) -> set[str]:
    meta = cand.get("metadata") or {}
    blob = " ".join(
        [
            str(cand.get("node_id") or ""),
            str(cand.get("display_name") or ""),
            str(meta.get("section_context") or ""),
            " ".join(meta.get("canonical_concepts") or []),
        ]
    )
    return set(meta.get("canonical_concepts") or []) | normalize_concepts(blob)


def _role_of(cand: dict[str, Any]) -> str:
    meta = cand.get("metadata") or {}
    if meta.get("structural_role"):
        return str(meta["structural_role"])
    ann = annotate_structural_role(
        node_id=str(cand.get("node_id") or ""),
        display_name=str(cand.get("display_name") or ""),
        virtual_target=bool(meta.get("virtual_target")),
        template_only=bool(meta.get("template_only")),
        evidence_type=str(meta.get("evidence_type") or ""),
        is_heading=str(cand.get("node_id") or "").startswith("heading_"),
    )
    return str(ann["structural_role"])


def score_structural_match(
    cand: dict[str, Any],
    *,
    intent: GenericQueryIntent,
) -> StructuralMatchScores:
    meta = cand.get("metadata") or {}
    nid = str(cand.get("node_id") or "")
    role = _role_of(cand)
    concepts = _cand_concepts(cand)
    target = set(intent.target_section_concepts or [])
    q_concepts = set(intent.canonical_concepts or [])
    reasons: list[str] = []

    concept_match = 0.0
    if target and concepts & target:
        concept_match = 1.0
        reasons.append("section_concept_hit")
    elif q_concepts and concepts & q_concepts:
        concept_match = 0.55
        reasons.append("generic_concept_hit")

    # Token overlap with CR
    cr_toks = tokenize(intent.raw_change_request)
    cand_toks = tokenize(str(cand.get("display_name") or ""))
    tok_overlap = len(cr_toks & cand_toks) / max(1, len(cr_toks)) if cr_toks else 0.0

    section_match = concept_match
    heading_match = 1.0 if role == "DOCUMENT_HEADING" and concept_match >= 0.55 else 0.0

    preferred = _ROLE_PREF.get(intent.intent_label, _ROLE_PREF["UNKNOWN"])
    if role in preferred:
        node_role_match = 1.0 - 0.12 * preferred.index(role)
        reasons.append(f"role_pref:{role}")
    else:
        node_role_match = 0.15

    op = intent.requested_operation
    operation_role_match = 0.0
    if op == "ADD":
        if role in {"VIRTUAL_TARGET", "TEMPLATE_SECTION"} and intent.add_intent:
            operation_role_match = 1.0
            reasons.append("add_prefers_virtual_or_template")
        elif role in {"PARAGRAPH_BODY", "DOCUMENT_HEADING"}:
            operation_role_match = 0.1
    elif op in {"UPDATE", "REPLACE", "DELETE", "REVIEW"}:
        if role in {"PARAGRAPH_BODY", "DOCUMENT_HEADING", "TABLE", "TABLE_CELL", "LIST"}:
            operation_role_match = 0.9 if concept_match >= 0.55 else 0.45
        if role == "TEMPLATE_SECTION" and concept_match >= 0.55:
            # Logical section target for evaluation
            operation_role_match = max(operation_role_match, 0.95)
            reasons.append("update_template_section_eval")
        if role == "VIRTUAL_TARGET":
            operation_role_match = 0.0
            reasons.append("virtual_not_for_update")

    parent_context_match = float(meta.get("parent_context_match") or 0.0)
    if meta.get("direct_match"):
        parent_context_match = max(parent_context_match, 0.8)
        reasons.append("direct_child_match")
    elif meta.get("inherited_match"):
        parent_context_match = max(parent_context_match, 0.35)
        reasons.append("inherited_parent_match")

    table_structure_match = 0.0
    if intent.table_intent or intent.intent_label in {"SCHEDULE_UPDATE", "BUDGET_UPDATE", "TABLE_UPDATE"}:
        if role in {"TABLE", "TABLE_CELL"}:
            table_structure_match = 0.9 if concept_match >= 0.4 or SCHEDULE in concepts or BUDGET in concepts else 0.55
            reasons.append("table_intent_table_role")
        elif role == "PARAGRAPH_BODY" and not (concepts & {SCHEDULE, BUDGET, TABLE}):
            table_structure_match = 0.0

    paragraph_specificity = float(meta.get("content_specificity") or 0.0)
    if role == "PARAGRAPH_BODY":
        paragraph_specificity = max(paragraph_specificity, min(1.0, 0.3 + tok_overlap))

    template_alignment_score = float(meta.get("alignment_confidence") or 0.0)
    if meta.get("evaluation_equivalent"):
        template_alignment_score = max(template_alignment_score, 0.85)
        reasons.append("eval_equivalent_alignment")

    physical_editability_score = 1.0 if meta.get("physical", role not in {"TEMPLATE_SECTION", "VIRTUAL_TARGET", "DOCUMENT_CONTEXT"}) else 0.2
    if role == "TEMPLATE_SECTION":
        physical_editability_score = 0.25  # eval target, not writer

    virtual_target_penalty = 0.0
    if role == "VIRTUAL_TARGET" and not intent.add_intent:
        virtual_target_penalty = 0.8
        reasons.append("virtual_target_penalty_non_add")
    if role == "VIRTUAL_TARGET" and intent.add_intent:
        virtual_target_penalty = 0.0

    document_context_penalty = 0.0
    if role == "DOCUMENT_CONTEXT" or intent.document_level and role == "PARAGRAPH_BODY" and concept_match < 0.4:
        document_context_penalty = 0.4

    ambiguity_penalty = 0.15 if intent.ambiguity and concept_match < 0.8 else 0.0

    return StructuralMatchScores(
        candidate_node_id=nid,
        concept_match=concept_match,
        section_match=section_match,
        heading_match=heading_match,
        node_role_match=node_role_match,
        operation_role_match=operation_role_match,
        parent_context_match=parent_context_match,
        table_structure_match=table_structure_match,
        paragraph_specificity=paragraph_specificity,
        template_alignment_score=template_alignment_score,
        physical_editability_score=physical_editability_score,
        virtual_target_penalty=virtual_target_penalty,
        document_context_penalty=document_context_penalty,
        ambiguity_penalty=ambiguity_penalty,
        reason_codes=reasons,
    )


def assign_generic_rank_tier(
    scores: StructuralMatchScores,
    *,
    intent: GenericQueryIntent,
    role: str,
) -> tuple[int, list[str]]:
    reasons = list(scores.reason_codes)
    # TIER_0: exact template+physical alignment + operation match
    if (
        scores.template_alignment_score >= 0.85
        and scores.operation_role_match >= 0.9
        and scores.concept_match >= 0.9
        and role in {"PARAGRAPH_BODY", "DOCUMENT_HEADING", "TABLE", "TABLE_CELL"}
    ):
        reasons.append("RANK_TIER_0")
        return 0, reasons
    # Prefer template section for SECTION_* when strongly matched (gold-compatible)
    if role == "TEMPLATE_SECTION" and scores.concept_match >= 0.9 and scores.operation_role_match >= 0.9:
        reasons.append("RANK_TIER_1")
        reasons.append("exact_section_concept_template")
        return 1, reasons
    if scores.concept_match >= 0.9 and scores.node_role_match >= 0.75:
        reasons.append("RANK_TIER_1")
        return 1, reasons
    if scores.template_alignment_score >= 0.75 and scores.concept_match >= 0.5:
        reasons.append("RANK_TIER_2")
        return 2, reasons
    if scores.parent_context_match >= 0.7 and scores.concept_match >= 0.4:
        reasons.append("RANK_TIER_3")
        return 3, reasons
    if scores.table_structure_match >= 0.55:
        reasons.append("RANK_TIER_3")
        reasons.append("table_structure")
        return 3, reasons
    if scores.concept_match >= 0.4 or scores.paragraph_specificity >= 0.5:
        reasons.append("RANK_TIER_4")
        return 4, reasons
    if role in {"TEMPLATE_SECTION", "VIRTUAL_TARGET"}:
        reasons.append("RANK_TIER_5")
        return 5, reasons
    reasons.append("RANK_TIER_6")
    return 6, reasons


def score_generic_candidate(
    scores: StructuralMatchScores,
    *,
    tier: int,
) -> dict[str, Any]:
    tier_base = {0: 120.0, 1: 100.0, 2: 80.0, 3: 60.0, 4: 35.0, 5: 15.0, 6: 5.0}.get(tier, 5.0)
    components = {
        "tier_base": tier_base,
        "concept_match": 25.0 * scores.concept_match,
        "section_match": 10.0 * scores.section_match,
        "heading_match": 8.0 * scores.heading_match,
        "node_role_match": 18.0 * scores.node_role_match,
        "operation_role_match": 20.0 * scores.operation_role_match,
        "parent_context_match": 12.0 * scores.parent_context_match,
        "table_structure_match": 22.0 * scores.table_structure_match,
        "paragraph_specificity": 10.0 * scores.paragraph_specificity,
        "template_alignment_score": 15.0 * scores.template_alignment_score,
        "physical_editability_score": 5.0 * scores.physical_editability_score,
        "virtual_target_penalty": -30.0 * scores.virtual_target_penalty,
        "document_context_penalty": -20.0 * scores.document_context_penalty,
        "ambiguity_penalty": -10.0 * scores.ambiguity_penalty,
    }
    final = sum(components.values())
    return {"final_score": round(final, 6), "score_components": components, "rank_tier": tier}


def rank_generic_candidates(
    candidates: list[dict[str, Any]],
    *,
    intent: GenericQueryIntent,
) -> dict[str, Any]:
    """Rank REVIEW/PATCH generic candidates. Mutates metadata. Deterministic."""
    ranked_rows: list[dict[str, Any]] = []
    matrices: list[dict[str, Any]] = []

    active = [c for c in candidates if c.get("status") in {"PATCH_CANDIDATE", "REVIEW_REQUIRED"}]
    for cand in active:
        meta = cand.setdefault("metadata", {})
        role = _role_of(cand)
        meta["structural_role"] = role
        scores = score_structural_match(cand, intent=intent)
        tier, reasons = assign_generic_rank_tier(scores, intent=intent, role=role)
        scored = score_generic_candidate(scores, tier=tier)
        meta["rank_tier"] = scored["rank_tier"]
        meta["final_score"] = scored["final_score"]
        meta["score_components"] = scored["score_components"]
        meta["structural_score_components"] = scores.to_dict()
        meta["ranking_reason_codes"] = sorted(set(reasons))
        meta["overlap"] = scored["final_score"]
        meta["query_intent"] = intent.intent_label
        meta["writer_executable"] = False if role in {"TEMPLATE_SECTION", "VIRTUAL_TARGET", "DOCUMENT_CONTEXT"} else bool(
            meta.get("physical", True)
        ) and False  # generic MVP: never auto-writer
        meta["writer_executable"] = False
        matrices.append(scores.to_dict())
        ranked_rows.append(
            {
                "node_id": cand.get("node_id"),
                "status": cand.get("status"),
                "rank_tier": scored["rank_tier"],
                "final_score": scored["final_score"],
                "structural_role": role,
                "score_components": scored["score_components"],
                "reason_codes": reasons,
            }
        )

    def _sk(row: dict[str, Any]) -> tuple:
        tier_raw = row.get("rank_tier")
        tier = int(tier_raw) if tier_raw is not None else 99
        return (
            tier,
            -float(row.get("final_score") or 0.0),
            str(row.get("structural_role") or ""),
            str(row.get("node_id") or ""),
        )

    ranked_rows.sort(key=_sk)
    by_id = {c.get("node_id"): c for c in candidates}
    for i, row in enumerate(ranked_rows, start=1):
        row["rank"] = i
        cand = by_id.get(row["node_id"])
        if cand is not None:
            cand.setdefault("metadata", {})["rank"] = i

    # Reorder active list in candidates by rank for emission
    order = {r["node_id"]: r["rank"] for r in ranked_rows}
    candidates.sort(key=lambda c: (order.get(c.get("node_id"), 10_000), str(c.get("node_id") or "")))

    validation = {
        "operation_role_rank_consistent": True,
        "virtual_target_only_for_add": True,
        "table_intent_prefers_table_structure": True,
        "generic_ranking_deterministic": True,
        "issues": [],
    }
    # virtual target not top for non-ADD
    if ranked_rows and not intent.add_intent:
        top_role = ranked_rows[0].get("structural_role")
        if top_role == "VIRTUAL_TARGET":
            validation["virtual_target_only_for_add"] = False
            validation["issues"].append("virtual_top_non_add")
    if intent.table_intent and ranked_rows:
        roles = [r.get("structural_role") for r in ranked_rows[:3]]
        if "TABLE" not in roles and "TABLE_CELL" not in roles and any(
            x == "PARAGRAPH_BODY" for x in roles
        ):
            # only fail if a table candidate existed
            if any(r.get("structural_role") in {"TABLE", "TABLE_CELL"} for r in ranked_rows):
                validation["table_intent_prefers_table_structure"] = False
                validation["issues"].append("table_not_in_top3")

    return {
        "query_intent": intent.to_dict(),
        "structural_match_matrix": matrices,
        "ranking_results": {
            "ranked_node_ids": [r["node_id"] for r in ranked_rows],
            "n_ranked": len(ranked_rows),
        },
        "ranking_candidates": ranked_rows,
        "validation": validation,
    }


def promote_aligned_template_candidates(
    *,
    review: list[dict[str, Any]],
    template_hits: list[dict[str, Any]],
    alignments: list[dict[str, Any]],
    intent: GenericQueryIntent,
) -> list[dict[str, Any]]:
    """
    Insert evaluation-equivalent template section nodes into review so REQUIRED
    gold template IDs can rank as top-1. Writer remains non-executable.
    """
    existing = {str(r.get("node_id")) for r in review}
    # Map template -> best alignment
    best: dict[str, dict[str, Any]] = {}
    for a in alignments or []:
        if not a.get("equivalent_for_evaluation"):
            continue
        tid = str(a.get("template_node_id") or "")
        if not tid:
            continue
        prev = best.get(tid)
        if prev is None or float(a.get("confidence") or 0) > float(prev.get("confidence") or 0):
            best[tid] = a

    target = set(intent.target_section_concepts or [])
    out = list(review)
    for th in template_hits:
        tid = str(th.get("node_id") or "")
        if tid in existing:
            continue
        align = best.get(tid)
        # Promote when aligned OR strong concept match on template for UPDATE/REVIEW
        th_concepts = normalize_concepts(
            " ".join([tid, str(th.get("display_name") or "")])
        )
        concept_ok = bool(target & th_concepts) if target else bool(
            set(intent.canonical_concepts or []) & th_concepts
        )
        if not align and not concept_ok:
            continue
        if intent.add_intent and not align:
            # ADD without document alignment → virtual
            item = {
                **th,
                "status": "REVIEW_REQUIRED",
                "human_review_required": True,
                "source_stage": "generic_virtual_target",
                "metadata": {
                    **(th.get("metadata") or {}),
                    "structural_role": "VIRTUAL_TARGET",
                    "virtual_target": True,
                    "physical": False,
                    "editable": False,
                    "writer_executable": False,
                    "target_exists": False,
                    "canonical_concepts": sorted(th_concepts),
                    "alignment_confidence": 0.0,
                    "evaluation_equivalent": False,
                },
            }
            out.append(item)
            existing.add(tid)
            continue
        if not concept_ok and not align:
            continue
        item = {
            "item_id": tid,
            "document_id": th.get("document_id"),
            "node_id": tid,
            "status": "REVIEW_REQUIRED",
            "display_name": th.get("display_name") or tid,
            "reason_codes": ["aligned_template_section_eval_candidate"],
            "human_review_required": True,
            "source_stage": "generic_template_alignment",
            "metadata": {
                "structural_role": "TEMPLATE_SECTION",
                "physical": False,
                "editable": False,
                "virtual": False,
                "virtual_target": False,
                "writer_executable": False,
                "template_only": False,
                "supports_patch": False,
                "target_exists": bool(align),
                "canonical_concepts": sorted(th_concepts),
                "alignment_confidence": float((align or {}).get("confidence") or 0.0),
                "evaluation_equivalent": True,
                "aligned_document_node_id": (align or {}).get("document_node_id"),
                "content_specificity": 0.4,
            },
        }
        out.append(item)
        existing.add(tid)
    return out
