# -*- coding: utf-8 -*-
"""PR-21: Deterministic rule matcher (0.0–1.0)."""

from __future__ import annotations

from typing import Any

from document_ai.semantic_locator.schema import SemanticLocatorInput, TemplateNodeCandidate
from document_ai.semantic_locator.text_normalization import normalize_path, normalize_text, tokenize
from document_ai.semantic_locator.thresholds import DEFAULT_THRESHOLDS


def _round(x: float) -> float:
    return round(float(x), DEFAULT_THRESHOLDS.round_digits)


def compute_rule_score(
    inp: SemanticLocatorInput,
    node: TemplateNodeCandidate,
) -> tuple[float, list[str], dict[str, Any]]:
    """Return (rule_score, reason_codes, rule_components)."""
    hints = node.locator_hints or {}
    hint_path = list(hints.get("heading_path") or [])
    hint_label = str(hints.get("field_label") or node.display_name or "")
    hint_exact = hints.get("exact_text")
    hint_section = hints.get("section_id") or node.section_id

    cand_path = list(inp.heading_path or [])
    cand_heading = inp.heading_text or inp.section_name or ""
    cand_label = inp.field_label or ""
    cand_exact = inp.exact_text or inp.candidate_text or ""

    n_cand_path = normalize_path(cand_path)
    n_hint_path = normalize_path(hint_path)
    n_heading = normalize_text(cand_heading)
    n_hint_last = normalize_text(hint_path[-1]) if hint_path else ""
    n_label_c = normalize_text(cand_label)
    n_label_h = normalize_text(hint_label)
    n_exact_c = normalize_text(cand_exact)
    n_exact_h = normalize_text(hint_exact) if hint_exact else ""
    n_section_c = normalize_text(inp.metadata.get("section_id") or "")
    n_section_h = normalize_text(str(hint_section or ""))

    components: dict[str, float] = {
        "exact_text": 0.0,
        "heading_path_exact": 0.0,
        "heading_path_partial": 0.0,
        "heading_text": 0.0,
        "field_label": 0.0,
        "section_id": 0.0,
        "normalized_string": 0.0,
        "parent_context": 0.0,
    }
    reasons: list[str] = []

    # 1. exact_text
    if n_exact_c and n_exact_h and n_exact_c == n_exact_h:
        components["exact_text"] = 1.0
        reasons.append("EXACT_TEXT_MATCH")
    elif n_exact_c and n_exact_h and (
        n_exact_c in n_exact_h or n_exact_h in n_exact_c
    ):
        components["exact_text"] = 0.6

    # 2–3. heading_path
    if n_cand_path and n_hint_path:
        if n_cand_path == n_hint_path:
            components["heading_path_exact"] = 1.0
            reasons.append("HEADING_PATH_MATCH")
        else:
            # longest common suffix / overlap ratio
            overlap = len(set(n_cand_path) & set(n_hint_path))
            denom = max(len(set(n_cand_path) | set(n_hint_path)), 1)
            partial = overlap / denom
            # suffix bonus
            m = min(len(n_cand_path), len(n_hint_path))
            suffix = 0
            for i in range(1, m + 1):
                if n_cand_path[-i] == n_hint_path[-i]:
                    suffix += 1
                else:
                    break
            suffix_score = suffix / max(len(n_hint_path), 1)
            components["heading_path_partial"] = _round(max(partial, suffix_score))
            if components["heading_path_partial"] >= 0.5:
                reasons.append("HEADING_PATH_MATCH")

    # 4. heading_text
    if n_heading:
        targets = [n_hint_last, normalize_text(node.display_name), n_label_h]
        if any(n_heading == t for t in targets if t):
            components["heading_text"] = 1.0
            reasons.append("HEADING_TEXT_MATCH")
        elif any(n_heading in t or t in n_heading for t in targets if t):
            components["heading_text"] = 0.55
            reasons.append("HEADING_TEXT_MATCH")

    # 5. field_label
    if n_label_c and n_label_h and n_label_c == n_label_h:
        components["field_label"] = 1.0
        reasons.append("FIELD_LABEL_MATCH")
    elif n_label_c and n_label_h and (
        n_label_c in n_label_h or n_label_h in n_label_c
    ):
        components["field_label"] = 0.6
        reasons.append("FIELD_LABEL_MATCH")
    elif n_heading and n_label_h and n_heading == n_label_h:
        components["field_label"] = 0.85
        reasons.append("FIELD_LABEL_MATCH")

    # 6. section_id
    if n_section_c and n_section_h and n_section_c == n_section_h:
        components["section_id"] = 1.0
        reasons.append("SECTION_MATCH")
    elif normalize_text(node.section_id) and n_heading:
        # weak: heading matches section_id slug words
        sec_toks = set(tokenize(node.section_id.replace("_", " ")))
        head_toks = set(tokenize(cand_heading))
        if sec_toks and sec_toks <= head_toks:
            components["section_id"] = 0.5
            reasons.append("SECTION_MATCH")

    # 7. normalized string against field_id / display
    blob_c = normalize_text(
        " ".join(
            [
                " ".join(cand_path),
                cand_heading,
                cand_label or "",
                cand_exact or "",
            ]
        )
    )
    blob_n = normalize_text(
        " ".join(
            [
                " ".join(hint_path),
                hint_label,
                node.field_id.replace("_", " "),
                node.section_id.replace("_", " "),
                node.display_name,
            ]
        )
    )
    if blob_c and blob_n:
        if blob_c == blob_n:
            components["normalized_string"] = 1.0
        else:
            ct = set(tokenize(blob_c))
            nt = set(tokenize(blob_n))
            if ct and nt:
                components["normalized_string"] = _round(
                    len(ct & nt) / max(len(ct | nt), 1)
                )
                if components["normalized_string"] >= 0.4:
                    reasons.append("PARTIAL_TOKEN_MATCH")

    # 8. parent context: shared ancestor in path
    if len(n_cand_path) >= 2 and len(n_hint_path) >= 2:
        if n_cand_path[0] == n_hint_path[0]:
            components["parent_context"] = 0.7
        if n_cand_path[:-1] == n_hint_path[:-1]:
            components["parent_context"] = 1.0

    # Weighted fusion of components (deterministic)
    weights = {
        "exact_text": 0.28,
        "heading_path_exact": 0.24,
        "heading_path_partial": 0.12,
        "heading_text": 0.14,
        "field_label": 0.10,
        "section_id": 0.04,
        "normalized_string": 0.04,
        "parent_context": 0.04,
    }
    score = sum(components[k] * weights[k] for k in weights)
    # Cap at 1.0; boost if exact path + label
    if components["heading_path_exact"] >= 1.0 and (
        components["field_label"] >= 0.85 or components["heading_text"] >= 1.0
    ):
        score = max(score, 0.92)
    if components["heading_path_exact"] >= 1.0:
        score = max(score, 0.88)
    score = _round(min(max(score, 0.0), 1.0))

    # Deduplicate reasons preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    return score, uniq, components
