# -*- coding: utf-8 -*-
"""Conservative no-impact / document decision policy for generic packs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.domain_packs.generic.target_existence import TargetExistenceDecision

DecisionStatus = Literal["IMPACTED", "REVIEW_REQUIRED", "UNRELATED", "INVALID"]

SUBSTANTIVE_EVIDENCE = frozenset(
    {
        "EXACT_SECTION_MATCH",
        "EXACT_HEADING_MATCH",
        "TEMPLATE_FIELD_MATCH",
        "STRUCTURAL_BLOCK_MATCH",
        "TABLE_HEADER_MATCH",
        "LIST_CONTEXT_MATCH",
        "SEMANTIC_SECTION_MATCH",
    }
)

NON_SUBSTANTIVE = frozenset(
    {
        "TEMPLATE_COMPATIBILITY",
        "DOCUMENT_PRESENCE",
        "DOCUMENT_LEVEL_CONCEPT_MATCH",
        "MISSING_TARGET_REQUEST",
        "NO_IMPACT_EVIDENCE",
    }
)


@dataclass
class ImpactEvidence:
    evidence_type: str
    evidence_value: str = ""
    node_id: str | None = None
    confidence: float = 0.0
    source_stage: str = ""
    supports_impacted: bool = False
    supports_review: bool = False
    reason_codes: list[str] = field(default_factory=list)

    @property
    def is_substantive(self) -> bool:
        return self.evidence_type in SUBSTANTIVE_EVIDENCE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NoImpactDecision:
    document_id: str
    status: DecisionStatus
    reason_codes: list[str] = field(default_factory=list)
    substantive_evidence_count: int = 0
    human_review_required: bool = False
    target_status: str | None = None
    top_evidence: list[dict[str, Any]] = field(default_factory=list)
    virtual_targets: list[dict[str, Any]] = field(default_factory=list)
    validation: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_decision(
    status: DecisionStatus,
    evidences: list[ImpactEvidence],
    target: TargetExistenceDecision | None,
) -> dict[str, bool]:
    substantive = [e for e in evidences if e.is_substantive]
    presence_only = evidences and all(e.evidence_type in NON_SUBSTANTIVE for e in evidences)
    tmpl_only = evidences and all(
        e.evidence_type in {"TEMPLATE_COMPATIBILITY", "DOCUMENT_LEVEL_CONCEPT_MATCH"} for e in evidences
    )
    checks = {
        "no_presence_only_impacted": not (status == "IMPACTED" and presence_only),
        "no_template_compatibility_only_impacted": not (status == "IMPACTED" and tmpl_only),
        "impacted_requires_specific_node_or_addable_target": (
            status != "IMPACTED"
            or any(e.node_id for e in substantive)
            or (target is not None and target.target_status == "MISSING_ADDABLE")
        ),
        "missing_unsupported_not_impacted": not (
            status == "IMPACTED"
            and target is not None
            and target.target_status in {"MISSING_UNSUPPORTED", "UNRELATED"}
        ),
        "unrelated_request_not_reviewed_without_evidence": not (
            status == "REVIEW_REQUIRED"
            and not substantive
            and (target is None or target.target_status in {"UNRELATED", "MISSING_UNSUPPORTED"})
            and not (target and target.target_status == "MISSING_ADDABLE")
        ),
    }
    return checks


def decide_no_impact(
    *,
    document_id: str,
    evidences: list[ImpactEvidence],
    target: TargetExistenceDecision | None = None,
) -> NoImpactDecision:
    """Map evidences + target existence → conservative document decision."""
    substantive = [e for e in evidences if e.is_substantive]
    reasons: list[str] = []
    virtuals: list[dict[str, Any]] = []

    if target and target.target_status == "INVALID":
        status: DecisionStatus = "INVALID"
        reasons.append("invalid_target")
    elif target and target.target_status == "UNRELATED" and not substantive:
        status = "UNRELATED"
        reasons.extend(["no_substantive_evidence", "unrelated_target"])
    elif target and target.target_status == "MISSING_UNSUPPORTED" and not substantive:
        # Template-only weak hit without document grounding → UNRELATED (safe)
        status = "UNRELATED"
        reasons.extend(["missing_unsupported_not_impacted", "template_only_no_document_grounding"])
        if target.virtual_target:
            virtuals.append(
                {
                    "virtual_target": True,
                    "target_exists": False,
                    "template_node_id": target.template_node_id,
                    "allowed_operation": "ADD",
                    "writer_supported": False,
                    "human_review_required": True,
                }
            )
    elif target and target.target_status == "MISSING_ADDABLE":
        # MVP writer cannot ADD sections → keep document UNRELATED (safe).
        # Virtual target is recorded for assisted review without elevating impact.
        status = "UNRELATED"
        reasons.extend(
            [
                "missing_addable_target",
                "writer_unsupported_blocked",
                "missing_unsupported_not_impacted",
                "virtual_target_not_document_review",
            ]
        )
        virtuals.append(
            {
                "virtual_target": True,
                "target_exists": False,
                "template_node_id": target.template_node_id,
                "allowed_operation": "ADD",
                "writer_supported": False,
                "human_review_required": True,
            }
        )
    elif any(e.supports_impacted and e.is_substantive and e.node_id for e in substantive):
        status = "IMPACTED"
        reasons.append("substantive_node_evidence")
    elif substantive and (
        any(e.supports_review for e in substantive)
        or (target and target.target_status in {"EXISTS_EXACT", "EXISTS_SEMANTIC", "AMBIGUOUS"})
    ):
        status = "REVIEW_REQUIRED"
        reasons.append("substantive_review_evidence")
        if target and target.target_status == "EXISTS_SEMANTIC":
            reasons.append("semantic_only_no_patch")
    elif not substantive:
        status = "UNRELATED"
        reasons.extend(["no_substantive_evidence", "presence_or_template_insufficient"])
    else:
        status = "REVIEW_REQUIRED"
        reasons.append("default_review")

    # Never IMPACTED without substantive node attribution
    if status == "IMPACTED" and not any(e.node_id for e in substantive):
        status = "REVIEW_REQUIRED"
        reasons.append("impacted_requires_specific_node")

    validation = _validate_decision(status, evidences, target)
    # If validation fails on review-without-evidence, force UNRELATED
    if not validation.get("unrelated_request_not_reviewed_without_evidence", True):
        if status == "REVIEW_REQUIRED" and not substantive:
            status = "UNRELATED"
            reasons.append("forced_unrelated_no_evidence")
            validation = _validate_decision(status, evidences, target)

    return NoImpactDecision(
        document_id=document_id,
        status=status,
        reason_codes=list(dict.fromkeys(reasons))[:16],
        substantive_evidence_count=len(substantive),
        human_review_required=status in {"REVIEW_REQUIRED", "INVALID", "IMPACTED"},
        target_status=target.target_status if target else None,
        top_evidence=[e.to_dict() for e in (substantive or evidences)[:5]],
        virtual_targets=virtuals,
        validation=validation,
        metadata={"policy": "generic_no_impact_v1"},
    )
