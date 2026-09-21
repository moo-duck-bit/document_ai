# -*- coding: utf-8 -*-
"""PR-8: ACU-driven owner selection (actual path).

Activates ONLY Design Discovery → Responsibility Alignment → Propagation Decision
using ACU v2 spans. Generation / DOCX / B3 / B4 remain unchanged.

Fallback: when no usable ACU exists, caller uses legacy CR-level owner selection.
"""

from __future__ import annotations

from typing import Any, Literal

from document_ai.impact.atomic_change import AtomicChangeUnit, decompose_change_request
from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.propagation import (
    AlignmentResult,
    PropagationDecision,
    PropagationDecisionResult,
    PropagationEvidence,
    PropagationTrace,
    align_design_candidate,
    decide_propagation,
    discover_design_candidates,
    proposed_mddr_design_description,
    _decision_to_outcome,
    _extract_b3_prior,
    _extract_b4_prior,
)
from document_ai.impact.semantic_index import RequirementBlock

OwnerSelectionMode = Literal["auto", "acu", "legacy"]

_DECISION_RANK: dict[str, int] = {
    "PATCH_EXISTING": 50,
    "EXTEND_EXISTING": 40,
    "NEW_DESIGN_CANDIDATE": 30,
    "NEEDS_REVIEW": 20,
    "SKIP": 10,
}


def usable_acus_for_owner_selection(units: list[AtomicChangeUnit]) -> list[AtomicChangeUnit]:
    """EXTRACTED ACUs drive owner selection; others are recorded as needs_review."""
    return [u for u in units if u.decomposition_status == "EXTRACTED" and u.source_span]


def resolve_owner_selection_mode(
    mode: OwnerSelectionMode,
    units: list[AtomicChangeUnit],
) -> tuple[str, str]:
    """Return (effective_mode, reason). effective is 'acu' or 'legacy'."""
    usable = usable_acus_for_owner_selection(units)
    if mode == "legacy":
        return "legacy", "explicit_legacy"
    if mode == "acu":
        if not usable:
            return "legacy", "acu_requested_but_empty_fallback"
        return "acu", "explicit_acu"
    # auto
    if usable:
        return "acu", "auto_acu_v2"
    return "legacy", "auto_fallback_empty_acu"


def _aggregate_decision(
    per_acu: list[dict[str, Any]],
) -> tuple[PropagationDecision, float, str, list[str]]:
    """Pick strongest ACU decision for one requirement."""
    if not per_acu:
        return "NEEDS_REVIEW", 0.0, "no_acu_evaluations", []
    best = max(
        per_acu,
        key=lambda r: (
            _DECISION_RANK.get(str(r.get("propagation_decision") or "SKIP"), 0),
            float(r.get("confidence") or 0.0),
        ),
    )
    prop = str(best.get("propagation_decision") or "NEEDS_REVIEW")
    if prop not in _DECISION_RANK:
        prop = "NEEDS_REVIEW"
    acu_ids = [str(r.get("atomic_change_id") or "") for r in per_acu if r.get("atomic_change_id")]
    reason = (
        f"ACU owner selection: best={best.get('atomic_change_id')} "
        f"decision={prop} | {best.get('reason') or ''}"
    )
    return prop, float(best.get("confidence") or 0.0), reason, acu_ids  # type: ignore[return-value]


def select_owners_via_acu(
    *,
    cr_text: str,
    acus: list[AtomicChangeUnit],
    consistency: list[ConsistencyDecision],
    blocks: list[RequirementBlock],
    b3_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run per-ACU discovery → alignment → decision; aggregate to req-level traces.

    Alignment/decision query text is ACU.source_span (never whole CR).
    Generation snippets still use whole CR when a patch is allowed (unchanged apply path).
    """
    by_key = {(b.req_id, b.document_type): b for b in blocks}
    b3_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for d in b3_decisions or []:
        rid = d.get("candidate_id") or d.get("candidate")
        doc = d.get("document")
        if rid and doc:
            b3_by_key[(rid, doc)] = d

    mdsr_decisions = [d for d in consistency if d.document == "MDSR"]
    mapping: list[dict[str, Any]] = []
    stage_candidates: list[dict[str, Any]] = []
    stage_alignments: list[dict[str, Any]] = []
    stage_decisions: list[dict[str, Any]] = []
    per_req: dict[str, list[dict[str, Any]]] = {d.req_id: [] for d in mdsr_decisions}

    for acu in acus:
        for decision in mdsr_decisions:
            mdsr = by_key.get((decision.req_id, "MDSR"))
            b3_prior = _extract_b3_prior(b3_by_key.get((decision.req_id, "MDSR")), decision)
            b4_prior = _extract_b4_prior(decision)
            candidates = discover_design_candidates(decision.req_id, by_key)
            stage_candidates.append(
                {
                    "atomic_change_id": acu.change_id,
                    "requirement_id": decision.req_id,
                    "candidate_count": len(candidates),
                    "candidates": [c.to_dict() for c in candidates],
                    "path": "actual_acu",
                    "query_span": acu.source_span,
                }
            )
            mddr = candidates[0].block if candidates else None

            if not mdsr:
                row = {
                    "atomic_change_id": acu.change_id,
                    "requirement_id": decision.req_id,
                    "design_id": None,
                    "propagation_decision": "NEEDS_REVIEW",
                    "confidence": 0.0,
                    "reason": "MDSR block missing",
                    "acu_status": acu.decomposition_status,
                    "owner_found": False,
                }
                mapping.append(row)
                per_req.setdefault(decision.req_id, []).append(row)
                continue

            if acu.decomposition_status != "EXTRACTED":
                row = {
                    "atomic_change_id": acu.change_id,
                    "requirement_id": decision.req_id,
                    "design_id": mddr.req_id if mddr else None,
                    "propagation_decision": "NEEDS_REVIEW",
                    "confidence": 0.0,
                    "reason": f"ACU status={acu.decomposition_status}",
                    "acu_status": acu.decomposition_status,
                    "owner_found": False,
                }
                mapping.append(row)
                per_req.setdefault(decision.req_id, []).append(row)
                continue

            # Owner-selection query = ACU span (not whole CR)
            align: AlignmentResult = align_design_candidate(
                acu.source_span,
                mdsr,
                mddr,
                decision=decision,
                b3_prior=b3_prior,
            )
            decided: PropagationDecisionResult = decide_propagation(
                requirement_id=decision.req_id,
                design_id=(mddr.req_id if mddr else ""),
                alignment=align,
                decision=decision,
            )
            stage_alignments.append(
                {
                    **align.to_dict(),
                    "atomic_change_id": acu.change_id,
                    "query_span": acu.source_span,
                    "path": "actual_acu",
                }
            )
            stage_decisions.append(
                {
                    **decided.to_dict(),
                    "atomic_change_id": acu.change_id,
                    "query_span": acu.source_span,
                    "path": "actual_acu",
                }
            )
            owner_found = decided.decision in ("PATCH_EXISTING", "EXTEND_EXISTING")
            row = {
                "atomic_change_id": acu.change_id,
                "requirement_id": decision.req_id,
                "design_id": mddr.req_id if mddr else None,
                "propagation_decision": decided.decision,
                "confidence": decided.confidence,
                "reason": decided.reason,
                "acu_status": acu.decomposition_status,
                "owner_found": owner_found,
                "source_span": acu.source_span,
                "alignment_status": align.alignment,
            }
            mapping.append(row)
            per_req.setdefault(decision.req_id, []).append(row)

    traces: list[PropagationTrace] = []
    owners_found = 0
    needs_review = 0

    for decision in mdsr_decisions:
        mdsr = by_key.get((decision.req_id, "MDSR"))
        b3_prior = _extract_b3_prior(b3_by_key.get((decision.req_id, "MDSR")), decision)
        b4_prior = _extract_b4_prior(decision)
        candidates = discover_design_candidates(decision.req_id, by_key)
        mddr = candidates[0].block if candidates else None
        rows = per_req.get(decision.req_id) or []
        # Prefer EXTRACTED ACU rows for aggregation
        extracted_rows = [r for r in rows if r.get("acu_status") == "EXTRACTED"]
        prop, conf, reason, acu_ids = _aggregate_decision(
            extracted_rows if extracted_rows else rows
        )

        if not mdsr:
            traces.append(
                PropagationTrace(
                    source_mdsr_req_id=decision.req_id,
                    mdsr_consistency_status=decision.status,
                    impacted_mddr_candidate=f"MDDR {decision.req_id}",
                    propagation_reason="MDSR block missing from index",
                    outcome="NEEDS_REVIEW",
                    evidence=["missing_mdsr_block"],
                    requirement=decision.req_id,
                    design_candidate="",
                    propagation_decision="NEEDS_REVIEW",
                    structured_evidence={
                        "owner_selection": "acu_v2",
                        "atomic_change_ids": acu_ids,
                        "missing_information": ["mdsr_block"],
                    },
                    allow_mdsr_patch=False,
                    b3_prior=b3_prior,
                    b4_prior=b4_prior,
                )
            )
            needs_review += 1
            continue

        before = (mddr.body_text or "")[:240] if mddr else ""
        design_label = (
            f"{mddr.req_id} ({mddr.document_type})" if mddr else f"MDDR {decision.req_id} (missing)"
        )
        aligned = prop in ("PATCH_EXISTING", "EXTEND_EXISTING")
        # Generation unchanged: whole-CR append when owner is selected
        after = ""
        no_delta = False
        if aligned and mddr:
            design_text = proposed_mddr_design_description(mddr, cr_text)
            if design_text is None:
                no_delta = True
                reason = (
                    f"{reason} | No additional MDDR design delta from CR append "
                    "(already covered or empty CR)"
                )
            else:
                after = design_text[:240]

        if aligned and after:
            outcome = "PATCHED"
            allow_docs = True
            owners_found += 1
        elif prop == "SKIP":
            outcome = "SKIPPED_WITH_REASON"
            allow_docs = False
        elif aligned and no_delta:
            outcome = "SKIPPED_WITH_REASON"
            allow_docs = False
        else:
            outcome = _decision_to_outcome(prop)
            allow_docs = False
            if prop == "NEEDS_REVIEW" or outcome == "NEEDS_REVIEW":
                needs_review += 1

        # Pick best row's alignment evidence for structured_evidence
        best_row = None
        if extracted_rows:
            best_row = max(
                extracted_rows,
                key=lambda r: (
                    _DECISION_RANK.get(str(r.get("propagation_decision") or "SKIP"), 0),
                    float(r.get("confidence") or 0.0),
                ),
            )

        pev = PropagationEvidence()
        traces.append(
            PropagationTrace(
                source_mdsr_req_id=decision.req_id,
                mdsr_consistency_status=decision.status,
                impacted_mddr_candidate=design_label,
                propagation_reason=reason,
                outcome=outcome,
                evidence=[
                    reason,
                    f"propagation_decision={prop}",
                    f"owner_selection=acu_v2",
                    f"atomic_change_ids={acu_ids}",
                ],
                design_responsibility_aligned=aligned and not no_delta,
                before_snippet=before,
                after_snippet=after,
                requirement=decision.req_id,
                design_candidate=design_label if mddr else "",
                propagation_decision=prop,
                structured_evidence={
                    **pev.to_dict(),
                    "owner_selection": "acu_v2",
                    "atomic_change_ids": acu_ids,
                    "best_acu": (best_row or {}).get("atomic_change_id"),
                    "query_mode": "acu_source_span",
                },
                confidence=conf,
                allow_mdsr_patch=allow_docs,
                b3_prior=b3_prior,
                b4_prior=b4_prior,
            )
        )

    summary = {
        "acu_count": len(acus),
        "usable_acu_count": len(usable_acus_for_owner_selection(acus)),
        "owners_found": owners_found,
        "needs_review": needs_review,
        "requirement_count": len(mdsr_decisions),
        "mapping_rows": len(mapping),
        "mode": "acu",
    }
    return {
        "traces": traces,
        "mapping": mapping,
        "summary": summary,
        "stage_candidates": stage_candidates,
        "stage_alignments": stage_alignments,
        "stage_decisions": stage_decisions,
    }


def build_owner_activation_diff(
    *,
    legacy_traces: list[PropagationTrace],
    acu_traces: list[PropagationTrace],
    legacy_summary: dict[str, Any] | None = None,
    acu_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare legacy CR-level owners vs ACU-activated owners."""
    leg = {
        t.source_mdsr_req_id: {
            "propagation_decision": t.propagation_decision,
            "allow_mdsr_patch": t.allow_mdsr_patch,
            "outcome": t.outcome,
        }
        for t in legacy_traces
    }
    acu = {
        t.source_mdsr_req_id: {
            "propagation_decision": t.propagation_decision,
            "allow_mdsr_patch": t.allow_mdsr_patch,
            "outcome": t.outcome,
        }
        for t in acu_traces
    }
    all_ids = sorted(set(leg) | set(acu))
    changes: list[dict[str, Any]] = []
    for rid in all_ids:
        a = leg.get(rid) or {}
        b = acu.get(rid) or {}
        if a != b:
            changes.append({"requirement_id": rid, "legacy": a, "acu": b})
    return {
        "stage": "owner_activation_diff",
        "legacy_targets": sum(1 for t in legacy_traces if t.allow_mdsr_patch),
        "acu_targets": sum(1 for t in acu_traces if t.allow_mdsr_patch),
        "decision_changes": changes,
        "legacy_summary": legacy_summary or {},
        "acu_summary": acu_summary or {},
        "note": "Generation/DOCX path unchanged; diff is owner-selection only.",
    }


def build_owner_activation_summary(
    *,
    effective_mode: str,
    mode_reason: str,
    acus: list[AtomicChangeUnit],
    legacy_traces: list[PropagationTrace],
    active_traces: list[PropagationTrace],
    acu_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    acu_sum = (acu_payload or {}).get("summary") or {}
    return {
        "stage": "owner_activation_summary",
        "effective_mode": effective_mode,
        "mode_reason": mode_reason,
        "acu_count": len(acus),
        "owners_found": int(acu_sum.get("owners_found") or sum(1 for t in active_traces if t.allow_mdsr_patch)),
        "needs_review": int(
            acu_sum.get("needs_review")
            or sum(1 for t in active_traces if t.propagation_decision == "NEEDS_REVIEW")
        ),
        "legacy_targets": sum(1 for t in legacy_traces if t.allow_mdsr_patch),
        "acu_targets": sum(1 for t in active_traces if t.allow_mdsr_patch),
        "generation_unchanged": True,
        "docx_unchanged_contract": True,
        "b3_b4_unchanged": True,
        "note": (
            "PR-8 activates ACU v2 for owner selection only. "
            "Patch text still uses whole-CR append helpers."
        ),
    }
