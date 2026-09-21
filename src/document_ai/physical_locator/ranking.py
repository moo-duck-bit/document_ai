# -*- coding: utf-8 -*-
"""PR-23: Score and rank physical location candidates."""

from __future__ import annotations

from document_ai.physical_locator.schema import (
    PhysicalLocationCandidate,
    PhysicalLocatorInput,
)
from document_ai.semantic_locator.text_normalization import normalize_path, normalize_text, tokenize

RESOLVED_MIN = 0.85
REVIEW_MIN = 0.60
MARGIN_MIN = 0.08
ROUND = 4

# Preferred location type by field_id heuristics
_FIELD_TYPE_PREF = {
    "data_sources": ("PARAGRAPH", "TABLE", "TABLE_CELL"),
    "key_findings": ("LIST", "PARAGRAPH"),
    "recommendations": ("LIST", "PARAGRAPH"),
    "tables": ("TABLE", "TABLE_CELL"),
    "entries": ("LIST", "PARAGRAPH"),
    "items": ("LIST", "TABLE"),
    "body": ("PARAGRAPH",),
    "title": ("HEADING", "SECTION"),
    "schedule": ("PARAGRAPH", "LIST"),
    "approach": ("PARAGRAPH",),
    "phases": ("LIST",),
    "deliverables": ("LIST",),
}


def _round(x: float) -> float:
    return round(float(x), ROUND)


def score_candidate(
    cand: PhysicalLocationCandidate,
    inp: PhysicalLocatorInput,
) -> PhysicalLocationCandidate:
    hint_path = normalize_path(inp.heading_path_hint)
    cand_path = normalize_path(cand.heading_path)
    field_id = normalize_text((inp.field_id or "").replace("_", " "))
    label = normalize_text(inp.field_label_hint or "")
    section_hint = normalize_text(inp.section_id or "")

    components = {
        "heading_match": 0.0,
        "parent_match": 0.0,
        "section_match": 0.0,
        "field_match": 0.0,
        "block_type": 0.0,
        "document_order": 0.0,
    }
    reasons: list[str] = []

    # Heading path
    if hint_path and cand_path:
        if hint_path == cand_path or (
            len(cand_path) >= len(hint_path)
            and cand_path[-len(hint_path) :] == hint_path
        ):
            components["heading_match"] = 1.0
            reasons.append("HEADING_PATH_EXACT")
        else:
            overlap = len(set(hint_path) & set(cand_path)) / max(
                len(set(hint_path) | set(cand_path)), 1
            )
            suffix = 0
            m = min(len(hint_path), len(cand_path))
            for i in range(1, m + 1):
                if hint_path[-i] == cand_path[-i]:
                    suffix += 1
                else:
                    break
            components["heading_match"] = _round(
                max(overlap, suffix / max(len(hint_path), 1))
            )
            if components["heading_match"] >= 0.5:
                reasons.append("HEADING_PATH_PARTIAL")

    # Parent (shared ancestors)
    if len(hint_path) >= 1 and len(cand_path) >= 1:
        # compare last hint parent vs cand ancestors
        if hint_path[0] in cand_path or (
            len(hint_path) >= 2 and hint_path[-2] in cand_path
        ):
            components["parent_match"] = 0.7
            reasons.append("PARENT_HEADING_MATCH")
        if len(hint_path) >= 2 and len(cand_path) >= 2:
            if hint_path[:-1] == cand_path[-(len(hint_path) - 1) - 0 : -1] or (
                cand_path[-(len(hint_path)) : -1] == hint_path[:-1]
            ):
                components["parent_match"] = 1.0

    # Section id / heading text vs section_id slug
    sec_norm = normalize_text((cand.section_id or "").replace("_", " "))
    heading_last = normalize_text(cand.heading_path[-1]) if cand.heading_path else ""
    if section_hint and (section_hint == sec_norm or section_hint == heading_last):
        components["section_match"] = 1.0
        reasons.append("SECTION_MATCH")
    elif section_hint and section_hint in sec_norm:
        components["section_match"] = 0.6
        reasons.append("SECTION_MATCH")

    # Field match against text/headers/items
    blob_parts = [
        str((cand.evidence or {}).get("text") or ""),
        str((cand.evidence or {}).get("heading_text") or ""),
        " ".join((cand.evidence or {}).get("headers") or []),
        " ".join((cand.evidence or {}).get("items") or []),
        str((cand.evidence or {}).get("cell_text") or ""),
    ]
    blob = normalize_text(" ".join(blob_parts))
    field_toks = set(tokenize(field_id)) | set(tokenize(label))
    blob_toks = set(tokenize(blob))
    if field_toks and blob_toks:
        components["field_match"] = _round(
            len(field_toks & blob_toks) / max(len(field_toks), 1)
        )
        if components["field_match"] >= 0.5:
            reasons.append("FIELD_TEXT_MATCH")
    if label and heading_last and label == heading_last:
        components["field_match"] = max(components["field_match"], 1.0)
        reasons.append("FIELD_LABEL_HEADING_MATCH")

    # Block type preference
    prefs = _FIELD_TYPE_PREF.get(inp.field_id or "", ())
    preferred = inp.preferred_location_type
    if preferred and cand.location_type == preferred:
        components["block_type"] = 1.0
        reasons.append("BLOCK_TYPE_PREFERRED")
    elif prefs:
        if cand.location_type == prefs[0]:
            components["block_type"] = 1.0
            reasons.append("BLOCK_TYPE_PREFERRED")
        elif cand.location_type in prefs:
            components["block_type"] = 0.7
            reasons.append("BLOCK_TYPE_COMPATIBLE")
        else:
            components["block_type"] = 0.2
    else:
        components["block_type"] = 0.4

    # Document order — slight preference for earlier matching content
    order = float((cand.evidence or {}).get("document_order") or 0)
    components["document_order"] = _round(max(0.0, 1.0 - min(order, 5000) / 5000.0) * 0.5)

    weights = {
        "heading_match": 0.34,
        "parent_match": 0.12,
        "section_match": 0.12,
        "field_match": 0.16,
        "block_type": 0.18,
        "document_order": 0.08,
    }
    score = sum(components[k] * weights[k] for k in weights)
    if components["heading_match"] >= 1.0 and components["block_type"] >= 0.7:
        score = max(score, 0.88)
    if components["heading_match"] >= 1.0 and components["field_match"] >= 0.5:
        score = max(score, 0.86)
    # Strong preference boost so preferred type wins with margin over siblings
    if preferred and cand.location_type == preferred and components["heading_match"] >= 0.8:
        score = min(score + 0.10, 1.0)
    elif prefs and cand.location_type == prefs[0] and components["heading_match"] >= 0.8:
        score = min(score + 0.08, 1.0)
    if preferred and cand.location_type != preferred:
        score = max(score - 0.06, 0.0)
    elif prefs and cand.location_type not in prefs:
        score = max(score - 0.04, 0.0)

    cand.location_score = _round(min(max(score, 0.0), 1.0))
    cand.score_components = {k: _round(v) for k, v in components.items()}
    # dedupe reasons
    uniq: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    cand.reason_codes = uniq
    return cand


def rank_candidates(
    candidates: list[PhysicalLocationCandidate],
    inp: PhysicalLocatorInput,
) -> list[PhysicalLocationCandidate]:
    scored = [score_candidate(c, inp) for c in candidates]
    preferred = inp.preferred_location_type or ""
    scored.sort(
        key=lambda c: (
            -c.location_score,
            0 if c.location_type == preferred else 1,
            c.location_type,
            c.physical_candidate_id,
        )
    )
    for i, c in enumerate(scored, start=1):
        c.rank = i
    return scored


def decide_location_status(
    ranked: list[PhysicalLocationCandidate],
    *,
    broken: bool = False,
    preferred_location_type: str | None = None,
) -> tuple[str, list[str], float | None, float | None, float | None]:
    if broken:
        return "INVALID", ["BROKEN_REFERENCE"], None, None, None
    if not ranked:
        return "UNRESOLVED", ["NO_PHYSICAL_CANDIDATES"], None, None, None
    top1 = ranked[0].location_score
    top2 = ranked[1].location_score if len(ranked) > 1 else None
    margin = _round(top1 - top2) if top2 is not None else None
    extra: list[str] = list(ranked[0].reason_codes)

    same_type_tie = False
    if len(ranked) > 1 and ranked[0].location_type == ranked[1].location_type:
        if margin is not None and margin < MARGIN_MIN:
            same_type_tie = True

    clear_preferred = bool(
        preferred_location_type
        and ranked[0].location_type == preferred_location_type
        and (
            margin is None
            or margin >= MARGIN_MIN
            or (
                len(ranked) > 1
                and ranked[1].location_type != preferred_location_type
            )
        )
    )

    if same_type_tie and top1 >= REVIEW_MIN:
        extra.append("AMBIGUOUS_TOP_LOCATIONS")
        return "REVIEW", extra, top1, top2, margin

    if (
        margin is not None
        and margin < MARGIN_MIN
        and top1 >= REVIEW_MIN
        and not clear_preferred
    ):
        extra.append("AMBIGUOUS_TOP_LOCATIONS")
        return "REVIEW", extra, top1, top2, margin

    if top1 >= RESOLVED_MIN:
        extra.append("PHYSICAL_LOCATION_RESOLVED")
        return "RESOLVED", extra, top1, top2, margin
    if top1 >= REVIEW_MIN:
        extra.append("PHYSICAL_LOCATION_REVIEW")
        return "REVIEW", extra, top1, top2, margin
    extra.append("PHYSICAL_LOCATION_UNRESOLVED")
    return "UNRESOLVED", extra, top1, top2, margin
