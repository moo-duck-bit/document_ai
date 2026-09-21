# -*- coding: utf-8 -*-
"""PR-5 / B6: Semantic Patch Planning (shadow only).

Answers: which ACU meaning should land on which document/id/field
with which operation — without generating final prose or mutating DOCX.

Actual whole-CR patch path remains unchanged in PR-5.
B6 output ≠ actual document mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.atomic_change import AtomicChangeUnit
from document_ai.impact.propagation import PropagationTrace

PatchOperation = Literal["ADD", "MODIFY", "EXTEND", "SPLIT", "NO_CHANGE", "REVIEW"]
PlanningStatus = Literal["PLANNED", "NEEDS_REVIEW", "BLOCKED"]

# Extensible target fields grounded in existing parsers (FieldSnapshot + MDDR body).
MDSR_FIELDS = ("title", "description", "purpose", "criteria")
MDDR_FIELDS = ("title", "design_body", "design_condition")


@dataclass
class PatchPlanItem:
    patch_id: str
    atomic_change_id: str
    target_document: str
    target_id: str | None
    target_field: str
    operation: PatchOperation | str
    semantic_intent: str
    source_cr_span: str
    justification: str
    owner_evidence_ids: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    planning_status: PlanningStatus | str = "PLANNED"
    review_reason: str | None = None
    plan_group_id: str | None = None
    conflict_status: str = "none"  # none | compatible | potentially_duplicate | conflict
    merge_candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_ids"] = list(self.owner_evidence_ids)
        return d


def semantic_intent_from_acu(acu: AtomicChangeUnit) -> str:
    """ACU-scoped semantic intent from ACU_DIRECT facets — never whole CR."""
    def _vals(role: str) -> list[str]:
        # Prefer ACU_DIRECT; allow discourse-inherited actor (CR_CONTEXT) for intent readability
        direct = [
            f["value"]
            for f in (acu.facet_origins or [])
            if f.get("role") == role
            and f.get("origin") == "ACU_DIRECT"
            and f.get("value")
        ]
        if direct:
            return list(dict.fromkeys(direct))
        if role == "actor":
            inherited = [
                f["value"]
                for f in (acu.facet_origins or [])
                if f.get("role") == "actor"
                and f.get("origin") == "CR_CONTEXT"
                and f.get("value")
            ]
            if inherited:
                return list(dict.fromkeys(inherited))
        return list(getattr(acu, role, None) or [])

    actor = _vals("actor")
    action = _vals("action")
    obj = _vals("object")
    recipient = _vals("recipient")
    affected = _vals("affected_entity")
    condition = _vals("condition")
    constraint = _vals("constraint")
    output = _vals("output")

    chunks: list[str] = []
    if condition:
        chunks.append(f"조건[{', '.join(condition)}]")
    if actor:
        chunks.append(f"행위자[{', '.join(actor)}]")
    if action:
        chunks.append(f"행위[{', '.join(action)}]")
    if affected:
        chunks.append(f"영향대상[{', '.join(affected)}]")
    if obj:
        chunks.append(f"대상[{', '.join(obj)}]")
    if recipient:
        chunks.append(f"수신자[{', '.join(recipient)}]")
    if constraint:
        chunks.append(f"제약[{', '.join(constraint)}]")
    if output:
        chunks.append(f"산출[{', '.join(output)}]")
    if chunks:
        return (
            f"{acu.responsibility_type}: "
            + " / ".join(chunks)
            + " 책임을 반영"
        )
    return f"{acu.responsibility_type}: {acu.source_span}"


def semantic_intent_struct_from_acu(acu: AtomicChangeUnit) -> dict[str, Any]:
    """Structured intent preferring ACU_DIRECT facets."""
    def _vals(role: str) -> list[str]:
        direct = [
            f["value"]
            for f in (acu.facet_origins or [])
            if f.get("role") == role and f.get("origin") == "ACU_DIRECT" and f.get("value")
        ]
        return list(dict.fromkeys(direct or list(getattr(acu, role, None) or [])))

    return {
        "responsibility_type": acu.responsibility_type,
        "actor": (_vals("actor") or [None])[0],
        "action": (_vals("action") or [None])[0],
        "affected_entity": _vals("affected_entity"),
        "object": _vals("object"),
        "condition": (_vals("condition") or [None])[0],
        "recipient": (_vals("recipient") or [None])[0],
        "output": _vals("output"),
        "source_span": acu.source_span,
        "origin": "ACU_DIRECT",
    }


def select_target_fields(
    *,
    document: str,
    responsibility_type: str,
    has_condition: bool,
) -> list[str]:
    """Domain-independent field selection; uncertain → empty (caller uses REVIEW)."""
    doc = (document or "").upper()
    rtype = responsibility_type or "other"

    if doc == "MDSR":
        # Behavior / capability / rules → criteria preferred, else description
        if rtype in ("classify", "display", "update", "enforce", "audit", "other"):
            fields = ["criteria"]
            if rtype in ("other", "update") and has_condition:
                fields = ["criteria"]
            return fields
        return ["description"]

    if doc == "MDDR":
        if has_condition:
            return ["design_condition", "design_body"]
        return ["design_body"]

    return []


def _operation_for_b5c(decision: str) -> PatchOperation:
    if decision == "PATCH_EXISTING":
        return "MODIFY"
    if decision == "EXTEND_EXISTING":
        return "EXTEND"
    if decision in ("NEW_DESIGN_CANDIDATE", "NEEDS_REVIEW"):
        return "REVIEW"
    if decision == "SKIP":
        return "NO_CHANGE"
    return "REVIEW"


def _acu_owner_match(
    acu: AtomicChangeUnit,
    trace: PropagationTrace,
) -> tuple[bool, list[str], str]:
    """Conservative responsibility overlap check — do not clone owner to all ACUs.

    Returns (matched, evidence_ids, reason).
    """
    if acu.decomposition_status in ("AMBIGUOUS", "NEEDS_REVIEW"):
        return False, [], f"acu_status={acu.decomposition_status}"

    se = trace.structured_evidence or {}
    matched_resp = [str(x).lower() for x in (se.get("matched_responsibilities") or [])]
    facets = [str(x).lower() for x in (se.get("matched_facets") or [])]
    acu_tokens = {
        t.lower()
        for t in (acu.action + acu.object + acu.actor + acu.output)
        if t
    }
    # Provenance evidence ids from ACU
    acu_eids = list((acu.provenance or {}).get("evidence_ids") or [])

    if not acu_tokens:
        return False, acu_eids, "acu_has_no_action_object_tokens"

    overlap = []
    for tok in acu_tokens:
        if any(tok in r or r in tok for r in matched_resp):
            overlap.append(tok)
        elif tok in facets or any(tok in f for f in facets):
            overlap.append(tok)

    # Also accept action∩responsibility_type alignment with non-SKIP patchable decisions
    if not overlap and acu.action and trace.propagation_decision in (
        "PATCH_EXISTING",
        "EXTEND_EXISTING",
    ):
        # Weak: shared action marker string in design/requirement snippets
        blob = " ".join(
            [
                " ".join(matched_resp),
                " ".join(facets),
                (trace.before_snippet or ""),
                (trace.after_snippet or ""),
                (trace.propagation_reason or ""),
            ]
        ).lower()
        overlap = [a for a in acu.action if a.lower() in blob]

    if overlap:
        return True, acu_eids, f"overlap={sorted(set(overlap))}"
    return False, acu_eids, "no_responsibility_overlap_with_owner_evidence"


def _legacy_targets_from_traces(traces: list[PropagationTrace]) -> list[dict[str, Any]]:
    """Describe actual whole-CR append targets (parity observation)."""
    out: list[dict[str, Any]] = []
    for tr in traces:
        if not tr.allow_mdsr_patch:
            continue
        rid = tr.source_mdsr_req_id
        out.append(
            {
                "legacy_mode": "whole_cr_append",
                "target_document": "MDSR",
                "target_id": rid,
                "target_field": "description",
                "operation": "EXTEND",
                "note": "proposed_mdsr_description appends whole CR",
            }
        )
        if tr.propagation_decision in ("PATCH_EXISTING", "EXTEND_EXISTING"):
            out.append(
                {
                    "legacy_mode": "whole_cr_append",
                    "target_document": "MDDR",
                    "target_id": rid,
                    "target_field": "design_body",
                    "operation": "EXTEND",
                    "note": "proposed_mddr_design_description appends whole CR",
                }
            )
    return out


def _annotate_conflicts(plans: list[PatchPlanItem]) -> None:
    """Group plans sharing the same target; mark duplicate/conflict metadata (no auto-merge)."""
    groups: dict[tuple[str, str | None, str], list[PatchPlanItem]] = {}
    for p in plans:
        if p.planning_status == "BLOCKED" or p.operation == "NO_CHANGE":
            continue
        key = (p.target_document, p.target_id, p.target_field)
        groups.setdefault(key, []).append(p)

    for idx, (key, items) in enumerate(sorted(groups.items(), key=lambda x: str(x[0]))):
        if len(items) < 2:
            continue
        gid = f"PGROUP-{idx + 1:03d}"
        actions = set()
        for it in items:
            actions.add(it.operation)
            it.plan_group_id = gid
            it.merge_candidate = True
        # Heuristic conflict status
        intents = [it.semantic_intent for it in items]
        if "REVIEW" in actions and any(a != "REVIEW" for a in actions):
            status = "conflict"
        elif len(set(intents)) < len(intents):
            status = "potentially_duplicate"
        else:
            status = "compatible"
        for it in items:
            it.conflict_status = status


def build_shadow_patch_plans(
    *,
    cr_text: str,
    acus: list[AtomicChangeUnit],
    traces: list[PropagationTrace],
) -> list[PatchPlanItem]:
    """Build B6 shadow patch plans from ACUs + actual B5c traces.

    Does not mutate documents. Does not re-run B3/B4/B5.
    """
    plans: list[PatchPlanItem] = []
    seq = 0

    def _next_id() -> str:
        nonlocal seq
        seq += 1
        return f"PATCH-{seq:03d}"

    # Index patchable traces by req id
    by_req = {t.source_mdsr_req_id: t for t in traces}

    for acu in acus:
        # Ambiguous / needs-review ACU → no auto plan
        if acu.decomposition_status in ("AMBIGUOUS", "NEEDS_REVIEW"):
            plans.append(
                PatchPlanItem(
                    patch_id=_next_id(),
                    atomic_change_id=acu.change_id,
                    target_document="",
                    target_id=None,
                    target_field="",
                    operation="REVIEW",
                    semantic_intent=semantic_intent_from_acu(acu),
                    source_cr_span=acu.source_span,
                    justification="ACU decomposition not safe for auto planning",
                    owner_evidence_ids=list(
                        (acu.provenance or {}).get("evidence_ids") or []
                    ),
                    provenance={
                        "atomic_change_id": acu.change_id,
                        "acu_provenance": dict(acu.provenance or {}),
                        "path": "shadow_only",
                        "note": "B6 shadow planning; actual whole-CR patch unchanged",
                    },
                    planning_status="NEEDS_REVIEW",
                    review_reason=f"acu_decomposition_status={acu.decomposition_status}",
                )
            )
            continue

        matched_any = False
        for tr in traces:
            decision = str(tr.propagation_decision or "")

            if decision == "SKIP":
                continue

            if decision == "NEEDS_REVIEW":
                # Do not auto-plan against REVIEW owners
                continue

            if decision == "NEW_DESIGN_CANDIDATE":
                # Proposal / review only — no existing target auto patch
                matched_any = True
                plans.append(
                    PatchPlanItem(
                        patch_id=_next_id(),
                        atomic_change_id=acu.change_id,
                        target_document="MDDR",
                        target_id=None,
                        target_field="",
                        operation="REVIEW",
                        semantic_intent=semantic_intent_from_acu(acu),
                        source_cr_span=acu.source_span,
                        justification=(
                            "B5c NEW_DESIGN_CANDIDATE — no existing design field auto-plan"
                        ),
                        owner_evidence_ids=list(
                            (acu.provenance or {}).get("evidence_ids") or []
                        ),
                        provenance={
                            "atomic_change_id": acu.change_id,
                            "b5c_decision": decision,
                            "owner_req_id": tr.source_mdsr_req_id,
                            "acu_provenance": dict(acu.provenance or {}),
                            "path": "shadow_only",
                        },
                        planning_status="NEEDS_REVIEW",
                        review_reason="new_design_candidate_no_auto_target",
                    )
                )
                continue

            if decision not in ("PATCH_EXISTING", "EXTEND_EXISTING"):
                continue

            ok, eids, reason = _acu_owner_match(acu, tr)
            if not ok:
                continue

            matched_any = True
            op = _operation_for_b5c(decision)
            # Prefer ADD when PATCH and criteria empty-ish not known — use MODIFY/EXTEND from B5c
            if decision == "PATCH_EXISTING":
                op = "ADD" if acu.responsibility_type in ("classify", "display", "other") else "MODIFY"

            # MDSR field plans
            mdsr_fields = select_target_fields(
                document="MDSR",
                responsibility_type=acu.responsibility_type,
                has_condition=bool(acu.condition),
            )
            for fld in mdsr_fields:
                if fld not in MDSR_FIELDS:
                    continue
                plans.append(
                    PatchPlanItem(
                        patch_id=_next_id(),
                        atomic_change_id=acu.change_id,
                        target_document="MDSR",
                        target_id=tr.source_mdsr_req_id,
                        target_field=fld,
                        operation=op,
                        semantic_intent=semantic_intent_from_acu(acu),
                        source_cr_span=acu.source_span,
                        justification=(
                            f"B5c={decision}; ACU↔owner match ({reason}); "
                            f"field rule responsibility_type={acu.responsibility_type}"
                        ),
                        owner_evidence_ids=eids,
                        provenance={
                            "atomic_change_id": acu.change_id,
                            "b5c_decision": decision,
                            "owner_req_id": tr.source_mdsr_req_id,
                            "match_reason": reason,
                            "acu_provenance": dict(acu.provenance or {}),
                            "path": "shadow_only",
                        },
                        planning_status="PLANNED",
                        review_reason=None,
                    )
                )

            # MDDR companion plans when design present / patchable
            if tr.design_responsibility_aligned or tr.allow_mdsr_patch:
                mddr_fields = select_target_fields(
                    document="MDDR",
                    responsibility_type=acu.responsibility_type,
                    has_condition=bool(acu.condition),
                )
                for fld in mddr_fields:
                    if fld not in MDDR_FIELDS:
                        continue
                    plans.append(
                        PatchPlanItem(
                            patch_id=_next_id(),
                            atomic_change_id=acu.change_id,
                            target_document="MDDR",
                            target_id=tr.source_mdsr_req_id,
                            target_field=fld,
                            operation=op if op != "ADD" else "EXTEND",
                            semantic_intent=semantic_intent_from_acu(acu),
                            source_cr_span=acu.source_span,
                            justification=(
                                f"B5c={decision}; multi-artifact plan for same ACU; "
                                f"MDDR field={fld}"
                            ),
                            owner_evidence_ids=eids,
                            provenance={
                                "atomic_change_id": acu.change_id,
                                "b5c_decision": decision,
                                "owner_req_id": tr.source_mdsr_req_id,
                                "match_reason": reason,
                                "acu_provenance": dict(acu.provenance or {}),
                                "path": "shadow_only",
                                "multi_artifact": True,
                            },
                            planning_status="PLANNED",
                            review_reason=None,
                        )
                    )

        if not matched_any:
            plans.append(
                PatchPlanItem(
                    patch_id=_next_id(),
                    atomic_change_id=acu.change_id,
                    target_document="",
                    target_id=None,
                    target_field="",
                    operation="REVIEW",
                    semantic_intent=semantic_intent_from_acu(acu),
                    source_cr_span=acu.source_span,
                    justification=(
                        "No ACU↔owner responsibility evidence; "
                        "refusing to clone whole-CR owner to this ACU"
                    ),
                    owner_evidence_ids=list(
                        (acu.provenance or {}).get("evidence_ids") or []
                    ),
                    provenance={
                        "atomic_change_id": acu.change_id,
                        "acu_provenance": dict(acu.provenance or {}),
                        "path": "shadow_only",
                        "candidate_owners_considered": list(by_req.keys()),
                    },
                    planning_status="NEEDS_REVIEW",
                    review_reason="unmatched_acu_owner_mapping",
                )
            )

    # Stable deterministic order
    plans.sort(
        key=lambda p: (
            p.atomic_change_id,
            p.target_document or "",
            p.target_id or "",
            p.target_field or "",
            p.patch_id,
        )
    )
    # Re-number patch ids for deterministic output after sort
    for i, p in enumerate(plans, start=1):
        p.patch_id = f"PATCH-{i:03d}"

    _annotate_conflicts(plans)
    return plans


def compare_legacy_vs_shadow(
    *,
    cr_text: str,
    traces: list[PropagationTrace],
    plans: list[PatchPlanItem],
) -> dict[str, Any]:
    """Compare whole-CR actual append targets vs ACU-scoped shadow plans."""
    legacy = _legacy_targets_from_traces(traces)
    shadow = [
        {
            "patch_id": p.patch_id,
            "atomic_change_id": p.atomic_change_id,
            "target_document": p.target_document,
            "target_id": p.target_id,
            "target_field": p.target_field,
            "operation": p.operation,
            "planning_status": p.planning_status,
            "semantic_intent": p.semantic_intent,
            "source_cr_span": p.source_cr_span,
        }
        for p in plans
        if p.planning_status == "PLANNED"
    ]
    return {
        "note": (
            "Actual path still uses whole-CR append; B6 shadow plans are observational. "
            "B6 output ≠ actual document mutation."
        ),
        "source_cr_len": len(cr_text or ""),
        "legacy_whole_cr_targets": legacy,
        "shadow_acu_scoped_plans": shadow,
        "summary": {
            "legacy_target_count": len(legacy),
            "shadow_planned_count": len(shadow),
            "shadow_review_count": sum(
                1 for p in plans if p.planning_status == "NEEDS_REVIEW"
            ),
        },
    }


def patch_plans_to_trace_payload(
    *,
    cr_text: str,
    acus: list[AtomicChangeUnit],
    plans: list[PatchPlanItem],
) -> dict[str, Any]:
    return {
        "stage": "B6_shadow",
        "source_cr": cr_text,
        "atomic_change_units": [a.to_dict() for a in acus],
        "patch_plans": [p.to_dict() for p in plans],
        "note": (
            "B6 semantic patch planning is shadow-only in PR-5; "
            "actual whole-CR patch path unchanged."
        ),
    }
