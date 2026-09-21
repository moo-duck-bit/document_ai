# -*- coding: utf-8 -*-
"""B5 PR-3: Evidence provenance / lineage (prior-bleed observability).

Tracks independent_group lineage across B3 → B4 → B5 so the same source
evidence is not treated as multiple independent corroborations in traces.

Does NOT change B5v2 confidence / decision formulas (actual path parity).
Shadow candidate comparison does not select a new owner.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EvidenceSourceType = Literal[
    "CR_DIRECT",
    "REQUIREMENT_DIRECT",
    "DESIGN_DIRECT",
    "RETRIEVAL_DERIVED",
    "B3_DERIVED",
    "B4_DERIVED",
    "TRACEABILITY",
]

EvidenceClass = Literal[
    "DIRECT",
    "SUPPORTING",
    "GENERIC",
    "CONFLICTING",
    "DERIVED",
]

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")


@dataclass
class EvidenceItem:
    evidence_id: str
    concept: str
    facet: str
    source_type: EvidenceSourceType | str
    source_span: str
    document: str | None
    candidate_id: str | None
    derived_from: list[str] = field(default_factory=list)
    independent_group: str = ""
    evidence_class: EvidenceClass | str = "DIRECT"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceBundle:
    """Provenance package for one requirement ↔ design alignment."""

    requirement_id: str
    design_id: str
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "design_id": self.design_id,
            "evidence_items": [e.to_dict() for e in self.evidence_items],
            "summary": dict(self.summary),
            "lineage_groups": _lineage_groups_map(self.evidence_items),
        }


def _short_hash(text: str, *, n: int = 10) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:n]


def independent_group_for_span(source_span: str, *, prefix: str = "span") -> str:
    """Same CR/source span → same independent_group (lineage key)."""
    norm = " ".join((source_span or "").split())
    if not norm:
        return f"{prefix}:empty"
    return f"{prefix}:{_short_hash(norm)}"


def make_evidence_id(
    *,
    source_type: str,
    facet: str,
    concept: str,
    independent_group: str,
    stage: str = "",
) -> str:
    raw = f"{stage}|{source_type}|{facet}|{concept}|{independent_group}"
    return f"ev_{_short_hash(raw, n=12)}"


def local_token_df(texts: list[str]) -> dict[str, int]:
    """Document frequency of tokens across a small comparison corpus (CR/MDSR/MDDR)."""
    df: dict[str, int] = {}
    for text in texts:
        toks = {t.lower() for t in TOKEN_RE.findall(text or "")}
        for t in toks:
            df[t] = df.get(t, 0) + 1
    return df


def is_low_specificity_concept(
    concept: str,
    *,
    weak_tokens: set[str],
    local_df: dict[str, int],
    n_docs: int,
    actor_markers: tuple[str, ...] | set[str] = (),
) -> bool:
    """Domain-independent genericity heuristic (no Scenario keyword blacklist).

    Signals:
    - already classified as weak/boilerplate in shared WEAK_TOKENS
    - high local DF across comparison docs + short form
    - actor-marker-only appearance with high DF (role token without discriminative mass)
    """
    c = (concept or "").strip().lower()
    if not c:
        return True
    if c in {w.lower() for w in weak_tokens}:
        return True
    df = int(local_df.get(c, 0))
    if n_docs >= 2 and df >= max(2, n_docs) and len(c) <= 3:
        return True
    markers = {m.lower() for m in actor_markers}
    if c in markers and df >= max(2, n_docs - 1):
        return True
    return False


def find_span_containing(text: str, concept: str, *, limit: int = 160) -> str:
    """Best-effort source span for a concept within text."""
    if not text or not concept:
        return (text or "")[:limit].replace("\n", " ")
    parts = re.split(r"[.\n。]+", text)
    for p in parts:
        if concept in p:
            return p.strip()[:limit]
    cl = concept.lower()
    for p in parts:
        if cl in p.lower():
            return p.strip()[:limit]
    return (text or "")[:limit].replace("\n", " ")


def summarize_evidence_items(items: list[EvidenceItem]) -> dict[str, Any]:
    """Provenance-aware counts — derived/prior do not inflate direct independent groups."""
    direct_groups: set[str] = set()
    supporting_groups: set[str] = set()
    generic_items = 0
    derived_prior = 0
    conflicting = 0
    unique_groups: set[str] = set()
    lineage_summary: list[dict[str, Any]] = []

    by_group: dict[str, list[EvidenceItem]] = {}
    for it in items:
        unique_groups.add(it.independent_group)
        by_group.setdefault(it.independent_group, []).append(it)
        if it.evidence_class == "CONFLICTING":
            conflicting += 1
        if it.evidence_class == "GENERIC":
            generic_items += 1
        if it.evidence_class == "DERIVED" or it.source_type in ("B3_DERIVED", "B4_DERIVED"):
            derived_prior += 1
        if it.evidence_class == "DIRECT":
            direct_groups.add(it.independent_group)
        elif it.evidence_class == "SUPPORTING":
            supporting_groups.add(it.independent_group)

    for gid, group_items in sorted(by_group.items()):
        lineage_summary.append(
            {
                "independent_group": gid,
                "item_count": len(group_items),
                "source_types": sorted({i.source_type for i in group_items}),
                "evidence_classes": sorted({i.evidence_class for i in group_items}),
                "concepts": sorted({i.concept for i in group_items if i.concept})[:12],
                "has_derived": any(
                    i.evidence_class == "DERIVED" or i.source_type in ("B3_DERIVED", "B4_DERIVED")
                    for i in group_items
                ),
            }
        )

    return {
        "direct_independent_count": len(direct_groups),
        "supporting_independent_count": len(supporting_groups),
        "generic_count": generic_items,
        "derived_prior_count": derived_prior,
        "conflicting_count": conflicting,
        "unique_independent_groups": sorted(unique_groups),
        "unique_independent_group_count": len(unique_groups),
        "evidence_lineage_summary": lineage_summary,
        "note": (
            "Derived/prior projections share independent_group with source; "
            "they are not counted as additional direct independent evidence."
        ),
    }


def _lineage_groups_map(items: list[EvidenceItem]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for it in items:
        out.setdefault(it.independent_group, []).append(it.evidence_id)
    return out


def build_alignment_provenance(
    *,
    cr_text: str,
    mdsr_text: str,
    mddr_text: str,
    requirement_id: str,
    design_id: str,
    b3_prior: dict[str, Any] | None,
    b4_prior: dict[str, Any] | None,
    matched_facets: list[str],
    matched_responsibilities: list[str],
    direct_traceability: list[str],
    conflicts: list[str],
    actor_shared: list[str],
    action_cr_mddr: list[str],
    cr_mddr_content: list[str],
    weak_tokens: set[str],
    actor_markers: tuple[str, ...] = (),
) -> ProvenanceBundle:
    """Build B3/B4/B5-aware provenance for one alignment (sidecar; parity-safe)."""
    b3 = b3_prior or {}
    b4 = b4_prior or {}
    texts = [cr_text or "", mdsr_text or "", mddr_text or ""]
    n_docs = sum(1 for t in texts if t.strip())
    df = local_token_df(texts)

    items: list[EvidenceItem] = []
    root_by_concept: dict[str, str] = {}
    root_by_facet: dict[str, str] = {}

    def _class_for_concept(concept: str, *, default: EvidenceClass = "DIRECT") -> EvidenceClass:
        if is_low_specificity_concept(
            concept,
            weak_tokens=weak_tokens,
            local_df=df,
            n_docs=max(n_docs, 1),
            actor_markers=actor_markers,
        ):
            return "GENERIC"
        return default

    def _gid_of(parent_id: str | None, fallback_span: str) -> str:
        if parent_id:
            for i in items:
                if i.evidence_id == parent_id:
                    return i.independent_group
        return independent_group_for_span(fallback_span)

    # --- CR_DIRECT seeds (object / actor / action) ---
    for concept in cr_mddr_content:
        span = find_span_containing(cr_text, concept)
        gid = independent_group_for_span(span)
        eid = make_evidence_id(
            source_type="CR_DIRECT", facet="object", concept=concept, independent_group=gid, stage="B5"
        )
        cls = _class_for_concept(concept)
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=concept,
                facet="object",
                source_type="CR_DIRECT",
                source_span=span,
                document="CR",
                candidate_id=requirement_id,
                derived_from=[],
                independent_group=gid,
                evidence_class=cls,
            )
        )
        root_by_concept[concept.lower()] = eid
        root_by_facet.setdefault("object", eid)

    for concept in actor_shared:
        span = find_span_containing(cr_text, concept)
        gid = independent_group_for_span(span)
        eid = make_evidence_id(
            source_type="CR_DIRECT", facet="actor", concept=concept, independent_group=gid, stage="B5"
        )
        cls = _class_for_concept(concept, default="SUPPORTING")
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=concept,
                facet="actor",
                source_type="CR_DIRECT",
                source_span=span,
                document="CR",
                candidate_id=requirement_id,
                derived_from=[],
                independent_group=gid,
                evidence_class=cls,
            )
        )
        root_by_concept.setdefault(concept.lower(), eid)
        root_by_facet.setdefault("actor", eid)

    for concept in action_cr_mddr:
        span = find_span_containing(cr_text, concept)
        gid = independent_group_for_span(span)
        eid = make_evidence_id(
            source_type="CR_DIRECT", facet="action", concept=concept, independent_group=gid, stage="B5"
        )
        cls = _class_for_concept(concept)
        design_span = find_span_containing(mddr_text, concept)
        notes: list[str] = []
        if design_span and span and design_span.strip() != span.strip():
            notes.append("surface_match_divergent_spans")
            if cls == "DIRECT":
                cls = "SUPPORTING"
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=concept,
                facet="action",
                source_type="CR_DIRECT",
                source_span=span,
                document="CR",
                candidate_id=requirement_id,
                derived_from=[],
                independent_group=gid,
                evidence_class=cls,
                notes=notes,
            )
        )
        root_by_concept.setdefault(concept.lower(), eid)
        root_by_facet.setdefault("action", eid)

    # DESIGN_DIRECT mirror — same independent_group (not a new corroboration)
    for concept in cr_mddr_content[:8]:
        parent = root_by_concept.get(concept.lower())
        if not parent:
            continue
        parent_item = next(i for i in items if i.evidence_id == parent)
        design_span = find_span_containing(mddr_text, concept)
        eid = make_evidence_id(
            source_type="DESIGN_DIRECT",
            facet="object",
            concept=concept,
            independent_group=parent_item.independent_group,
            stage="B5",
        )
        notes = []
        if design_span and parent_item.source_span and design_span.strip() != parent_item.source_span.strip():
            notes.append("surface_match_divergent_spans")
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=concept,
                facet="object",
                source_type="DESIGN_DIRECT",
                source_span=design_span,
                document="MDDR",
                candidate_id=design_id or None,
                derived_from=[parent],
                independent_group=parent_item.independent_group,
                evidence_class=(
                    "GENERIC" if parent_item.evidence_class == "GENERIC" else "SUPPORTING"
                ),
                notes=notes,
            )
        )

    # --- B3_DERIVED ---
    for concept in b3.get("matched_concepts") or []:
        if not isinstance(concept, str) or not concept:
            continue
        parent = root_by_concept.get(concept.lower())
        span = find_span_containing(cr_text, concept)
        gid = _gid_of(parent, span)
        if parent is None:
            root_eid = make_evidence_id(
                source_type="CR_DIRECT",
                facet="concept",
                concept=concept,
                independent_group=gid,
                stage="B3",
            )
            items.append(
                EvidenceItem(
                    evidence_id=root_eid,
                    concept=concept,
                    facet="concept",
                    source_type="CR_DIRECT",
                    source_span=span,
                    document="CR",
                    candidate_id=requirement_id,
                    derived_from=[],
                    independent_group=gid,
                    evidence_class=_class_for_concept(concept, default="SUPPORTING"),
                )
            )
            parent = root_eid
            root_by_concept[concept.lower()] = root_eid
        eid = make_evidence_id(
            source_type="B3_DERIVED",
            facet="matched_concept",
            concept=concept,
            independent_group=gid,
            stage="B3",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=concept,
                facet="matched_concept",
                source_type="B3_DERIVED",
                source_span=span,
                document="B3",
                candidate_id=requirement_id,
                derived_from=[parent] if parent else [],
                independent_group=gid,
                evidence_class="DERIVED",
            )
        )

    behavioral = b3.get("behavioral_overlap") if isinstance(b3.get("behavioral_overlap"), dict) else {}
    for facet, vals in behavioral.items():
        if not vals:
            continue
        parent = root_by_facet.get(str(facet))
        concept = ""
        if isinstance(vals, list) and vals:
            concept = str(vals[0])
        elif isinstance(vals, str):
            concept = vals
        span = find_span_containing(cr_text, concept) if concept else (cr_text or "")[:160]
        if parent is None and concept:
            parent = root_by_concept.get(concept.lower())
        gid = _gid_of(parent, span)
        eid = make_evidence_id(
            source_type="B3_DERIVED",
            facet=str(facet),
            concept=concept or str(facet),
            independent_group=gid,
            stage="B3",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=concept or str(facet),
                facet=str(facet),
                source_type="B3_DERIVED",
                source_span=span,
                document="B3",
                candidate_id=requirement_id,
                derived_from=[parent] if parent else [],
                independent_group=gid,
                evidence_class="DERIVED",
            )
        )
        root_by_facet.setdefault(str(facet), parent or eid)

    # --- B4_DERIVED ---
    for facet in b4.get("compatible_facets") or []:
        facet_s = str(facet)
        parent = root_by_facet.get(facet_s)
        gid = _gid_of(parent, f"b4:{facet_s}")
        if parent is None:
            root_eid = make_evidence_id(
                source_type="CR_DIRECT",
                facet=facet_s,
                concept=facet_s,
                independent_group=gid,
                stage="B4",
            )
            items.append(
                EvidenceItem(
                    evidence_id=root_eid,
                    concept=facet_s,
                    facet=facet_s,
                    source_type="CR_DIRECT",
                    source_span=f"facet:{facet_s}",
                    document="CR",
                    candidate_id=requirement_id,
                    derived_from=[],
                    independent_group=gid,
                    evidence_class="SUPPORTING",
                )
            )
            parent = root_eid
            root_by_facet[facet_s] = root_eid
        eid = make_evidence_id(
            source_type="B4_DERIVED",
            facet=facet_s,
            concept=facet_s,
            independent_group=gid,
            stage="B4",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=facet_s,
                facet=facet_s,
                source_type="B4_DERIVED",
                source_span=f"b4_compatible:{facet_s}",
                document="B4",
                candidate_id=requirement_id,
                derived_from=[parent] if parent else [],
                independent_group=gid,
                evidence_class="DERIVED",
            )
        )

    for facet in b4.get("conflicting_facets") or []:
        facet_s = str(facet)
        gid = independent_group_for_span(f"b4_conflict:{facet_s}")
        eid = make_evidence_id(
            source_type="B4_DERIVED",
            facet=facet_s,
            concept=facet_s,
            independent_group=gid,
            stage="B4",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=facet_s,
                facet=facet_s,
                source_type="B4_DERIVED",
                source_span=f"b4_conflict:{facet_s}",
                document="B4",
                candidate_id=requirement_id,
                derived_from=[],
                independent_group=gid,
                evidence_class="CONFLICTING",
            )
        )

    # B5 b3_prior_* projections → DERIVED, same group
    for facet in matched_facets:
        if not str(facet).startswith("b3_prior_"):
            continue
        base = str(facet).removeprefix("b3_prior_")
        parent = root_by_facet.get(base)
        gid = _gid_of(parent, f"b3_prior:{base}")
        eid = make_evidence_id(
            source_type="B3_DERIVED",
            facet=str(facet),
            concept=base,
            independent_group=gid,
            stage="B5",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=base,
                facet=str(facet),
                source_type="B3_DERIVED",
                source_span=f"b5_projection:{facet}",
                document="B5",
                candidate_id=design_id or requirement_id,
                derived_from=[parent] if parent else [],
                independent_group=gid,
                evidence_class="DERIVED",
                notes=["prior_projection_not_independent_direct"],
            )
        )

    for facet in matched_facets:
        if str(facet).startswith("b3_prior_"):
            continue
        facet_s = str(facet)
        if facet_s in root_by_facet:
            continue
        gid = independent_group_for_span(f"b5_facet:{facet_s}")
        eid = make_evidence_id(
            source_type="DESIGN_DIRECT",
            facet=facet_s,
            concept=facet_s,
            independent_group=gid,
            stage="B5",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=facet_s,
                facet=facet_s,
                source_type="DESIGN_DIRECT",
                source_span=f"matched_facet:{facet_s}",
                document="B5",
                candidate_id=design_id or None,
                derived_from=[],
                independent_group=gid,
                evidence_class="SUPPORTING",
            )
        )
        root_by_facet[facet_s] = eid

    # Traceability — separate from ownership
    for t in direct_traceability:
        gid = f"traceability:{t}"
        eid = make_evidence_id(
            source_type="TRACEABILITY",
            facet="traceability",
            concept=str(t),
            independent_group=gid,
            stage="B5",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=str(t),
                facet="traceability",
                source_type="TRACEABILITY",
                source_span=str(t),
                document="MDSR+MDDR",
                candidate_id=requirement_id,
                derived_from=[],
                independent_group=gid,
                evidence_class="SUPPORTING",
                notes=["traceability_not_ownership"],
            )
        )

    for c in conflicts:
        gid = independent_group_for_span(f"conflict:{c}")
        eid = make_evidence_id(
            source_type="DESIGN_DIRECT",
            facet="conflict",
            concept=str(c),
            independent_group=gid,
            stage="B5",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=str(c),
                facet="conflict",
                source_type="DESIGN_DIRECT",
                source_span=str(c),
                document="B5",
                candidate_id=design_id or None,
                derived_from=[],
                independent_group=gid,
                evidence_class="CONFLICTING",
            )
        )

    for concept in matched_responsibilities:
        if concept.lower() in root_by_concept:
            continue
        span = find_span_containing(cr_text, concept)
        gid = independent_group_for_span(span)
        eid = make_evidence_id(
            source_type="CR_DIRECT",
            facet="responsibility",
            concept=concept,
            independent_group=gid,
            stage="B5",
        )
        items.append(
            EvidenceItem(
                evidence_id=eid,
                concept=concept,
                facet="responsibility",
                source_type="CR_DIRECT",
                source_span=span,
                document="CR",
                candidate_id=requirement_id,
                derived_from=[],
                independent_group=gid,
                evidence_class=_class_for_concept(concept),
            )
        )

    summary = summarize_evidence_items(items)
    return ProvenanceBundle(
        requirement_id=requirement_id,
        design_id=design_id,
        evidence_items=items,
        summary=summary,
    )


def empty_provenance_summary() -> dict[str, Any]:
    return {
        "direct_independent_count": 0,
        "supporting_independent_count": 0,
        "generic_count": 0,
        "derived_prior_count": 0,
        "conflicting_count": 0,
        "unique_independent_groups": [],
        "unique_independent_group_count": 0,
        "evidence_lineage_summary": [],
        "note": "Shadow candidate comparison does not select a new owner.",
    }
