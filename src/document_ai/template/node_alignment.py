# -*- coding: utf-8 -*-
"""Template ↔ document structural node alignment (evaluation vs patch separated)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from document_ai.template.concept_normalization import (
    SCHEDULE,
    normalize_concepts,
    tokenize,
)


@dataclass
class NodeAlignment:
    alignment_id: str
    document_id: str
    template_node_id: str
    document_node_id: str
    alignment_type: str
    section_id: str | None = None
    source_locator: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    equivalent_for_evaluation: bool = False
    equivalent_for_patch: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StructuralEquivalenceGroup:
    group_id: str
    document_id: str
    template_node_ids: list[str] = field(default_factory=list)
    document_node_ids: list[str] = field(default_factory=list)
    section_id: str | None = None
    concepts: list[str] = field(default_factory=list)
    evaluation_equivalent: bool = True
    patch_equivalent: bool = False
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_SECTION_RE = re.compile(r"^([a-z0-9_]+(?:_v\d+)?)\.([a-z0-9_]+)$", re.IGNORECASE)


def _section_id_from_template(node_id: str) -> str | None:
    m = _SECTION_RE.match(node_id or "")
    return m.group(2) if m else None


def build_node_alignments(
    *,
    document_id: str,
    template_review_items: list[dict[str, Any]],
    document_review_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Align template section nodes with heading/paragraph/table document nodes
    when concepts/section ids match. No case-id hardcoding.
    """
    alignments: list[NodeAlignment] = []
    groups: dict[str, StructuralEquivalenceGroup] = {}
    aid = 0

    template_nodes = [
        t
        for t in template_review_items
        if str(t.get("node_id") or "").count(".") >= 1
        and not str(t.get("node_id") or "").startswith(("heading_", "paragraph_", "table_"))
    ]
    doc_nodes = [
        d
        for d in document_review_items
        if str(d.get("node_id") or "").startswith(("heading_", "paragraph_", "table_"))
    ]

    for tmpl in template_nodes:
        tid = str(tmpl.get("node_id") or "")
        sec = _section_id_from_template(tid) or str(tmpl.get("display_name") or "")
        tmpl_blob = " ".join(
            [
                tid,
                str(tmpl.get("display_name") or ""),
                sec,
            ]
        )
        tmpl_concepts = normalize_concepts(tmpl_blob)
        tmpl_toks = tokenize(tmpl_blob)

        for doc in doc_nodes:
            if str(doc.get("document_id") or document_id) != document_id and doc.get("document_id"):
                # wrong document
                if str(doc.get("document_id")) != str(document_id):
                    continue
            did = str(doc.get("node_id") or "")
            doc_meta = doc.get("metadata") or {}
            doc_concepts_list = list(
                doc.get("canonical_concepts")
                or doc_meta.get("canonical_concepts")
                or []
            )
            doc_blob = " ".join(
                [
                    did,
                    str(doc.get("display_name") or ""),
                    str(doc.get("section_context") or doc_meta.get("section_context") or ""),
                    " ".join(str(x) for x in doc_concepts_list),
                ]
            )
            doc_concepts = normalize_concepts(doc_blob) | set(doc_concepts_list)
            doc_toks = tokenize(doc_blob)

            concept_hit = bool(tmpl_concepts & doc_concepts)
            token_hit = bool(tmpl_toks & doc_toks) and len(tmpl_toks & doc_toks) >= 1
            schedule_bridge = SCHEDULE in tmpl_concepts and (
                SCHEDULE in doc_concepts or "일정" in doc_blob or "schedule" in doc_blob.lower()
            )
            section_name_hit = bool(sec) and (
                sec.lower() in doc_blob.lower()
                or str(tmpl.get("display_name") or "").lower() in doc_blob.lower()
            )

            if not (concept_hit or schedule_bridge or section_name_hit or token_hit):
                continue

            if did.startswith("heading_"):
                atype = "HEADING_TO_SECTION"
            elif did.startswith("paragraph_"):
                atype = "PARAGRAPH_TO_FIELD"
            elif did.startswith("table_"):
                atype = "TABLE_TO_SECTION"
            else:
                atype = "REVIEW_CONTEXT"

            conf = 0.55
            reasons = ["concept_or_token_bridge"]
            if schedule_bridge:
                conf = 0.9
                reasons.append("schedule_family_bridge")
            if section_name_hit:
                conf = max(conf, 0.8)
                reasons.append("section_name_hit")
            if concept_hit:
                conf = max(conf, 0.75)
                reasons.append("shared_canonical_concept")

            # Patch equivalence only when physical locator resolved
            locator = doc.get("source_locator") or {}
            patch_eq = bool(locator) and atype in {"TABLE_TO_SECTION", "PARAGRAPH_TO_FIELD"}
            # Headings are evaluation-equivalent but not patch targets unless locator present
            eval_eq = conf >= 0.55

            aid += 1
            al = NodeAlignment(
                alignment_id=f"NA-{aid:04d}",
                document_id=document_id,
                template_node_id=tid,
                document_node_id=did,
                alignment_type=atype,
                section_id=sec,
                source_locator=dict(locator),
                confidence=round(conf, 4),
                reason_codes=sorted(set(reasons)),
                equivalent_for_evaluation=eval_eq,
                equivalent_for_patch=patch_eq,
            )
            alignments.append(al)

            gid = f"{document_id}:{sec or tid}"
            g = groups.get(gid)
            if g is None:
                g = StructuralEquivalenceGroup(
                    group_id=gid,
                    document_id=document_id,
                    template_node_ids=[tid],
                    document_node_ids=[],
                    section_id=sec,
                    concepts=sorted(tmpl_concepts | doc_concepts),
                    evaluation_equivalent=True,
                    patch_equivalent=False,
                    reason_codes=["structural_equivalence"],
                )
                groups[gid] = g
            if tid not in g.template_node_ids:
                g.template_node_ids.append(tid)
            if did not in g.document_node_ids:
                g.document_node_ids.append(did)
            if al.equivalent_for_patch:
                g.patch_equivalent = False  # group patch still false unless all resolved
            g.concepts = sorted(set(g.concepts) | tmpl_concepts | doc_concepts)

    # Validation
    issues: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    for a in alignments:
        key = (a.template_node_id, a.document_node_id)
        if key in seen_pairs:
            issues.append(f"duplicate_alignment:{key}")
        seen_pairs.add(key)
        if a.document_id != document_id:
            issues.append(f"document_mismatch:{a.alignment_id}")
        if a.equivalent_for_patch and not a.source_locator:
            issues.append(f"patch_eq_without_locator:{a.alignment_id}")
            a.equivalent_for_patch = False
        if a.equivalent_for_evaluation and a.confidence < 0.4:
            issues.append(f"weak_eval_equivalence:{a.alignment_id}")

    validation = {
        "ok": not issues,
        "issues": issues,
        "alignment_requires_evidence": all(a.reason_codes for a in alignments),
        "evaluation_patch_equivalence_separated": all(
            (not a.equivalent_for_patch) or a.equivalent_for_evaluation for a in alignments
        )
        or not alignments,
        "n_alignments": len(alignments),
        "n_groups": len(groups),
    }

    return {
        "alignments": [a.to_dict() for a in alignments],
        "structural_equivalence_groups": [g.to_dict() for g in groups.values()],
        "validation": validation,
    }


def expand_acceptable_groups_with_alignments(
    groups: list[list[str]],
    alignments: list[dict[str, Any]],
    equivalence_groups: list[dict[str, Any]] | None = None,
) -> list[list[str]]:
    """Expand evaluation groups with evaluation-equivalent document nodes."""
    expanded: list[list[str]] = []
    for g in groups:
        s = set(g)
        for a in alignments:
            if not a.get("equivalent_for_evaluation"):
                continue
            tid = a.get("template_node_id")
            did = a.get("document_node_id")
            if tid in s and did:
                s.add(str(did))
            if did in s and tid:
                s.add(str(tid))
        for eg in equivalence_groups or []:
            if not eg.get("evaluation_equivalent"):
                continue
            members = set(eg.get("template_node_ids") or []) | set(eg.get("document_node_ids") or [])
            if s & members:
                s |= members
        expanded.append(sorted(s))
    return expanded


def boost_template_alignment_scores(
    review_items: list[dict[str, Any]],
    alignments: list[dict[str, Any]],
) -> None:
    """Raise template section scores when validated document alignments exist (in-place)."""
    aligned_templates = {
        a["template_node_id"]
        for a in alignments
        if a.get("equivalent_for_evaluation") and float(a.get("confidence") or 0) >= 0.75
    }
    for item in review_items:
        nid = item.get("node_id")
        if nid not in aligned_templates:
            continue
        meta = item.setdefault("metadata", {})
        # Boost above typical heading scores (~1.0) without becoming PATCH
        base = float(item.get("overlap") or meta.get("overlap") or 0.7)
        boosted = max(base, 1.25)
        item["overlap"] = boosted
        meta["overlap"] = boosted
        meta["final_score"] = boosted
        meta["template_alignment"] = True
        rc = list(item.get("reason_codes") or [])
        if "template_document_aligned" not in rc:
            rc.append("template_document_aligned")
        item["reason_codes"] = rc
