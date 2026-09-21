# -*- coding: utf-8 -*-
"""PR-6: Shadow End-to-End Staged Decision Path.

Connects ACU → B5a (incl. cross-ID) → B5b + provenance → owner proposal
→ shadow B5c → B6 patch plans.

Shadow only — never mutates DOCX / actual B5c / allow_mdsr_patch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.atomic_change import AtomicChangeUnit
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.patch_plan import (
    PatchPlanItem,
    build_shadow_patch_plans,
    compare_legacy_vs_shadow,
    semantic_intent_from_acu,
)
from document_ai.impact.propagation import (
    PropagationTrace,
    WEAK_TOKENS,
    align_design_candidate,
    decide_propagation,
    discover_design_candidates_shadow,
)
from document_ai.impact.semantic_index import RequirementBlock

RecommendationStatus = Literal[
    "CLEAR_OWNER",
    "MULTIPLE_PLAUSIBLE",
    "NO_SAFE_OWNER",
    "NEEDS_REVIEW",
]


@dataclass
class ShadowOwnerProposal:
    atomic_change_id: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    recommended_owner: str | None = None
    recommendation_status: RecommendationStatus | str = "NEEDS_REVIEW"
    evidence: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    requirement_context_id: str | None = None
    shadow_decision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ACUStagedShadowResult:
    atomic_change_id: str
    source_span: str
    requirement_contexts: list[str]
    candidate_designs: list[dict[str, Any]]
    owner_proposal: dict[str, Any]
    shadow_decision: str
    patch_plans: list[dict[str, Any]]
    provenance_summary: dict[str, Any]
    row_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _synthetic_decision(
    req_id: str,
    *,
    status: str = "NEEDS_REVIEW",
    allow_auto_patch: bool = False,
    base: ConsistencyDecision | None = None,
) -> ConsistencyDecision:
    if base is not None:
        return base
    return ConsistencyDecision(
        req_id=req_id,
        document="MDSR",
        status=status,  # type: ignore[arg-type]
        reason="shadow_e2e_prior_context",
        allow_auto_patch=allow_auto_patch,
        fields={},
        evidence={"compatible_facets": [], "conflicting_facets": []},
        confidence=0.0,
    )


def _b3_by_key(b3_decisions: list[dict[str, Any]] | None) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for d in b3_decisions or []:
        rid = d.get("candidate_id") or d.get("candidate")
        doc = d.get("document")
        if rid and doc:
            out[(str(rid), str(doc))] = d
    return out


def _requirement_context_ids(
    consistency: list[ConsistencyDecision],
    b3_decisions: list[dict[str, Any]] | None,
) -> list[str]:
    """MDSR ids usable as requirement context priors (not automatic owners)."""
    ids: list[str] = []
    for d in consistency:
        if d.document == "MDSR" and d.req_id not in ids:
            ids.append(d.req_id)
    for d in b3_decisions or []:
        if d.get("document") == "MDSR" and d.get("judgment") == "IMPACTED":
            rid = d.get("candidate_id") or d.get("candidate")
            if rid and rid not in ids:
                ids.append(str(rid))
    return ids


def _extract_b3_prior_local(
    b3_row: dict[str, Any] | None,
) -> dict[str, Any]:
    if not b3_row:
        return {}
    ev = b3_row.get("evidence") if isinstance(b3_row.get("evidence"), dict) else {}
    return {
        "judgment": b3_row.get("judgment") or "",
        "matched_concepts": list(ev.get("matched_concepts") or []),
        "behavioral_overlap": dict(ev.get("behavioral_overlap") or {}),
        "candidate_spans": list(ev.get("candidate_spans") or []),
        "confidence": float(b3_row.get("confidence") or 0.0),
    }


def _acu_facet_list(acu: AtomicChangeUnit, role: str) -> list[str]:
    if hasattr(acu, "direct_facet_values"):
        return list(acu.direct_facet_values(role) or [])
    return list(getattr(acu, role, None) or [])


def _strong_acu_hits(acu: AtomicChangeUnit, design_text: str) -> list[str]:
    """Non-weak ACU_DIRECT action/object/affected tokens present in design."""
    weak = {w.lower() for w in WEAK_TOKENS}
    blob = (design_text or "").lower()
    hits: list[str] = []
    tokens = (
        _acu_facet_list(acu, "action")
        + _acu_facet_list(acu, "object")
        + _acu_facet_list(acu, "affected_entity")
    )
    for t in tokens:
        if not t:
            continue
        tl = t.lower()
        if tl in weak or tl == "implicit_system":
            continue
        if tl in blob:
            hits.append(t)
    return hits


def _discriminative_ok(
    summary: dict[str, Any],
    *,
    strong_hits: list[str] | None = None,
) -> bool:
    """CLEAR_OWNER gate: requires non-weak ACU↔design hits; rejects generic/prior-only."""
    conflicting = int(summary.get("conflicting_count") or 0)
    derived = int(summary.get("derived_prior_count") or 0)
    direct = int(summary.get("direct_independent_count") or 0)
    strong = list(strong_hits or [])
    if conflicting > 0:
        return False
    # Must have at least one non-weak ACU action/object token in the design.
    # same-ID / prior-only / weak-token overlap alone never qualifies.
    if not strong:
        return False
    # Prior-dominated with no provenance direct still OK if strong hits exist,
    # but prior-only without strong already rejected above.
    if derived > 0 and direct <= 0 and len(strong) == 0:
        return False
    return True


def _score_candidate(
    summary: dict[str, Any],
    acu: AtomicChangeUnit,
    design_text: str,
    *,
    strong_hits: list[str],
) -> float:
    direct = float(summary.get("direct_independent_count") or 0)
    supporting = float(summary.get("supporting_independent_count") or 0)
    generic = float(summary.get("generic_count") or 0)
    derived = float(summary.get("derived_prior_count") or 0)
    conflicting = float(summary.get("conflicting_count") or 0)
    score = (
        2.0 * direct
        + 1.0 * supporting
        + 1.5 * len(strong_hits)
        - 0.5 * generic
        - 0.35 * derived
        - 3.0 * conflicting
    )
    return score


def _evaluate_acu_candidates(
    *,
    acu: AtomicChangeUnit,
    req_contexts: list[str],
    by_key: dict[tuple[str, str], RequirementBlock],
    consistency_by_id: dict[str, ConsistencyDecision],
    b3_map: dict[tuple[str, str], dict[str, Any]],
    b3_decisions: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Per-ACU design candidate evaluation with provenance (shadow only)."""
    evaluated: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()  # req_ctx, design_id, document

    for req_id in req_contexts:
        mdsr = by_key.get((req_id, "MDSR"))
        if not mdsr:
            continue
        decision = consistency_by_id.get(req_id) or _synthetic_decision(req_id)
        # Cross-ID + same-id pool for this requirement context
        pool = discover_design_candidates_shadow(
            req_id, by_key, b3_decisions=b3_decisions
        )
        for cand in pool:
            key = (req_id, cand.design_id, cand.document)
            if key in seen:
                continue
            seen.add(key)
            mddr = cand.block
            b3_prior = _extract_b3_prior_local(
                b3_map.get((req_id, "MDSR")) or b3_map.get((cand.design_id, "MDDR"))
            )
            # Align using ACU span — not whole CR
            align = align_design_candidate(
                acu.source_span,
                mdsr,
                mddr,
                decision=decision,
                b3_prior=b3_prior,
            )
            prov = align.provenance or {}
            summary = dict(prov.get("summary") or {})
            design_text = f"{mddr.title}\n{mddr.body_text}" if mddr else ""
            strong = _strong_acu_hits(acu, design_text)
            score = _score_candidate(summary, acu, design_text, strong_hits=strong)
            ok = _discriminative_ok(summary, strong_hits=strong)
            evaluated.append(
                {
                    "requirement_context_id": req_id,
                    "design_id": cand.design_id,
                    "document": cand.document,
                    "sources": list(cand.sources),
                    "is_same_id": "same_id" in (cand.sources or []),
                    "alignment": align.alignment,
                    "confidence": align.confidence,
                    "score": round(score, 4),
                    "discriminative_ok": ok,
                    "strong_acu_hits": strong,
                    "provenance_summary": summary,
                    "direct_independent_count": summary.get("direct_independent_count", 0),
                    "supporting_independent_count": summary.get(
                        "supporting_independent_count", 0
                    ),
                    "generic_count": summary.get("generic_count", 0),
                    "derived_prior_count": summary.get("derived_prior_count", 0),
                    "conflicting_count": summary.get("conflicting_count", 0),
                    "unique_independent_groups": list(
                        summary.get("unique_independent_groups") or []
                    ),
                    "evidence_lineage_summary": list(
                        summary.get("evidence_lineage_summary") or []
                    ),
                    "reason": align.reason,
                    "_align": align,
                    "_decision": decision,
                    "_mddr": mddr,
                    "_mdsr": mdsr,
                }
            )

    evaluated.sort(
        key=lambda r: (
            -int(r.get("discriminative_ok") or 0),
            -float(r.get("score") or 0.0),
            str(r.get("design_id") or ""),
            str(r.get("requirement_context_id") or ""),
        )
    )
    return evaluated


def _recommend_owner(
    acu: AtomicChangeUnit,
    evaluated: list[dict[str, Any]],
) -> ShadowOwnerProposal:
    if acu.decomposition_status in ("AMBIGUOUS", "NEEDS_REVIEW"):
        return ShadowOwnerProposal(
            atomic_change_id=acu.change_id,
            candidates=[_public_cand(c) for c in evaluated],
            recommended_owner=None,
            recommendation_status="NEEDS_REVIEW",
            evidence={"note": "acu_not_extracted_safely"},
            reason=f"ACU status={acu.decomposition_status}",
        )

    viable = [c for c in evaluated if c.get("discriminative_ok")]
    if not viable:
        # Distinguish prior/generic-only vs empty
        if evaluated and all(
            int(c.get("direct_independent_count") or 0) <= 0 for c in evaluated
        ):
            return ShadowOwnerProposal(
                atomic_change_id=acu.change_id,
                candidates=[_public_cand(c) for c in evaluated],
                recommended_owner=None,
                recommendation_status="NO_SAFE_OWNER",
                evidence={"note": "no_discriminative_direct_evidence"},
                reason="generic-only / prior-only / empty evidence — CLEAR_OWNER forbidden",
            )
        return ShadowOwnerProposal(
            atomic_change_id=acu.change_id,
            candidates=[_public_cand(c) for c in evaluated],
            recommended_owner=None,
            recommendation_status="NO_SAFE_OWNER",
            evidence={"note": "no_viable_candidates"},
            reason="No safe owner with discriminative responsibility evidence",
        )

    top = viable[0]
    # same-ID alone never sufficient — already gated by discriminative_ok
    peers = [
        c
        for c in viable
        if abs(float(c["score"]) - float(top["score"])) <= 0.35
        and c["design_id"] != top["design_id"]
    ]
    if peers:
        return ShadowOwnerProposal(
            atomic_change_id=acu.change_id,
            candidates=[_public_cand(c) for c in evaluated],
            recommended_owner=None,
            recommendation_status="MULTIPLE_PLAUSIBLE",
            evidence={
                "top": _public_cand(top),
                "peers": [_public_cand(p) for p in peers],
            },
            reason="Multiple design candidates with similar discriminative evidence",
            requirement_context_id=str(top.get("requirement_context_id") or ""),
        )

    return ShadowOwnerProposal(
        atomic_change_id=acu.change_id,
        candidates=[_public_cand(c) for c in evaluated],
        recommended_owner=str(top["design_id"]),
        recommendation_status="CLEAR_OWNER",
        evidence={"chosen": _public_cand(top)},
        reason=(
            f"Discriminative evidence for {top['design_id']} "
            f"(score={top['score']}; sources={top.get('sources')})"
        ),
        requirement_context_id=str(top.get("requirement_context_id") or ""),
    )


def _public_cand(c: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in c.items()
        if not str(k).startswith("_")
    }


def _shadow_decision_for_proposal(
    acu: AtomicChangeUnit,
    proposal: ShadowOwnerProposal,
    evaluated: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    """Return (shadow_decision, chosen_evaluated_row_or_none)."""
    status = proposal.recommendation_status
    if status == "NEEDS_REVIEW":
        return "NEEDS_REVIEW", None
    if status == "MULTIPLE_PLAUSIBLE":
        return "NEEDS_REVIEW", None
    if status == "NO_SAFE_OWNER":
        return "NEW_DESIGN_CANDIDATE", None
    # CLEAR_OWNER — run B5c decide on chosen candidate using ACU span alignment
    chosen = next(
        (
            c
            for c in evaluated
            if c.get("design_id") == proposal.recommended_owner
            and c.get("requirement_context_id") == proposal.requirement_context_id
        ),
        None,
    )
    if not chosen:
        chosen = next(
            (c for c in evaluated if c.get("design_id") == proposal.recommended_owner),
            None,
        )
    if not chosen:
        return "NEEDS_REVIEW", None

    align = chosen["_align"]
    decision = chosen["_decision"]
    # Prefer auto-patch eligible decision for shadow decide when B4 was CONSISTENT
    if decision.status == "CONSISTENT" and not decision.allow_auto_patch:
        decision = ConsistencyDecision(
            req_id=decision.req_id,
            document=decision.document,
            status="CONSISTENT",
            reason=decision.reason,
            allow_auto_patch=True,
            fields=decision.fields,
            evidence=decision.evidence,
            confidence=decision.confidence,
        )
    decided = decide_propagation(
        requirement_id=str(chosen.get("requirement_context_id") or acu.change_id),
        design_id=str(chosen.get("design_id") or ""),
        alignment=align,
        decision=decision,
    )
    # If decide says SKIP due to mismatch, keep CLEAR_OWNER analysis but shadow SKIP
    return decided.decision, chosen


def _plans_for_clear_owner(
    *,
    acu: AtomicChangeUnit,
    shadow_decision: str,
    chosen: dict[str, Any],
) -> list[PatchPlanItem]:
    if shadow_decision not in ("PATCH_EXISTING", "EXTEND_EXISTING"):
        return []
    req_id = str(chosen.get("requirement_context_id") or "")
    synth = PropagationTrace(
        source_mdsr_req_id=req_id,
        mdsr_consistency_status="CONSISTENT",
        impacted_mddr_candidate=f"{chosen.get('design_id')} (MDDR)",
        propagation_reason="shadow_e2e_clear_owner",
        outcome="PATCHED",
        design_responsibility_aligned=True,
        allow_mdsr_patch=False,  # never actual
        requirement=req_id,
        design_candidate=str(chosen.get("design_id") or ""),
        propagation_decision=shadow_decision,  # type: ignore[arg-type]
        structured_evidence={
            "matched_responsibilities": list(acu.action + acu.object),
            "matched_facets": ["action", "object"],
            "requirement_spans": [acu.source_span],
            "design_spans": [],
            "direct_traceability": [],
            "conflicts": [],
            "missing_information": [],
        },
        confidence=float(chosen.get("confidence") or 0.0),
    )
    # Intent must stay ACU-scoped (build_shadow_patch_plans uses semantic_intent_from_acu)
    return build_shadow_patch_plans(
        cr_text=acu.source_span,
        acus=[acu],
        traces=[synth],
    )


def run_staged_shadow_e2e(
    *,
    cr_text: str,
    acus: list[AtomicChangeUnit],
    blocks: list[RequirementBlock],
    consistency: list[ConsistencyDecision],
    b3_decisions: list[dict[str, Any]] | None = None,
    actual_traces: list[PropagationTrace] | None = None,
) -> dict[str, Any]:
    """Orchestrate ACU → B5a/b/provenance → owner proposal → shadow B5c → B6.

    Does not modify actual_traces / DOCX. recommended_owner is analysis-only.
    """
    by_key = {(b.req_id, b.document_type): b for b in blocks}
    b3_map = _b3_by_key(b3_decisions)
    consistency_by_id = {
        d.req_id: d for d in consistency if d.document == "MDSR"
    }
    req_contexts = _requirement_context_ids(consistency, b3_decisions)
    if not req_contexts:
        # Still allow cross-ID MDDR-only discovery via a placeholder context if any MDSR exists
        req_contexts = sorted({b.req_id for b in blocks if b.document_type == "MDSR"})[:8]

    acu_results: list[ACUStagedShadowResult] = []
    all_candidates: list[dict[str, Any]] = []
    all_recommendations: list[dict[str, Any]] = []
    all_plans: list[dict[str, Any]] = []

    for acu in acus:
        evaluated = _evaluate_acu_candidates(
            acu=acu,
            req_contexts=req_contexts,
            by_key=by_key,
            consistency_by_id=consistency_by_id,
            b3_map=b3_map,
            b3_decisions=b3_decisions,
        )
        proposal = _recommend_owner(acu, evaluated)
        shadow_decision, chosen = _shadow_decision_for_proposal(acu, proposal, evaluated)
        proposal.shadow_decision = shadow_decision

        plans: list[PatchPlanItem] = []
        if (
            proposal.recommendation_status == "CLEAR_OWNER"
            and chosen is not None
            and shadow_decision in ("PATCH_EXISTING", "EXTEND_EXISTING")
        ):
            plans = _plans_for_clear_owner(
                acu=acu, shadow_decision=shadow_decision, chosen=chosen
            )
        elif proposal.recommendation_status == "MULTIPLE_PLAUSIBLE":
            plans = [
                PatchPlanItem(
                    patch_id=f"PATCH-REV-{acu.change_id}",
                    atomic_change_id=acu.change_id,
                    target_document="",
                    target_id=None,
                    target_field="",
                    operation="REVIEW",
                    semantic_intent=semantic_intent_from_acu(acu),
                    source_cr_span=acu.source_span,
                    justification="MULTIPLE_PLAUSIBLE owners — no auto plan",
                    planning_status="NEEDS_REVIEW",
                    review_reason="multiple_plausible_owners",
                    provenance={"path": "staged_shadow_e2e"},
                )
            ]
        elif proposal.recommendation_status == "NO_SAFE_OWNER":
            plans = [
                PatchPlanItem(
                    patch_id=f"PATCH-NEW-{acu.change_id}",
                    atomic_change_id=acu.change_id,
                    target_document="MDDR",
                    target_id=None,
                    target_field="",
                    operation="REVIEW",
                    semantic_intent=semantic_intent_from_acu(acu),
                    source_cr_span=acu.source_span,
                    justification="NO_SAFE_OWNER — NEW_DESIGN / REVIEW",
                    planning_status="NEEDS_REVIEW",
                    review_reason="no_safe_owner",
                    provenance={"path": "staged_shadow_e2e", "shadow_decision": shadow_decision},
                )
            ]

        pub_cands = [_public_cand(c) for c in evaluated]
        all_candidates.append(
            {
                "atomic_change_id": acu.change_id,
                "source_span": acu.source_span,
                "requirement_contexts": req_contexts,
                "candidates": pub_cands,
            }
        )
        all_recommendations.append(proposal.to_dict())
        plan_dicts = [p.to_dict() for p in plans]
        all_plans.extend(plan_dicts)

        top_summary = {}
        if chosen:
            top_summary = dict(chosen.get("provenance_summary") or {})
        elif evaluated:
            top_summary = dict(evaluated[0].get("provenance_summary") or {})

        row = {
            "ACU": acu.change_id,
            "Requirement Context": proposal.requirement_context_id or ",".join(req_contexts[:3]),
            "Candidate Designs": [c.get("design_id") for c in pub_cands],
            "Owner Status": proposal.recommendation_status,
            "Shadow Decision": shadow_decision,
            "Patch Plan": [
                f"{p.get('target_document')}:{p.get('target_id')}:{p.get('target_field')}"
                for p in plan_dicts
                if p.get("planning_status") == "PLANNED"
            ]
            or [p.get("planning_status") for p in plan_dicts],
        }
        acu_results.append(
            ACUStagedShadowResult(
                atomic_change_id=acu.change_id,
                source_span=acu.source_span,
                requirement_contexts=list(req_contexts),
                candidate_designs=pub_cands,
                owner_proposal=proposal.to_dict(),
                shadow_decision=shadow_decision,
                patch_plans=plan_dicts,
                provenance_summary=top_summary,
                row_summary=row,
            )
        )

    status_counts = {
        "CLEAR_OWNER": 0,
        "MULTIPLE_PLAUSIBLE": 0,
        "NO_SAFE_OWNER": 0,
        "NEEDS_REVIEW": 0,
    }
    for r in all_recommendations:
        st = r.get("recommendation_status") or "NEEDS_REVIEW"
        if st in status_counts:
            status_counts[st] += 1

    legacy_cmp = compare_legacy_vs_shadow(
        cr_text=cr_text,
        traces=actual_traces or [],
        plans=[
            PatchPlanItem(
                patch_id=p.get("patch_id") or "PATCH",
                atomic_change_id=p.get("atomic_change_id") or "",
                target_document=p.get("target_document") or "",
                target_id=p.get("target_id"),
                target_field=p.get("target_field") or "",
                operation=p.get("operation") or "REVIEW",
                semantic_intent=p.get("semantic_intent") or "",
                source_cr_span=p.get("source_cr_span") or "",
                justification=p.get("justification") or "",
                owner_evidence_ids=list(p.get("owner_evidence_ids") or p.get("evidence_ids") or []),
                provenance=dict(p.get("provenance") or {}),
                planning_status=p.get("planning_status") or "NEEDS_REVIEW",
                review_reason=p.get("review_reason"),
            )
            for p in all_plans
        ],
    )

    return {
        "stage": "staged_shadow_e2e",
        "note": (
            "Shadow staged path is analysis-only. "
            "recommended_owner is NOT the actual patch owner. "
            "Does not mutate DOCX / allow_mdsr_patch / actual B5c."
        ),
        "source_cr": cr_text,
        "summary": {
            "total_acus": len(acus),
            "clear_owners": status_counts["CLEAR_OWNER"],
            "multiple_plausible": status_counts["MULTIPLE_PLAUSIBLE"],
            "no_safe_owner": status_counts["NO_SAFE_OWNER"],
            "needs_review": status_counts["NEEDS_REVIEW"],
            "planned_patches": sum(
                1 for p in all_plans if p.get("planning_status") == "PLANNED"
            ),
        },
        "acu_results": [r.to_dict() for r in acu_results],
        "table_rows": [r.row_summary for r in acu_results],
        "acu_owner_candidates": all_candidates,
        "acu_owner_recommendations": all_recommendations,
        "staged_patch_plans": all_plans,
        "legacy_vs_staged": {
            **legacy_cmp,
            "actual_propagation_decisions": [
                {
                    "req_id": t.source_mdsr_req_id,
                    "propagation_decision": t.propagation_decision,
                    "allow_mdsr_patch": t.allow_mdsr_patch,
                }
                for t in (actual_traces or [])
            ],
            "staged_shadow_decisions": [
                {
                    "atomic_change_id": r.atomic_change_id,
                    "recommendation_status": r.owner_proposal.get("recommendation_status"),
                    "recommended_owner": r.owner_proposal.get("recommended_owner"),
                    "shadow_decision": r.shadow_decision,
                }
                for r in acu_results
            ],
        },
    }
