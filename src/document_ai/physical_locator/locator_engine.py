# -*- coding: utf-8 -*-
"""PR-23: Physical locator engine (single-target processing)."""

from __future__ import annotations

from document_ai.document_parser.structure import DocumentModel
from document_ai.physical_locator.candidate_builder import build_physical_candidates
from document_ai.physical_locator.ranking import decide_location_status, rank_candidates
from document_ai.physical_locator.schema import (
    PhysicalLocatorInput,
    PhysicalLocationCandidate,
    PrimaryPhysicalLocation,
)


def locate_physical_target(
    inp: PhysicalLocatorInput,
    doc: DocumentModel | None,
    *,
    seq: int,
) -> tuple[list[PhysicalLocationCandidate], PrimaryPhysicalLocation]:
    """Map one logical patch target to ranked physical locations (observational)."""
    broken = False
    reasons_pre: list[str] = []

    if inp.target_status == "INVALID":
        broken = True
        reasons_pre.append("INVALID_PATCH_TARGET")
    if not inp.document_id:
        broken = True
        reasons_pre.append("MISSING_DOCUMENT_ID")
    if doc is None:
        broken = True
        reasons_pre.append("DOCUMENT_NOT_FOUND")
    elif inp.document_id and doc.document_id != inp.document_id:
        broken = True
        reasons_pre.append("DOCUMENT_ID_MISMATCH")
    if inp.section_id and doc is not None:
        sec_ids = {s.section_id for s in doc.sections}
        # section_id from template may not equal structure section_id — not automatically broken
        # Only mark broken if metadata forces exact structure section
        if inp.metadata.get("require_structure_section") and inp.section_id not in sec_ids:
            broken = True
            reasons_pre.append("SECTION_NOT_FOUND")

    if broken:
        primary = PrimaryPhysicalLocation(
            primary_location_id=f"PPL-{seq:04d}",
            patch_target_candidate_id=inp.patch_target_candidate_id,
            document_id=inp.document_id,
            physical_candidate_id=None,
            location_status="INVALID",
            reason_codes=reasons_pre + ["BROKEN_REFERENCE"],
            evidence={"observational_only": True},
            actual_docx_changed=False,
            actual_writer_called=False,
            actual_patch_created=False,
        )
        return [], primary

    raw = build_physical_candidates(inp, doc, seq_prefix=f"PLC{seq:02d}")
    ranked = rank_candidates(raw, inp)
    status, reasons, top1, top2, margin = decide_location_status(
        ranked,
        preferred_location_type=inp.preferred_location_type,
    )

    # Top-K keep for artifact (all ranked, but primary uses top1)
    top = ranked[0] if ranked else None
    primary = PrimaryPhysicalLocation(
        primary_location_id=f"PPL-{seq:04d}",
        patch_target_candidate_id=inp.patch_target_candidate_id,
        document_id=inp.document_id,
        physical_candidate_id=top.physical_candidate_id if top else None,
        location_status=status,
        location_type=top.location_type if top else None,
        section_id=top.section_id if top else None,
        heading_path=list(top.heading_path) if top else [],
        location_score=top.location_score if top else 0.0,
        top1_score=top1,
        top2_score=top2,
        score_margin=margin,
        candidate_count=len(ranked),
        reason_codes=reasons,
        evidence={
            "top_k": [
                {
                    "physical_candidate_id": c.physical_candidate_id,
                    "location_type": c.location_type,
                    "location_score": c.location_score,
                    "rank": c.rank,
                }
                for c in ranked[:5]
            ],
            "score_components": dict(top.score_components) if top else {},
            "observational_only": True,
        },
        actual_docx_changed=False,
        actual_writer_called=False,
        actual_patch_created=False,
    )
    return ranked, primary
