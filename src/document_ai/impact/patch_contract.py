# -*- coding: utf-8 -*-
"""PR-9: Patch Contract — stable interface between B6 planning and future generation.

Shadow / observational only in PR-9:
- Does NOT generate prose
- Does NOT mutate DOCX
- Does NOT change owner selection, B3/B4, or legacy whole-CR generation

One PatchContract ≡ one Atomic Change Unit intent toward an explicit DocumentTarget.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.atomic_change import AtomicChangeUnit
from document_ai.impact.patch_plan import (
    MDSR_FIELDS,
    MDDR_FIELDS,
    PatchPlanItem,
    semantic_intent_struct_from_acu,
)
from document_ai.impact.propagation import PropagationTrace

ContractOperation = Literal[
    "ADD",
    "UPDATE",
    "DELETE",
    "CONSTRAIN",
    "REPLACE",
    "LINK",
    "NO_ACTION",
    "REVIEW_REQUIRED",
]

# Map legacy B6 / free-form ops → contract ops (closed set).
_OP_NORMALIZE: dict[str, ContractOperation] = {
    "ADD": "ADD",
    "UPDATE": "UPDATE",
    "MODIFY": "UPDATE",
    "EXTEND": "UPDATE",
    "DELETE": "DELETE",
    "CONSTRAIN": "CONSTRAIN",
    "REPLACE": "REPLACE",
    "LINK": "LINK",
    "SPLIT": "UPDATE",
    "NO_CHANGE": "NO_ACTION",
    "NO_ACTION": "NO_ACTION",
    "REVIEW": "REVIEW_REQUIRED",
    "NEEDS_REVIEW": "REVIEW_REQUIRED",
    "REVIEW_REQUIRED": "REVIEW_REQUIRED",
    "BLOCKED": "REVIEW_REQUIRED",
}

_ALLOWED_FIELDS = {
    "MDSR": set(MDSR_FIELDS),
    "MDDR": set(MDDR_FIELDS),
}


@dataclass
class DocumentTarget:
    """Explicit document target — generation must not infer this later."""

    document: str
    requirement_id: str | None = None
    field: str = ""
    section: str | None = None
    anchor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_complete(self) -> bool:
        doc = (self.document or "").upper()
        if doc not in ("MDSR", "MDDR"):
            return False
        if not self.requirement_id:
            return False
        if not self.field:
            return False
        if self.field not in _ALLOWED_FIELDS.get(doc, set()):
            return False
        return True


@dataclass
class SemanticIntentContract:
    """Structured semantic intent for future generation consumption."""

    responsibility_type: str = "other"
    actor: str | None = None
    recipient: str | None = None
    action: str | None = None
    object: list[str] = field(default_factory=list)
    condition: str | None = None
    constraint: list[str] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    affected_entity: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_complete(self) -> bool:
        return bool(self.action) or bool(self.responsibility_type and self.responsibility_type != "other")


@dataclass
class PatchContractProvenance:
    atomic_change_id: str
    source_span: str
    evidence_ids: list[str] = field(default_factory=list)
    owner_evidence_ids: list[str] = field(default_factory=list)
    owner_requirement_id: str | None = None
    owner_design_id: str | None = None
    confidence: float = 0.0
    plan_id: str | None = None
    path: str = "shadow_patch_contract"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PatchContract:
    """Intent-only atomic modification contract. No generated prose."""

    contract_id: str
    atomic_change_id: str
    owner_requirement_id: str | None
    owner_design_id: str | None
    semantic_intent: dict[str, Any]
    responsibility_type: str
    patch_operation: ContractOperation | str
    target: dict[str, Any]
    target_section: str | None = None
    target_field: str = ""
    source_span: str = ""
    rationale: str = ""
    confidence: float = 0.0
    provenance: dict[str, Any] = field(default_factory=dict)
    review_required: bool = False
    validation_status: str = "OK"  # OK | REVIEW_REQUIRED | INVALID
    validation_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_patch_operation(raw: str | None) -> ContractOperation:
    key = (raw or "").strip().upper()
    return _OP_NORMALIZE.get(key, "REVIEW_REQUIRED")


def normalize_document_target(
    *,
    document: str | None,
    requirement_id: str | None,
    field: str | None,
    section: str | None = None,
    anchor: str | None = None,
) -> DocumentTarget:
    doc = (document or "").strip().upper()
    fld = (field or "").strip()
    # Normalize common aliases
    aliases = {
        "design_description": "design_body",
        "body": "design_body",
        "desc": "description",
    }
    fld = aliases.get(fld, fld)
    if doc and doc not in ("MDSR", "MDDR"):
        # Keep original casing only if unknown — mark incomplete via empty doc later
        pass
    sec = section
    if not sec and doc == "MDSR" and fld:
        sec = f"MDSR.{fld}"
    elif not sec and doc == "MDDR" and fld:
        sec = f"MDDR.{fld}"
    return DocumentTarget(
        document=doc,
        requirement_id=requirement_id,
        field=fld,
        section=sec,
        anchor=anchor or (f"{requirement_id}:{fld}" if requirement_id and fld else None),
    )


def build_semantic_intent_contract(acu: AtomicChangeUnit) -> SemanticIntentContract:
    raw = semantic_intent_struct_from_acu(acu)
    cond = raw.get("condition")
    if isinstance(cond, list):
        cond = cond[0] if cond else None
    constraints = raw.get("constraint") or []
    if isinstance(constraints, str):
        constraints = [constraints]
    action = raw.get("action")
    if isinstance(action, list):
        action = action[0] if action else None
    return SemanticIntentContract(
        responsibility_type=str(raw.get("responsibility_type") or acu.responsibility_type or "other"),
        actor=raw.get("actor"),
        recipient=raw.get("recipient"),
        action=action,
        object=list(raw.get("object") or []),
        condition=cond if isinstance(cond, str) or cond is None else str(cond),
        constraint=list(constraints),
        output=list(raw.get("output") or []),
        affected_entity=list(raw.get("affected_entity") or []),
    )


def validate_patch_contract(contract: PatchContract) -> PatchContract:
    """Lightweight required-field validation. Missing → REVIEW_REQUIRED."""
    issues: list[str] = []
    op = normalize_patch_operation(str(contract.patch_operation))
    contract.patch_operation = op

    if op == "REVIEW_REQUIRED":
        issues.append("operation_review_required")

    target = contract.target or {}
    dt = DocumentTarget(
        document=str(target.get("document") or ""),
        requirement_id=target.get("requirement_id"),
        field=str(target.get("field") or ""),
        section=target.get("section"),
        anchor=target.get("anchor"),
    )
    if op not in ("NO_ACTION", "REVIEW_REQUIRED") and not dt.is_complete():
        issues.append("incomplete_target")
    if not contract.owner_requirement_id and op not in ("NO_ACTION", "REVIEW_REQUIRED"):
        issues.append("missing_owner_requirement")
    if not contract.owner_design_id and op not in ("NO_ACTION", "REVIEW_REQUIRED"):
        # Design owner optional for MDSR-only, but flag when MDDR target
        if (dt.document or "").upper() == "MDDR":
            issues.append("missing_owner_design")

    intent = contract.semantic_intent or {}
    if not intent.get("action") and not intent.get("responsibility_type"):
        issues.append("incomplete_semantic_intent")
    if not contract.atomic_change_id:
        issues.append("missing_atomic_change_id")
    if not contract.source_span:
        issues.append("missing_source_span")
    if not (contract.provenance or {}).get("evidence_ids") and not (
        contract.provenance or {}
    ).get("owner_evidence_ids"):
        issues.append("missing_provenance_evidence")

    if issues:
        contract.review_required = True
        contract.validation_status = "REVIEW_REQUIRED"
        contract.validation_issues = issues
        if op not in ("NO_ACTION", "REVIEW_REQUIRED"):
            contract.patch_operation = "REVIEW_REQUIRED"
    else:
        contract.validation_status = "OK"
        contract.validation_issues = []
        if op == "REVIEW_REQUIRED":
            contract.review_required = True
    return contract


def build_patch_contract(
    *,
    acu: AtomicChangeUnit,
    plan: PatchPlanItem | None = None,
    owner_trace: PropagationTrace | None = None,
    contract_id: str | None = None,
) -> PatchContract:
    """Build one PatchContract from ACU + optional B6 plan + owner trace.

    No document generation. Intent only.
    """
    intent = build_semantic_intent_contract(acu)
    cid = contract_id or f"PC-{acu.change_id}"

    owner_req = None
    owner_des = None
    owner_eids: list[str] = []
    conf = float(acu.confidence or 0.0)

    if owner_trace is not None:
        owner_req = owner_trace.source_mdsr_req_id
        # design_candidate like "Req.X (MDDR)" → Req.X
        des = (owner_trace.design_candidate or "").split()
        owner_des = des[0] if des else owner_trace.source_mdsr_req_id
        se = owner_trace.structured_evidence or {}
        owner_eids = [
            str(x)
            for x in (se.get("evidence_ids") or se.get("matched_facets") or [])
            if x
        ]
        conf = max(conf, float(owner_trace.confidence or 0.0))

    if plan is not None:
        owner_req = plan.target_id or owner_req
        owner_des = plan.target_id or owner_des
        owner_eids = list(plan.owner_evidence_ids or owner_eids)
        conf = max(conf, 0.5 if plan.planning_status == "PLANNED" else conf)
        op = normalize_patch_operation(str(plan.operation))
        if plan.planning_status in ("NEEDS_REVIEW", "BLOCKED"):
            op = "REVIEW_REQUIRED"
        target = normalize_document_target(
            document=plan.target_document,
            requirement_id=plan.target_id,
            field=plan.target_field,
            section=None,
            anchor=None,
        )
        rationale = plan.justification or plan.review_reason or ""
        plan_id = plan.patch_id
        source_span = plan.source_cr_span or acu.source_span
    else:
        # No plan: REVIEW or NO_ACTION depending on ACU/owner
        if acu.decomposition_status != "EXTRACTED":
            op = "REVIEW_REQUIRED"
        elif owner_trace is None or not owner_trace.allow_mdsr_patch:
            op = "REVIEW_REQUIRED" if owner_trace is None else "NO_ACTION"
        else:
            op = "UPDATE"
        target = normalize_document_target(
            document="MDSR" if owner_req else "",
            requirement_id=owner_req,
            field="criteria" if owner_req else "",
        )
        rationale = "no_patch_plan_provided"
        plan_id = None
        source_span = acu.source_span

    if not owner_trace and not plan:
        op = "REVIEW_REQUIRED"
        rationale = "no_owner_and_no_plan"

    acu_eids = list((acu.provenance or {}).get("evidence_ids") or [])
    prov = PatchContractProvenance(
        atomic_change_id=acu.change_id,
        source_span=source_span,
        evidence_ids=acu_eids,
        owner_evidence_ids=owner_eids,
        owner_requirement_id=owner_req,
        owner_design_id=owner_des,
        confidence=conf,
        plan_id=plan_id,
    )

    contract = PatchContract(
        contract_id=cid,
        atomic_change_id=acu.change_id,
        owner_requirement_id=owner_req,
        owner_design_id=owner_des,
        semantic_intent=intent.to_dict(),
        responsibility_type=intent.responsibility_type,
        patch_operation=op,
        target=target.to_dict(),
        target_section=target.section,
        target_field=target.field,
        source_span=source_span,
        rationale=rationale,
        confidence=conf,
        provenance=prov.to_dict(),
        review_required=(op == "REVIEW_REQUIRED"),
    )
    return validate_patch_contract(contract)


def build_patch_contracts(
    *,
    acus: list[AtomicChangeUnit],
    plans: list[PatchPlanItem] | None = None,
    traces: list[PropagationTrace] | None = None,
) -> list[PatchContract]:
    """Build one contract per ACU (exactly one primary contract each).

    When multiple plans exist for one ACU, emit one contract per plan but
    contract_id stays ACU-scoped with suffix; primary mapping remains 1 ACU → N
    artifact contracts. For the 1:1 requirement, prefer the first PLANNED plan,
    else first plan, else owner-only contract.
    """
    plans = list(plans or [])
    traces = list(traces or [])
    by_acu_plans: dict[str, list[PatchPlanItem]] = {}
    for p in plans:
        by_acu_plans.setdefault(p.atomic_change_id, []).append(p)
    by_req = {t.source_mdsr_req_id: t for t in traces}

    contracts: list[PatchContract] = []
    for acu in acus:
        acu_plans = by_acu_plans.get(acu.change_id) or []
        # Prefer planned non-review plans; else any plan; else none
        planned = [
            p
            for p in acu_plans
            if p.planning_status == "PLANNED" and normalize_patch_operation(p.operation) != "REVIEW_REQUIRED"
        ]
        chosen_plans = planned or acu_plans[:1] or [None]

        # Resolve owner trace: match plan target_id or first patchable trace with overlap
        owner: PropagationTrace | None = None
        if chosen_plans and chosen_plans[0] is not None and chosen_plans[0].target_id:
            owner = by_req.get(str(chosen_plans[0].target_id))
        if owner is None:
            for t in traces:
                if t.allow_mdsr_patch:
                    owner = t
                    break
            if owner is None and traces:
                owner = traces[0]

        if len(chosen_plans) == 1 and chosen_plans[0] is None:
            contracts.append(
                build_patch_contract(acu=acu, plan=None, owner_trace=owner, contract_id=f"PC-{acu.change_id}")
            )
            continue

        for i, plan in enumerate(chosen_plans):
            suffix = "" if i == 0 else f"-{i + 1}"
            if plan is not None and plan.target_id:
                owner = by_req.get(str(plan.target_id)) or owner
            contracts.append(
                build_patch_contract(
                    acu=acu,
                    plan=plan,
                    owner_trace=owner,
                    contract_id=f"PC-{acu.change_id}{suffix}",
                )
            )
    return contracts


def validate_patch_contracts(contracts: list[PatchContract]) -> dict[str, Any]:
    """Aggregate validation report."""
    ok = sum(1 for c in contracts if c.validation_status == "OK")
    review = sum(1 for c in contracts if c.validation_status == "REVIEW_REQUIRED")
    return {
        "stage": "patch_contract_validation",
        "total": len(contracts),
        "ok": ok,
        "review_required": review,
        "entries": [
            {
                "contract_id": c.contract_id,
                "atomic_change_id": c.atomic_change_id,
                "validation_status": c.validation_status,
                "validation_issues": list(c.validation_issues),
                "patch_operation": c.patch_operation,
                "review_required": c.review_required,
            }
            for c in contracts
        ],
        "note": "PR-9 shadow validation only — does not block legacy generation.",
    }


def compare_contracts_to_legacy(
    *,
    contracts: list[PatchContract],
    traces: list[PropagationTrace],
    plans: list[PatchPlanItem] | None = None,
) -> dict[str, Any]:
    """Diff shadow contracts vs legacy whole-CR targets / B6 plans."""
    legacy_targets = []
    for t in traces:
        if not t.allow_mdsr_patch:
            continue
        legacy_targets.append(
            {
                "requirement_id": t.source_mdsr_req_id,
                "mode": "whole_cr_append",
                "documents": ["MDSR", "MDDR"],
            }
        )
    return {
        "stage": "patch_contract_diff",
        "legacy_target_count": len(legacy_targets),
        "contract_count": len(contracts),
        "plan_count": len(plans or []),
        "contracts_ok": sum(1 for c in contracts if c.validation_status == "OK"),
        "contracts_review": sum(1 for c in contracts if c.review_required),
        "legacy_targets": legacy_targets,
        "contract_summaries": [
            {
                "contract_id": c.contract_id,
                "atomic_change_id": c.atomic_change_id,
                "operation": c.patch_operation,
                "target": c.target,
                "owner_requirement_id": c.owner_requirement_id,
                "review_required": c.review_required,
            }
            for c in contracts
        ],
        "note": (
            "Patch Contract is shadow-only in PR-9. "
            "Legacy whole-CR generation remains the actual prose path."
        ),
    }


def patch_contracts_to_trace_payload(
    *,
    contracts: list[PatchContract],
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": "patch_contracts",
        "schema_version": "patch_contract_v1",
        "note": (
            "PR-9 Patch Contract stabilizes B6→generation interface. "
            "No prose; no DOCX mutation."
        ),
        "contract_count": len(contracts),
        "contracts": [c.to_dict() for c in contracts],
        "validation": validation or validate_patch_contracts(contracts),
    }
