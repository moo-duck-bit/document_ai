# -*- coding: utf-8 -*-
"""Deterministic REQUIRED/AMBIGUOUS/OPTIONAL/NOT_APPLICABLE labeling policy.

Inputs are limited to: case metadata (change_request, tags) and a
document-structure ``inventory`` (see ``document_inventory.py``). No
prediction artifact is read here.

Rules (see plan):

- ``UPDATE``/``REVIEW`` prefers an existing PHYSICAL node when the target
  concept's section already exists in the document.
- ``ADD`` may resolve to an OPTIONAL virtual/template target when the section
  does not exist yet.
- ``ADD`` onto an *existing* section (e.g. "위험 관리 항목 추가" when a 위험 관리
  section is already present) is AMBIGUOUS: augment the existing section vs.
  treat as a new addition are both plausible.
- A concept matched by more than one section (e.g. two schedule headings) is
  AMBIGUOUS across the matching sections.
- TABLE-intent change requests must resolve to a TABLE physical node when one
  exists in the matching section; a TABLE intent resolved to a bare paragraph
  is flagged by ``validation.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from document_ai.domain_packs.business_proposal.concepts import (
    BUDGET,
    COST,
    DELIVERABLE,
    EXPECTED_EFFECT,
    KPI,
    MARKET,
    ORGANIZATION,
    RISK_MANAGEMENT,
    SCHEDULE,
    normalize_proposal_concepts,
    template_node_for_concepts,
)
from document_ai.domain_packs.business_proposal.query_intent import (
    parse_business_proposal_query_intent,
)
from document_ai.evaluation.business_proposal_gold.document_inventory import (
    find_matching_sections,
    nodes_by_id,
)
from document_ai.evaluation.business_proposal_gold.schema import BusinessProposalGoldRow
from document_ai.template.concept_normalization import normalize_concepts

CONCEPT_PRIORITY: list[str] = [
    SCHEDULE,
    BUDGET,
    KPI,
    RISK_MANAGEMENT,
    ORGANIZATION,
    EXPECTED_EFFECT,
    DELIVERABLE,
    COST,
    MARKET,
]

CONCEPT_TAG_MAP: dict[str, str] = {
    "schedule": SCHEDULE,
    "sched": SCHEDULE,
    "sched_table": SCHEDULE,
    "schedule_section": SCHEDULE,
    "budget": BUDGET,
    "labor_cell": COST,
    "risk": RISK_MANAGEMENT,
    "risk_amb": RISK_MANAGEMENT,
    "org": ORGANIZATION,
    "organization": ORGANIZATION,
    "org_table": ORGANIZATION,
    "effect": EXPECTED_EFFECT,
    "effect_para": EXPECTED_EFFECT,
    "outcome": EXPECTED_EFFECT,
    "kpi": KPI,
    "deliverable": DELIVERABLE,
    "market_add": MARKET,
}

# Tags that force a single (already-uniquely-matched) section into AMBIGUOUS
# scope regardless of the detected operation (structural / scope ambiguity,
# not an artifact of prediction disagreement).
FORCE_AMBIGUOUS_TAGS = frozenset({"schedule_section", "risk_amb"})
# Tags whose CR intentionally has no addressable physical/template target.
FORCE_OPTIONAL_TAGS = frozenset({"market_add", "style_overall"})
NOT_APPLICABLE_TAGS = frozenset({"no_impact"})

_BOILERPLATE_SCORE = 70
_CONTENT_SCORE = 90
_HEADING_SCORE = 80
_TABLE_SCORE = 100
_UNRELATED_SCORE = 0


def resolve_target_concept(change_request: str, tags: list[str] | None = None) -> str | None:
    tag_set = {str(t).lower() for t in (tags or [])}
    for tag in tag_set:
        if tag in CONCEPT_TAG_MAP:
            return CONCEPT_TAG_MAP[tag]
    concepts = normalize_proposal_concepts(change_request or "") | normalize_concepts(change_request or "")
    for c in CONCEPT_PRIORITY:
        if c in concepts:
            return c
    return None


def _score_member(node: dict[str, Any], *, target_concept: str) -> int:
    ntype = node.get("node_type")
    concepts = set(node.get("concepts") or [])
    if ntype == "TABLE":
        return _TABLE_SCORE if target_concept in concepts else -1
    if ntype == "HEADING":
        return _HEADING_SCORE if target_concept in concepts else -1
    # PARAGRAPH
    own_match = target_concept in concepts
    if node.get("is_boilerplate"):
        return _BOILERPLATE_SCORE if own_match else _UNRELATED_SCORE
    if own_match or node.get("has_digit"):
        return _CONTENT_SCORE
    return _UNRELATED_SCORE


def select_section_representative(
    section: dict[str, Any],
    node_index: dict[str, dict[str, Any]],
    *,
    target_concept: str,
    prefer_table: bool = False,
    prefer_paragraph: bool = False,
) -> tuple[str | None, int]:
    """Return (node_id, score) of the best physical representative in a section."""
    members = [node_index[nid] for nid in section.get("member_node_ids") or [] if nid in node_index]
    scored = [(n["node_id"], _score_member(n, target_concept=target_concept), n["node_type"]) for n in members]
    scored = [(nid, sc, nt) for nid, sc, nt in scored if sc > 0]
    if not scored:
        return None, 0
    if prefer_table:
        tables = [(nid, sc) for nid, sc, nt in scored if nt == "TABLE"]
        if tables:
            tables.sort(key=lambda x: (-x[1], x[0]))
            return tables[0]
    if prefer_paragraph:
        paras = [(nid, sc) for nid, sc, nt in scored if nt == "PARAGRAPH"]
        if paras:
            paras.sort(key=lambda x: (-x[1], x[0]))
            return paras[0]
    scored.sort(key=lambda x: (-x[1], x[0]))
    nid, sc, _nt = scored[0]
    return nid, sc


def _matching_member_ids(section: dict[str, Any], node_index: dict[str, dict[str, Any]], target_concept: str) -> list[str]:
    out = []
    for nid in section.get("member_node_ids") or []:
        n = node_index.get(nid) or {}
        if _score_member(n, target_concept=target_concept) > 0:
            out.append(nid)
    return out


def classify_case(
    *,
    case_id: str,
    document_id: str,
    change_request: str,
    tags: list[str] | None,
    inventory: dict[str, Any],
) -> BusinessProposalGoldRow:
    """Deterministically derive one gold row from structure + change_request."""
    tag_set = {str(t).lower() for t in (tags or [])}
    now = datetime.now(timezone.utc).isoformat()
    intent = parse_business_proposal_query_intent(change_request or "")
    node_index = nodes_by_id(inventory)

    def _row(**kw: Any) -> BusinessProposalGoldRow:
        base = dict(
            case_id=case_id,
            document_id=document_id,
            label_source="document_structure_and_change_request",
            labeled_by="pass1_structure_policy",
            labeled_at=now,
            label_confidence=0.85,
        )
        base.update(kw)
        return BusinessProposalGoldRow(**base)

    if tag_set & NOT_APPLICABLE_TAGS:
        return _row(
            node_evaluation_mode="NOT_APPLICABLE",
            primary_reference=None,
            expected_operation=intent.requested_operation,
            expected_location_type=None,
            label_rationale=(
                f"tag(s) {sorted(tag_set & NOT_APPLICABLE_TAGS)} indicate the change request has no "
                "structural counterpart in this document (off-topic / cover-only edit)."
            ),
            label_confidence=0.95,
        )

    target_concept = resolve_target_concept(change_request, tags)

    if target_concept is None or (tag_set & FORCE_OPTIONAL_TAGS):
        return _row(
            node_evaluation_mode="OPTIONAL",
            primary_reference={
                "reference_type": "VIRTUAL",
                "stable_node_id": None,
                "template_node_id": None,
                "document_node_id": None,
                "stable_locator": {},
                "canonical_concepts": [],
            },
            expected_node_type=None,
            expected_structural_role="VIRTUAL_PROPOSAL_TARGET",
            expected_template_node_id=None,
            expected_physical_node_type="NONE",
            expected_location_type="DOCUMENT_LEVEL",
            expected_operation=intent.requested_operation,
            label_rationale=(
                "Change request does not map to a canonical Business Proposal concept/template "
                "section (document-level or out-of-schema request); no gold node can be pinned "
                "without risking hallucinated structure."
            ),
            label_confidence=0.7,
        )

    template_node_id = template_node_for_concepts({target_concept}) or intent.preferred_template_node_id
    matching_sections = find_matching_sections(inventory, target_concept)

    prefer_table = bool(intent.table_intent)
    prefer_paragraph = bool(intent.paragraph_intent) and not prefer_table

    if not matching_sections:
        # No physical section exists yet for this concept.
        if intent.add_intent:
            mode = "OPTIONAL"
            rationale = (
                f"CR requests ADD of a new '{target_concept}' section; the document has no matching "
                "physical section yet, so only the (virtual) template target can be offered for review."
            )
        else:
            mode = "OPTIONAL"
            rationale = (
                f"CR references concept '{target_concept}' but no matching physical section exists in "
                "the document; treated as a missing-section OPTIONAL review target rather than invented gold."
            )
        return _row(
            node_evaluation_mode=mode,
            primary_reference={
                "reference_type": "TEMPLATE" if template_node_id else "VIRTUAL",
                "stable_node_id": None,
                "template_node_id": template_node_id,
                "document_node_id": None,
                "stable_locator": {},
                "canonical_concepts": [target_concept],
            },
            acceptable_references=(
                [{"reference_type": "TEMPLATE", "template_node_id": template_node_id}] if template_node_id else []
            ),
            expected_node_type="TEMPLATE" if template_node_id else "VIRTUAL",
            expected_structural_role="VIRTUAL_PROPOSAL_TARGET",
            expected_template_node_id=template_node_id,
            expected_physical_node_type="NONE",
            expected_location_type="VIRTUAL",
            expected_operation=intent.requested_operation,
            label_rationale=rationale,
            label_confidence=0.6,
        )

    if len(matching_sections) > 1:
        # Multi-section ambiguity: which section is the CR actually targeting?
        group = [s["heading_node_id"] for s in matching_sections if s.get("heading_node_id")]
        if template_node_id:
            group = group + [template_node_id]
        physical_type = "HEADING"
        rationale = (
            f"'{target_concept}' matches {len(matching_sections)} distinct sections "
            f"({', '.join(str(s.get('heading_node_id')) for s in matching_sections)}); the change "
            "request does not disambiguate which one is intended, so this is AMBIGUOUS across "
            "the section headings plus the template section."
        )
        return _row(
            node_evaluation_mode="AMBIGUOUS",
            primary_reference={
                "reference_type": "TEMPLATE" if template_node_id else "PHYSICAL",
                "stable_node_id": None,
                "template_node_id": template_node_id,
                "document_node_id": group[0] if group else None,
                "stable_locator": {},
                "canonical_concepts": [target_concept],
            },
            acceptable_references=[{"reference_type": "PHYSICAL", "document_node_id": g} for g in group],
            acceptable_groups=[group],
            expected_node_type="HEADING",
            expected_structural_role="DOCUMENT_HEADING",
            expected_template_node_id=template_node_id,
            expected_physical_node_type=physical_type,
            expected_location_type="SECTION",
            expected_operation=intent.requested_operation,
            label_rationale=rationale,
            label_confidence=0.75,
        )

    # Exactly one matching section.
    section = matching_sections[0]
    rep_node_id, _score = select_section_representative(
        section,
        node_index,
        target_concept=target_concept,
        prefer_table=prefer_table,
        prefer_paragraph=prefer_paragraph,
    )
    matching_members = _matching_member_ids(section, node_index, target_concept)
    physical_node = node_index.get(rep_node_id) if rep_node_id else None
    physical_node_type = physical_node.get("node_type") if physical_node else "NONE"

    add_but_exists = intent.add_intent
    force_ambiguous = bool(tag_set & FORCE_AMBIGUOUS_TAGS)

    if add_but_exists or force_ambiguous:
        group = list(matching_members)
        if template_node_id and template_node_id not in group:
            group = group + [template_node_id]
        reason = (
            "CR uses ADD phrasing but the target section already exists physically"
            if add_but_exists
            else "case tagged as scope-ambiguous (whole-section edit vs. single physical node)"
        )
        rationale = (
            f"{reason}: augmenting the existing '{target_concept}' section vs. treating this as a "
            f"fresh addition are both plausible, so this is AMBIGUOUS over {group}."
        )
        return _row(
            node_evaluation_mode="AMBIGUOUS",
            primary_reference={
                "reference_type": "TEMPLATE" if template_node_id else "PHYSICAL",
                "stable_node_id": None,
                "template_node_id": template_node_id,
                "document_node_id": rep_node_id,
                "stable_locator": {},
                "canonical_concepts": [target_concept],
            },
            acceptable_references=[{"reference_type": "PHYSICAL", "document_node_id": g} for g in group],
            acceptable_groups=[group],
            expected_node_type=physical_node_type,
            expected_structural_role=section.get("heading_text"),
            expected_template_node_id=template_node_id,
            expected_physical_node_type=physical_node_type or "NONE",
            expected_location_type="SECTION",
            expected_operation=intent.requested_operation,
            label_rationale=rationale,
            label_confidence=0.75,
        )

    # REQUIRED: unique section, unique physical representative, template as stable evaluation primary.
    acceptable_ids = [nid for nid in matching_members if nid != rep_node_id]
    group = list(matching_members)
    if template_node_id and template_node_id not in group:
        group = group + [template_node_id]
    rationale = (
        f"CR maps to concept '{target_concept}' with a unique matching physical node "
        f"({rep_node_id}, type={physical_node_type}) in section '{section.get('heading_text')}'. "
        "Stable ref > Template > Physical priority: template section is used as the projected "
        "evaluation primary for cross-run stability; the physical node is recorded as the preferred "
        "acceptable/UPDATE target."
    )
    return _row(
        node_evaluation_mode="REQUIRED",
        primary_reference={
            "reference_type": "TEMPLATE" if template_node_id else "PHYSICAL",
            "stable_node_id": None,
            "template_node_id": template_node_id,
            "document_node_id": rep_node_id,
            "stable_locator": {},
            "canonical_concepts": [target_concept],
        },
        acceptable_references=(
            [{"reference_type": "PHYSICAL", "document_node_id": rep_node_id}]
            + [{"reference_type": "PHYSICAL", "document_node_id": nid} for nid in acceptable_ids]
        ),
        acceptable_groups=[group],
        expected_node_type=physical_node_type,
        expected_structural_role=section.get("heading_text"),
        expected_template_node_id=template_node_id,
        expected_physical_node_type=physical_node_type or "NONE",
        expected_location_type="TABLE" if physical_node_type == "TABLE" else "SECTION",
        expected_operation=intent.requested_operation,
        label_rationale=rationale,
        label_confidence=0.9,
    )
