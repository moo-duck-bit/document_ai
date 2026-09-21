# -*- coding: utf-8 -*-
"""Target existence decisions for generic document packs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TargetStatus = Literal[
    "EXISTS_EXACT",
    "EXISTS_SEMANTIC",
    "MISSING_ADDABLE",
    "MISSING_UNSUPPORTED",
    "AMBIGUOUS",
    "UNRELATED",
    "INVALID",
]


@dataclass
class TargetExistenceDecision:
    document_id: str
    requested_concepts: list[str] = field(default_factory=list)
    matched_sections: list[str] = field(default_factory=list)
    matched_nodes: list[str] = field(default_factory=list)
    target_exists: bool = False
    target_status: TargetStatus = "UNRELATED"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    human_review_required: bool = False
    virtual_target: bool = False
    template_node_id: str | None = None
    writer_supported: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Template section ids considered addable for general_report (writer still unsupported in MVP)
_ADDABLE_SECTIONS = frozenset(
    {
        "methodology",
        "results",
        "discussion",
        "conclusion",
        "references",
        "schedule",
        "appendix",
        "background",
        "objectives",
    }
)


def decide_target_existence(
    *,
    document_id: str,
    requested_concepts: set[str] | list[str],
    document_heading_concepts: set[str] | None = None,
    document_heading_tokens: set[str] | None = None,
    cr_tokens: set[str] | None = None,
    template_section_hits: list[dict[str, Any]] | None = None,
    document_node_hits: list[dict[str, Any]] | None = None,
    schedule_document_grounded: bool = False,
) -> TargetExistenceDecision:
    """Classify whether the CR targets an existing / missing / unrelated section."""
    concepts = sorted({c for c in (requested_concepts or []) if c})
    cr_toks = set(cr_tokens or [])
    doc_concepts = set(document_heading_concepts or [])
    doc_toks = set(document_heading_tokens or [])
    tmpl_hits = [h for h in (template_section_hits or []) if h.get("status") == "REVIEW_REQUIRED"]
    doc_hits = list(document_node_hits or [])

    matched_sections = [
        str(h.get("node_id") or h.get("display_name") or "")
        for h in tmpl_hits
        if h.get("node_id")
    ]
    matched_nodes = [
        str(h.get("node_id") or "")
        for h in doc_hits
        if h.get("node_id")
    ]

    # Exact: document paragraph/heading/table grounded
    if doc_hits or schedule_document_grounded:
        return TargetExistenceDecision(
            document_id=document_id,
            requested_concepts=concepts,
            matched_sections=matched_sections,
            matched_nodes=matched_nodes,
            target_exists=True,
            target_status="EXISTS_EXACT" if (doc_hits or schedule_document_grounded) else "EXISTS_SEMANTIC",
            evidence=[{"type": "DOCUMENT_NODE", "node_id": n} for n in matched_nodes[:8]],
            reason_codes=["document_grounded_target"],
            human_review_required=True,
        )

    # Semantic: CR concepts overlap document headings
    if concepts and doc_concepts and set(concepts) & doc_concepts:
        return TargetExistenceDecision(
            document_id=document_id,
            requested_concepts=concepts,
            matched_sections=matched_sections,
            matched_nodes=[],
            target_exists=True,
            target_status="EXISTS_SEMANTIC",
            evidence=[{"type": "HEADING_CONCEPT", "concepts": sorted(set(concepts) & doc_concepts)}],
            reason_codes=["semantic_heading_overlap"],
            human_review_required=True,
        )

    # Token overlap with document headings (any shared heading token)
    shared = cr_toks & doc_toks
    if shared:
        return TargetExistenceDecision(
            document_id=document_id,
            requested_concepts=concepts,
            matched_sections=matched_sections,
            matched_nodes=[],
            target_exists=True,
            target_status="EXISTS_SEMANTIC",
            evidence=[{"type": "HEADING_TOKEN", "tokens": sorted(shared)[:12]}],
            reason_codes=["heading_token_overlap"],
            human_review_required=True,
        )

    # Template-only hit → missing addable / unsupported
    if tmpl_hits:
        addable = []
        unsupported = []
        for h in tmpl_hits:
            sid = str(h.get("node_id") or "").split(".")[-1]
            if sid in _ADDABLE_SECTIONS:
                addable.append(h)
            else:
                unsupported.append(h)
        if addable and not doc_hits:
            top = addable[0]
            return TargetExistenceDecision(
                document_id=document_id,
                requested_concepts=concepts,
                matched_sections=matched_sections,
                matched_nodes=[],
                target_exists=False,
                target_status="MISSING_ADDABLE",
                evidence=[{"type": "TEMPLATE_ONLY", "node_id": top.get("node_id")}],
                reason_codes=["missing_addable_target", "writer_unsupported_mvp"],
                human_review_required=True,
                virtual_target=True,
                template_node_id=str(top.get("node_id")),
                writer_supported=False,
            )
        return TargetExistenceDecision(
            document_id=document_id,
            requested_concepts=concepts,
            matched_sections=matched_sections,
            matched_nodes=[],
            target_exists=False,
            target_status="MISSING_UNSUPPORTED",
            evidence=[{"type": "TEMPLATE_ONLY", "count": len(tmpl_hits)}],
            reason_codes=["missing_unsupported_or_template_only"],
            human_review_required=True,
            virtual_target=True,
            writer_supported=False,
        )

    if not concepts and not cr_toks:
        return TargetExistenceDecision(
            document_id=document_id,
            target_status="INVALID",
            reason_codes=["empty_change_request"],
            human_review_required=True,
        )

    return TargetExistenceDecision(
        document_id=document_id,
        requested_concepts=concepts,
        target_exists=False,
        target_status="UNRELATED",
        reason_codes=["no_target_evidence"],
        human_review_required=False,
    )
