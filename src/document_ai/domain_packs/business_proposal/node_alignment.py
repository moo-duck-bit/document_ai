# -*- coding: utf-8 -*-
"""Business Proposal template ↔ document alignment helpers."""

from __future__ import annotations

from typing import Any

from document_ai.domain_packs.business_proposal.concepts import normalize_proposal_concepts
from document_ai.template.concept_normalization import normalize_concepts
from document_ai.template.node_alignment import build_node_alignments


def proposal_alignment_id(
    *,
    document_id: str,
    template_node_id: str,
    document_node_id: str,
    alignment_type: str,
) -> str:
    return f"BP-{document_id}-{template_node_id}-{document_node_id}-{alignment_type}"


def _enrich_alignment(alignment: dict[str, Any]) -> dict[str, Any]:
    tmpl = str(alignment.get("template_node_id") or "")
    doc = str(alignment.get("document_node_id") or "")
    blob = " ".join([tmpl, doc, str(alignment.get("section_id") or "")])
    concepts = sorted(normalize_proposal_concepts(blob) | normalize_concepts(blob))
    out = dict(alignment)
    out["canonical_concept"] = concepts[0] if concepts else None
    out["canonical_concepts"] = concepts
    out["alignment_type"] = out.get("alignment_type") or "REVIEW_CONTEXT"
    out["evaluation_equivalence"] = bool(out.get("equivalent_for_evaluation"))
    out["patch_equivalence"] = bool(out.get("equivalent_for_patch"))
    if not out.get("alignment_id"):
        out["alignment_id"] = proposal_alignment_id(
            document_id=str(out.get("document_id") or ""),
            template_node_id=tmpl,
            document_node_id=doc,
            alignment_type=str(out["alignment_type"]),
        )
    return out


def build_proposal_alignments(
    *,
    document_id: str,
    template_review_items: list[dict[str, Any]],
    document_review_items: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = build_node_alignments(
        document_id=document_id,
        template_review_items=template_review_items,
        document_review_items=document_review_items,
    )
    enriched = [_enrich_alignment(a) for a in payload.get("alignments") or []]
    payload["alignments"] = enriched
    return payload
