# -*- coding: utf-8 -*-
"""EC-SW document-level impact evidence and decision policy."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from document_ai.domain_packs.ec_sw.identifier_parser import (
    ParsedRequirementId,
    parse_requirement_identifiers,
    valid_canonical_requirement_ids,
)

DocumentImpactStatus = Literal["IMPACTED", "REVIEW_REQUIRED", "UNRELATED", "INVALID"]

SUBSTANTIVE_TYPES = frozenset(
    {
        "EXACT_IDENTIFIER_MATCH",
        "NORMALIZED_IDENTIFIER_MATCH",
        "CROSS_DOCUMENT_IDENTIFIER_MATCH",
        "SEMANTIC_SECTION_MATCH",
    }
)


@dataclass
class DocumentImpactEvidence:
    document_id: str
    document_role: str
    evidence_type: str
    evidence_value: str
    source_stage: str
    source_node_id: str | None = None
    confidence: float = 0.0
    independent_group: str = "default"
    reason_codes: list[str] = field(default_factory=list)
    supports_impacted: bool = False
    supports_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_substantive(self) -> bool:
        return self.evidence_type in SUBSTANTIVE_TYPES


def decide_status_from_evidence(
    evidences: list[DocumentImpactEvidence],
    *,
    malformed_only: bool = False,
) -> tuple[DocumentImpactStatus, list[str]]:
    """Apply IMPACTED / REVIEW_REQUIRED / UNRELATED policy."""
    reasons: list[str] = []
    if not evidences:
        return "UNRELATED", ["no_evidence"]

    substantive = [e for e in evidences if e.is_substantive]
    role_only = [e for e in evidences if e.evidence_type in {"ROLE_COMPATIBILITY", "DOCUMENT_PRESENCE"}]
    malformed = [e for e in evidences if e.evidence_type == "MALFORMED_IDENTIFIER"]
    ambiguous = [e for e in evidences if e.evidence_type == "AMBIGUOUS_IDENTIFIER"]
    semantic = [e for e in evidences if e.evidence_type == "SEMANTIC_SECTION_MATCH"]
    exactish = [
        e
        for e in substantive
        if e.evidence_type
        in {
            "EXACT_IDENTIFIER_MATCH",
            "NORMALIZED_IDENTIFIER_MATCH",
            "CROSS_DOCUMENT_IDENTIFIER_MATCH",
        }
    ]

    # Role / presence alone → UNRELATED
    if not substantive and not malformed and not ambiguous:
        if role_only:
            return "UNRELATED", ["role_or_presence_only", "no_role_only_impacted"]
        return "UNRELATED", ["no_substantive_evidence"]

    if malformed_only or (malformed and not substantive and not semantic):
        return "UNRELATED", ["malformed_id_only", "malformed_id_not_exact"]

    if exactish:
        groups = {e.independent_group for e in exactish}
        if any(e.supports_impacted for e in exactish):
            reasons.append("exact_or_normalized_identifier_match")
            # duplicate / multi-node ambiguity → still IMPACTED but review flag elsewhere
            return "IMPACTED", reasons + ["impacted_requires_substantive_evidence"]

    if len({e.independent_group for e in substantive}) >= 2 and all(
        e.supports_impacted or e.supports_review for e in substantive
    ):
        if any(e.supports_impacted for e in substantive):
            return "IMPACTED", ["independent_substantive_evidence"]

    if semantic and not exactish:
        return "REVIEW_REQUIRED", ["semantic_only_review", "no_semantic_only_patch"]

    if ambiguous and not exactish:
        return "REVIEW_REQUIRED", ["ambiguous_identifier"]

    if malformed and semantic:
        return "REVIEW_REQUIRED", ["malformed_plus_semantic"]

    if substantive and all(e.supports_review and not e.supports_impacted for e in substantive):
        return "REVIEW_REQUIRED", ["indirect_or_review_evidence"]

    if role_only and not substantive:
        return "UNRELATED", ["role_or_presence_only"]

    return "UNRELATED", ["default_unrelated"]


def build_evidences_for_uploads(
    *,
    change_request: str,
    uploaded_docs: list[dict[str, Any]],
    patch_candidates: list[dict[str, Any]],
    review_required: list[dict[str, Any]],
    parsed_ids: list[ParsedRequirementId] | None = None,
) -> dict[str, list[DocumentImpactEvidence]]:
    """Build per-document evidence from MDTM candidates + upload roles (no role-only IMPACTED)."""
    parsed = parsed_ids if parsed_ids is not None else parse_requirement_identifiers(change_request)
    valid_ids = {p.canonical_id for p in parsed if p.status in {"VALID_EXACT", "VALID_NORMALIZED"} and p.canonical_id}
    malformed = [p for p in parsed if p.status == "MALFORMED"]
    ambiguous = [p for p in parsed if p.status == "AMBIGUOUS"]

    by_doc: dict[str, list[DocumentImpactEvidence]] = {}

    def add(doc_id: str, ev: DocumentImpactEvidence) -> None:
        by_doc.setdefault(doc_id, []).append(ev)

    # Presence / role (never sufficient alone)
    for d in uploaded_docs:
        did = str(d.get("document_id") or "")
        role = str(d.get("role") or "custom")
        add(
            did,
            DocumentImpactEvidence(
                document_id=did,
                document_role=role,
                evidence_type="DOCUMENT_PRESENCE",
                evidence_value=str(d.get("filename") or did),
                source_stage="upload",
                confidence=0.1,
                independent_group="presence",
                reason_codes=["document_uploaded"],
                supports_impacted=False,
                supports_review=False,
            ),
        )
        if role in {"requirements", "design", "traceability"}:
            add(
                did,
                DocumentImpactEvidence(
                    document_id=did,
                    document_role=role,
                    evidence_type="ROLE_COMPATIBILITY",
                    evidence_value=role,
                    source_stage="catalog_role",
                    confidence=0.2,
                    independent_group="role",
                    reason_codes=["role_compatible"],
                    supports_impacted=False,
                    supports_review=False,
                ),
            )

    # Node-level matches → evidence on that document_id only (no set-wide propagation)
    for c in patch_candidates:
        did = str(c.get("document_id") or "MDTM")
        matched = c.get("matched_requirement_ids") or []
        et = "EXACT_IDENTIFIER_MATCH"
        add(
            did,
            DocumentImpactEvidence(
                document_id=did,
                document_role="traceability",
                evidence_type=et,
                evidence_value=",".join(matched) or str(c.get("node_id") or ""),
                source_stage="mdtm_change_poc",
                source_node_id=c.get("node_id"),
                confidence=0.95,
                independent_group=f"node:{c.get('node_id')}",
                reason_codes=list(c.get("reason_codes") or ["exact_requirement_id_match"]),
                supports_impacted=True,
                supports_review=False,
            ),
        )

    for c in review_required:
        did = str(c.get("document_id") or "MDTM")
        reasons = list(c.get("reason_codes") or [])
        if "indirect_design_or_test_match" in reasons:
            et = "SEMANTIC_SECTION_MATCH"
        elif "semantic_or_lexical_overlap_only" in reasons:
            et = "SEMANTIC_SECTION_MATCH"
        else:
            et = "SEMANTIC_SECTION_MATCH"
        add(
            did,
            DocumentImpactEvidence(
                document_id=did,
                document_role="traceability",
                evidence_type=et,
                evidence_value=str(c.get("node_id") or c.get("item_id") or ""),
                source_stage="mdtm_change_poc",
                source_node_id=c.get("node_id"),
                confidence=0.55,
                independent_group=f"review:{c.get('node_id')}",
                reason_codes=reasons or ["review_required"],
                supports_impacted=False,
                supports_review=True,
            ),
        )

    # Malformed / ambiguous at CR level — attach to docs that have presence only (no exact)
    for d in uploaded_docs:
        did = str(d.get("document_id") or "")
        for p in malformed:
            add(
                did,
                DocumentImpactEvidence(
                    document_id=did,
                    document_role=str(d.get("role") or ""),
                    evidence_type="MALFORMED_IDENTIFIER",
                    evidence_value=p.raw_text,
                    source_stage="identifier_parser",
                    confidence=0.2,
                    independent_group="malformed_cr",
                    reason_codes=list(p.reason_codes),
                    supports_impacted=False,
                    supports_review=False,
                ),
            )
        for p in ambiguous:
            add(
                did,
                DocumentImpactEvidence(
                    document_id=did,
                    document_role=str(d.get("role") or ""),
                    evidence_type="AMBIGUOUS_IDENTIFIER",
                    evidence_value=p.raw_text or "ambiguous",
                    source_stage="identifier_parser",
                    confidence=0.2,
                    independent_group="ambiguous_cr",
                    reason_codes=list(p.reason_codes),
                    supports_impacted=False,
                    supports_review=True,
                ),
            )

    # Explicit document mention in CR (e.g. "MDTM만") — weak cross hint, not auto-IMPACT for others
    cr_l = (change_request or "").lower()
    for d in uploaded_docs:
        did = str(d.get("document_id") or "")
        name = str(d.get("filename") or "").lower()
        stem = Path(name).stem.lower()
        if did.lower() in cr_l or stem in cr_l or (did == "MDTM" and "mdtm" in cr_l):
            add(
                did,
                DocumentImpactEvidence(
                    document_id=did,
                    document_role=str(d.get("role") or ""),
                    evidence_type="CROSS_DOCUMENT_IDENTIFIER_MATCH"
                    if valid_ids
                    else "SEMANTIC_SECTION_MATCH",
                    evidence_value="explicit_document_mention",
                    source_stage="change_request_mention",
                    confidence=0.5,
                    independent_group="cr_mention",
                    reason_codes=["explicit_document_mention"],
                    supports_impacted=bool(valid_ids) and did == "MDTM",
                    supports_review=True,
                ),
            )

    # Ensure MDTM key exists when candidates reference MDTM but upload id differs
    if any(c.get("document_id") == "MDTM" for c in patch_candidates + review_required):
        by_doc.setdefault("MDTM", by_doc.get("MDTM", []))

    return by_doc


def decide_document_impacts(
    evidence_by_doc: dict[str, list[DocumentImpactEvidence]],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for doc_id, evs in sorted(evidence_by_doc.items()):
        malformed_only = bool(evs) and all(
            e.evidence_type in {"MALFORMED_IDENTIFIER", "ROLE_COMPATIBILITY", "DOCUMENT_PRESENCE"}
            for e in evs
        )
        status, reasons = decide_status_from_evidence(evs, malformed_only=malformed_only)
        substantive = [e for e in evs if e.is_substantive]
        role_ev = [e for e in evs if e.evidence_type in {"ROLE_COMPATIBILITY", "DOCUMENT_PRESENCE"}]
        exact = [e for e in evs if e.evidence_type == "EXACT_IDENTIFIER_MATCH"]
        norm = [e for e in evs if e.evidence_type == "NORMALIZED_IDENTIFIER_MATCH"]
        sem = [e for e in evs if e.evidence_type == "SEMANTIC_SECTION_MATCH"]
        mal = [e for e in evs if e.evidence_type == "MALFORMED_IDENTIFIER"]
        top = sorted(evs, key=lambda e: (-e.confidence, e.evidence_type))[:5]
        decisions.append(
            {
                "document_id": doc_id,
                "predicted_status": status,
                "substantive_evidence_count": len(substantive),
                "role_evidence_count": len(role_ev),
                "exact_identifier_count": len(exact),
                "normalized_identifier_count": len(norm),
                "semantic_evidence_count": len(sem),
                "malformed_identifier_count": len(mal),
                "reason_codes": reasons,
                "source_stages": sorted({e.source_stage for e in evs}),
                "top_evidence": [e.to_dict() for e in top],
                "human_review_required": status == "REVIEW_REQUIRED",
            }
        )
    return decisions


def validate_document_impact_decisions(
    decisions: list[dict[str, Any]],
    evidence_by_doc: dict[str, list[DocumentImpactEvidence]],
) -> dict[str, Any]:
    issues: list[str] = []
    for d in decisions:
        did = d["document_id"]
        evs = evidence_by_doc.get(did) or []
        substantive = [e for e in evs if e.is_substantive]
        if d["predicted_status"] == "IMPACTED" and not substantive:
            issues.append(f"impacted_requires_substantive_evidence:{did}")
        if d["predicted_status"] == "IMPACTED" and d.get("substantive_evidence_count", 0) == 0:
            issues.append(f"no_role_only_impacted:{did}")
        if d.get("exact_identifier_count", 0) and any(
            e.evidence_type == "MALFORMED_IDENTIFIER" and e.supports_impacted for e in evs
        ):
            issues.append(f"malformed_id_not_exact:{did}")
        # semantic-only must not be IMPACTED without exact
        if (
            d["predicted_status"] == "IMPACTED"
            and d.get("exact_identifier_count", 0) == 0
            and d.get("normalized_identifier_count", 0) == 0
            and d.get("semantic_evidence_count", 0) > 0
            and not any(e.evidence_type == "CROSS_DOCUMENT_IDENTIFIER_MATCH" for e in evs)
        ):
            # allow IMPACTED only with cross-doc or exact; else flag
            if not any(e.supports_impacted and e.is_substantive for e in evs):
                issues.append(f"no_semantic_only_patch:{did}")
    return {
        "ok": not issues,
        "status": "VALID" if not issues else "INVALID",
        "issues": issues,
        "invariants": [
            "no_role_only_impacted",
            "malformed_id_not_exact",
            "impacted_requires_substantive_evidence",
            "no_semantic_only_patch",
            "no_document_set_membership_promotion",
        ],
    }


def write_document_impact_artifacts(
    out_dir: Path,
    *,
    parsed_ids: list[ParsedRequirementId],
    evidence_by_doc: dict[str, list[DocumentImpactEvidence]],
    decisions: list[dict[str, Any]],
) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_document_impact_decisions(decisions, evidence_by_doc)
    summary = {
        "document_count": len(decisions),
        "impacted": sum(1 for d in decisions if d["predicted_status"] == "IMPACTED"),
        "review_required": sum(1 for d in decisions if d["predicted_status"] == "REVIEW_REQUIRED"),
        "unrelated": sum(1 for d in decisions if d["predicted_status"] == "UNRELATED"),
        "valid_requirement_ids": valid_canonical_requirement_ids(
            " ".join(p.raw_text for p in parsed_ids if p.raw_text)
        )
        or [p.canonical_id for p in parsed_ids if p.canonical_id and p.status.startswith("VALID")],
        "malformed_count": sum(1 for p in parsed_ids if p.status == "MALFORMED"),
        "validation_ok": validation["ok"],
    }
    paths = {
        "ec_sw_identifier_analysis.json": [p.to_dict() for p in parsed_ids],
        "ec_sw_document_impact_evidence.json": {
            k: [e.to_dict() for e in v] for k, v in evidence_by_doc.items()
        },
        "ec_sw_document_impact_decisions.json": decisions,
        "ec_sw_document_impact_summary.json": summary,
        "ec_sw_document_impact_validation.json": validation,
    }
    written = {}
    for name, payload in paths.items():
        path = out_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written[name] = str(path).replace("\\", "/")
    return written
