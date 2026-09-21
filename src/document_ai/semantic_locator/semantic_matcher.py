# -*- coding: utf-8 -*-
"""PR-21: Local deterministic semantic similarity (no LLM / remote / transformers)."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from document_ai.semantic_locator.schema import SemanticLocatorInput, TemplateNodeCandidate
from document_ai.semantic_locator.text_normalization import normalize_text, tokenize
from document_ai.semantic_locator.thresholds import DEFAULT_THRESHOLDS


def _round(x: float) -> float:
    return round(float(x), DEFAULT_THRESHOLDS.round_digits)


def _char_ngrams(text: str, n: int = 3) -> Counter[str]:
    s = normalize_text(text)
    if not s:
        return Counter()
    padded = f"  {s}  "
    return Counter(padded[i : i + n] for i in range(max(len(padded) - n + 1, 0)))


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _token_overlap(a: str, b: str) -> float:
    ta = set(tokenize(a))
    tb = set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _tfidf_cosine(a: str, b: str) -> float:
    """Tiny 2-document TF-IDF cosine (deterministic, local)."""
    docs = [tokenize(a), tokenize(b)]
    if not docs[0] or not docs[1]:
        return 0.0
    df: Counter[str] = Counter()
    for toks in docs:
        for t in set(toks):
            df[t] += 1
    n_docs = 2.0

    def vec(toks: list[str]) -> dict[str, float]:
        tf = Counter(toks)
        out: dict[str, float] = {}
        length = max(len(toks), 1)
        for t, c in tf.items():
            idf = math.log((n_docs + 1.0) / (df[t] + 1.0)) + 1.0
            out[t] = (c / length) * idf
        return out

    va = vec(docs[0])
    vb = vec(docs[1])
    keys = set(va) | set(vb)
    dot = sum(va.get(k, 0.0) * vb.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _candidate_blob(inp: SemanticLocatorInput) -> str:
    parts = [
        " ".join(inp.heading_path or []),
        inp.heading_text or "",
        inp.section_name or "",
        inp.field_label or "",
        inp.exact_text or "",
        inp.candidate_text or "",
    ]
    return " ".join(p for p in parts if p)


def _node_blob(node: TemplateNodeCandidate) -> str:
    hints = node.locator_hints or {}
    parts = [
        " ".join(hints.get("heading_path") or []),
        str(hints.get("field_label") or ""),
        str(hints.get("exact_text") or ""),
        node.display_name,
        node.field_id.replace("_", " "),
        node.section_id.replace("_", " "),
    ]
    return " ".join(p for p in parts if p)


def compute_semantic_score(
    inp: SemanticLocatorInput,
    node: TemplateNodeCandidate,
) -> tuple[float, list[str], dict[str, Any]]:
    cand = _candidate_blob(inp)
    tmpl = _node_blob(node)
    tfidf = _tfidf_cosine(cand, tmpl)
    ngram = _cosine(_char_ngrams(cand), _char_ngrams(tmpl))
    overlap = _token_overlap(cand, tmpl)

    # Fixed blend
    score = _round(min(max(0.45 * tfidf + 0.35 * ngram + 0.20 * overlap, 0.0), 1.0))
    reasons: list[str] = []
    if score >= 0.35:
        reasons.append("SEMANTIC_SIMILARITY")
    if overlap >= 0.4:
        reasons.append("PARTIAL_TOKEN_MATCH")

    components = {
        "tfidf_cosine": _round(tfidf),
        "char_ngram_cosine": _round(ngram),
        "token_overlap": _round(overlap),
        "normalized_candidate_text": normalize_text(cand),
        "normalized_template_text": normalize_text(tmpl),
    }
    # dedupe reasons
    uniq: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return score, uniq, components
