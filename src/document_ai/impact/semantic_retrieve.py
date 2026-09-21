# -*- coding: utf-8 -*-
"""B2: Lexical candidate retrieval over RequirementBlock index (Trial 2).

Must NOT load or use expected_impact.* for ranking/expansion.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from document_ai.impact.semantic_index import RequirementBlock, TOKEN_RE, _tokenize

STOPWORDS = {
    "해야",
    "한다",
    "있다",
    "없는",
    "있도록",
    "경우",
    "대한",
    "통해",
    "위해",
    "또는",
    "및",
    "등",
    "수",
    "것",
    "및을",
    "change",
    "update",
    "the",
    "and",
    "for",
    "with",
}


@dataclass
class RetrievalCandidate:
    candidate_id: str
    document: str
    rank: int
    score: float
    matched_evidence: list[str] = field(default_factory=list)
    retrieval_reason: str = ""
    evidence_snippet: str = ""
    source_path: str = ""
    source_locator: str = ""
    title: str = ""
    scoring: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _query_tokens(text: str) -> list[str]:
    tokens = []
    for t in _tokenize(text):
        if t in STOPWORDS:
            continue
        if len(t) < 2:
            continue
        tokens.append(t)
    return tokens


def _snippet(body: str, matched: list[str], *, width: int = 160) -> str:
    if not body:
        return ""
    lower = body.lower()
    pos = -1
    hit = ""
    for m in matched:
        idx = lower.find(m.lower())
        if idx >= 0:
            pos = idx
            hit = m
            break
    if pos < 0:
        return body[:width].replace("\n", " ")
    start = max(0, pos - 40)
    end = min(len(body), pos + width)
    snippet = body[start:end].replace("\n", " ")
    if start > 0:
        snippet = "…" + snippet
    if end < len(body):
        snippet = snippet + "…"
    return snippet


def score_block(query_tokens: list[str], block: RequirementBlock) -> tuple[float, list[str], dict[str, Any]]:
    """Lexical overlap score: weighted Jaccard-like + keyword boost.

    No expected-impact leakage.
    """
    if not query_tokens:
        return 0.0, [], {"method": "lexical_overlap", "query_empty": True}

    doc_text = f"{block.title}\n{block.body_text}\n{' '.join(block.keywords)}"
    doc_tokens = set(_tokenize(doc_text))
    qset = set(query_tokens)
    overlap = sorted(qset & doc_tokens)
    if not overlap:
        # substring fallback for Korean compounds in query not split same way
        substr_hits: list[str] = []
        for qt in query_tokens:
            if len(qt) >= 2 and qt in doc_text.lower():
                substr_hits.append(qt)
        overlap = sorted(set(substr_hits))
        if not overlap:
            return 0.0, [], {"method": "lexical_overlap", "overlap": 0}

    jaccard = len(overlap) / max(len(qset | doc_tokens), 1)
    coverage = len(overlap) / max(len(qset), 1)
    # keyword list boost (domain tags on block)
    kw_hits = [k for k in block.keywords if any(k in qt or qt in k for qt in query_tokens)]
    kw_boost = 0.05 * len(kw_hits)
    # title hit boost
    title_hits = [t for t in overlap if t in (block.title or "").lower()]
    title_boost = 0.08 if title_hits else 0.0
    score = coverage * 0.7 + jaccard * 0.3 + kw_boost + title_boost
    score = round(min(score, 1.5), 6)
    detail = {
        "method": "lexical_overlap",
        "overlap_count": len(overlap),
        "query_token_count": len(qset),
        "coverage": round(coverage, 4),
        "jaccard": round(jaccard, 4),
        "keyword_boost": kw_boost,
        "title_boost": title_boost,
    }
    return score, overlap, detail


def retrieve_candidates(
    query: str,
    blocks: list[RequirementBlock],
    *,
    top_k: int = 10,
    document_filter: str | None = None,
) -> list[RetrievalCandidate]:
    """Return top-k lexical candidates. Never consults expected_impact."""
    q_tokens = _query_tokens(query)
    scored: list[tuple[float, list[str], dict[str, Any], RequirementBlock]] = []
    for block in blocks:
        if document_filter and block.document_type != document_filter:
            continue
        score, matched, detail = score_block(q_tokens, block)
        if score <= 0:
            continue
        scored.append((score, matched, detail, block))

    scored.sort(key=lambda x: (-x[0], x[3].req_id, x[3].document_type))
    results: list[RetrievalCandidate] = []
    for rank, (score, matched, detail, block) in enumerate(scored[:top_k], start=1):
        reason = (
            f"lexical overlap tokens={matched[:12]}; "
            f"coverage={detail.get('coverage')}; doc={block.document_type}"
        )
        results.append(
            RetrievalCandidate(
                candidate_id=block.req_id,
                document=block.document_type,
                rank=rank,
                score=score,
                matched_evidence=matched[:20],
                retrieval_reason=reason,
                evidence_snippet=_snippet(block.body_text or block.title, matched),
                source_path=block.source_path,
                source_locator=block.source_locator,
                title=block.title,
                scoring=detail,
            )
        )
    return results


def save_candidates(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
