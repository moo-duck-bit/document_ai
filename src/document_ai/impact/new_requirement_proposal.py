# -*- coding: utf-8 -*-
"""Zero-IMPACTED fallback: structured NEW_REQUIREMENT / NEEDS_REVIEW proposals.

Does not insert requirements into DOCX. Does not use expected_impact.*.
Does not hard-code scenario-specific Req IDs or feature keywords.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from document_ai.impact.impact_judgment import ImpactDecision
from document_ai.impact.semantic_hybrid_retrieve import ScoredHit

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")


@dataclass
class NewRequirementProposal:
    status: str = "NEW_REQUIREMENT_CANDIDATE"
    proposed_title: str = ""
    proposed_requirement_intent: str = ""
    source_cr: str = ""
    related_existing_req_candidates: list[dict[str, Any]] = field(default_factory=list)
    why_existing_may_be_insufficient: str = ""
    potential_mdsr_location: str = ""
    potential_mddr_impact: str = ""
    human_decision_required: list[str] = field(default_factory=list)
    trigger: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _title_from_cr(cr: str, *, max_len: int = 80) -> str:
    line = " ".join((cr or "").strip().split())
    if not line:
        return "Untitled change request"
    # First clause / sentence as title seed — not a permanent Req number
    for sep in (".", "。", "\n"):
        if sep in line:
            line = line.split(sep, 1)[0].strip()
            break
    if len(line) > max_len:
        line = line[: max_len - 1].rstrip() + "…"
    return line


def should_emit_zero_impacted_fallback(
    decisions: list[ImpactDecision],
    ranked: list[ScoredHit],
    *,
    top_n: int = 8,
) -> bool:
    """Emit proposal only when zero IMPACTED *and* evidence-related candidates exist.

    Ranked Top-k existence alone is never sufficient (all-NOT_RELATED must not emit).
    """
    if any(d.judgment == "IMPACTED" for d in decisions):
        return False
    if not ranked:
        return False

    by_key = {(d.candidate_id, d.document): d for d in decisions}
    top_keys = {(h.candidate_id, h.document) for h in ranked[:top_n]}

    def _has_related_evidence(d: ImpactDecision) -> bool:
        ev = d.evidence_structured or {}
        concepts = ev.get("matched_concepts") or []
        facets = ev.get("behavioral_overlap") or {}
        relevance = float((d.scores or {}).get("relevance") or 0.0)
        if d.change_type in {"EXTEND_EXISTING", "NEW_REQUIREMENT_CANDIDATE", "MODIFY_EXISTING"}:
            return True
        if d.judgment == "UNCERTAIN" and (concepts or facets) and relevance >= 0.05:
            return True
        if concepts and facets and relevance >= 0.06:
            return True
        return False

    relatedish = [
        d
        for d in decisions
        if (d.candidate_id, d.document) in top_keys
        and d.change_type != "NOT_RELATED"
        and _has_related_evidence(d)
    ]
    return bool(relatedish)


def build_new_requirement_proposal(
    cr_text: str,
    decisions: list[ImpactDecision],
    ranked: list[ScoredHit],
    *,
    top_n: int = 8,
) -> NewRequirementProposal | None:
    """Build structured proposal when no candidate is safely IMPACTED."""
    if not should_emit_zero_impacted_fallback(decisions, ranked, top_n=top_n):
        return None

    by_key = {(d.candidate_id, d.document): d for d in decisions}
    related: list[dict[str, Any]] = []
    for hit in ranked[:top_n]:
        d = by_key.get((hit.candidate_id, hit.document))
        if d and d.judgment == "NOT_IMPACTED" and d.change_type == "NOT_RELATED":
            # skip clear non-related unless very top-ranked (still list lightly)
            if hit.rank > 3:
                continue
        related.append(
            {
                "req_id": hit.candidate_id,
                "document": hit.document,
                "rank": hit.rank,
                "hybrid_score": hit.hybrid_score,
                "judgment": d.judgment if d else None,
                "change_type": d.change_type if d else None,
                "title": hit.title,
                "reason": (d.reason[:200] if d else ""),
            }
        )

    mdsr_related = [r for r in related if r["document"] == "MDSR"]
    mddr_related = [r for r in related if r["document"] == "MDDR"]

    insufficient = (
        "No candidate was judged IMPACTED with evidence sufficient for safe auto-modify. "
        "Top retrieval hits may be thematically adjacent but lack in-scope applicability, "
        "or the CR introduces responsibilities not covered by existing requirement blocks."
    )

    return NewRequirementProposal(
        status="NEW_REQUIREMENT_CANDIDATE",
        proposed_title=_title_from_cr(cr_text),
        proposed_requirement_intent=" ".join(cr_text.split()),
        source_cr=cr_text.strip(),
        related_existing_req_candidates=related,
        why_existing_may_be_insufficient=insufficient,
        potential_mdsr_location=(
            "Human to place under the functional area of related MDSR candidates: "
            + (", ".join(r["req_id"] for r in mdsr_related[:5]) or "(none ranked)")
            + ". Do not assign a permanent Req number until approved."
        ),
        potential_mddr_impact=(
            "If approved, review MDDR designs linked to related candidates: "
            + (", ".join(r["req_id"] for r in mddr_related[:5]) or "(none ranked)")
            + " for computation, persistence, and UI/API display responsibilities."
        ),
        human_decision_required=[
            "Extend an existing related requirement (EXTEND_EXISTING)",
            "OR create a new requirement (NEW_REQUIREMENT_CANDIDATE) with human-assigned ID",
            "OR mark CR out of scope / defer",
        ],
        trigger="zero_IMPACTED_with_ranked_candidates",
        notes=[
            "Proposal only — DOCX not modified for new requirement insertion.",
            "Status remains NEW_REQUIREMENT_CANDIDATE until human approval.",
        ],
    )


def render_new_requirement_markdown(proposal: NewRequirementProposal) -> str:
    lines = [
        "# NEW_REQUIREMENT_CANDIDATE Proposal",
        "",
        f"- status: `{proposal.status}`",
        f"- trigger: `{proposal.trigger}`",
        "",
        "## Proposed title",
        "",
        proposal.proposed_title,
        "",
        "## Proposed requirement intent",
        "",
        proposal.proposed_requirement_intent,
        "",
        "## Source CR",
        "",
        "```",
        proposal.source_cr,
        "```",
        "",
        "## Related existing requirement candidates",
        "",
    ]
    if not proposal.related_existing_req_candidates:
        lines.append("- (none)")
    for r in proposal.related_existing_req_candidates:
        lines.append(
            f"- {r.get('req_id')} [{r.get('document')}] rank={r.get('rank')} "
            f"judgment={r.get('judgment')} change_type={r.get('change_type')} "
            f"— {r.get('title')}"
        )
    lines.extend(
        [
            "",
            "## Why existing requirements may be insufficient",
            "",
            proposal.why_existing_may_be_insufficient,
            "",
            "## Potential MDSR location",
            "",
            proposal.potential_mdsr_location,
            "",
            "## Potential MDDR impact",
            "",
            proposal.potential_mddr_impact,
            "",
            "## Human decision required",
            "",
        ]
    )
    for item in proposal.human_decision_required:
        lines.append(f"- {item}")
    lines.extend(["", "## Notes", ""])
    for n in proposal.notes:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)
