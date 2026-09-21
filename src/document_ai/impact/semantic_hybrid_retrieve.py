# -*- coding: utf-8 -*-
"""Hybrid retrieval: lexical + TF-IDF cosine (semantic channel).

Does NOT read expected_impact.*. Document identity is (req_id, document_type).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.semantic_index import RequirementBlock
from document_ai.impact.semantic_retrieve import (
    _query_tokens,
    _snippet,
    score_block,
)
from document_ai.retrieval.embedding import TfidfEmbedding
from document_ai.retrieval.similarity import cosine_similarity

MethodName = Literal["lexical", "semantic", "hybrid"]


@dataclass
class ScoredHit:
    candidate_id: str
    document: str
    title: str
    source_path: str
    source_locator: str
    lexical_score: float
    semantic_score: float
    hybrid_score: float
    rank: int = 0
    matched_evidence: list[str] = field(default_factory=list)
    evidence_snippet: str = ""
    retrieval_reason: str = ""
    method: str = ""
    scoring: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _block_text(block: RequirementBlock) -> str:
    return f"{block.title}\n{block.body_text}\n{' '.join(block.keywords)}"


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def score_all_methods(
    query: str,
    blocks: list[RequirementBlock],
    *,
    hybrid_lexical_weight: float = 0.4,
    hybrid_semantic_weight: float = 0.6,
) -> list[ScoredHit]:
    """Score every block with lexical, semantic (TF-IDF cosine), and hybrid."""
    q_tokens = _query_tokens(query)
    docs = [_block_text(b) for b in blocks]
    tfidf = TfidfEmbedding()
    tfidf.fit(docs)
    q_vec = tfidf.query_vector(query)
    doc_vecs = tfidf.transform(docs)

    raw: list[ScoredHit] = []
    for i, block in enumerate(blocks):
        lex, matched, lex_detail = score_block(q_tokens, block)
        sem = float(cosine_similarity(q_vec, doc_vecs[i]))
        raw.append(
            ScoredHit(
                candidate_id=block.req_id,
                document=block.document_type,
                title=block.title,
                source_path=block.source_path,
                source_locator=block.source_locator,
                lexical_score=float(lex),
                semantic_score=round(sem, 6),
                hybrid_score=0.0,
                matched_evidence=matched[:20],
                evidence_snippet=_snippet(block.body_text or block.title, matched),
                scoring={"lexical": lex_detail, "semantic_method": "tfidf_cosine"},
            )
        )

    lex_n = _minmax([h.lexical_score for h in raw])
    sem_n = _minmax([h.semantic_score for h in raw])
    w_l, w_s = hybrid_lexical_weight, hybrid_semantic_weight
    for i, hit in enumerate(raw):
        hit.hybrid_score = round(w_l * lex_n[i] + w_s * sem_n[i], 6)
        hit.scoring["lexical_norm"] = round(lex_n[i], 6)
        hit.scoring["semantic_norm"] = round(sem_n[i], 6)
        hit.scoring["hybrid_weights"] = {"lexical": w_l, "semantic": w_s}
    return raw


def rank_by_method(
    scored: list[ScoredHit],
    method: MethodName,
    *,
    top_k: int = 15,
    min_score: float = 0.0,
) -> list[ScoredHit]:
    key = {
        "lexical": lambda h: h.lexical_score,
        "semantic": lambda h: h.semantic_score,
        "hybrid": lambda h: h.hybrid_score,
    }[method]
    ordered = sorted(
        [h for h in scored if key(h) > min_score],
        key=lambda h: (-key(h), h.candidate_id, h.document),
    )
    out: list[ScoredHit] = []
    for rank, hit in enumerate(ordered[:top_k], start=1):
        # copy-like update
        item = ScoredHit(
            candidate_id=hit.candidate_id,
            document=hit.document,
            title=hit.title,
            source_path=hit.source_path,
            source_locator=hit.source_locator,
            lexical_score=hit.lexical_score,
            semantic_score=hit.semantic_score,
            hybrid_score=hit.hybrid_score,
            rank=rank,
            matched_evidence=list(hit.matched_evidence),
            evidence_snippet=hit.evidence_snippet,
            method=method,
            scoring=dict(hit.scoring),
            retrieval_reason=(
                f"method={method}; lex={hit.lexical_score}; sem={hit.semantic_score}; "
                f"hybrid={hit.hybrid_score}; doc={hit.document}; "
                f"tokens={hit.matched_evidence[:8]}"
            ),
        )
        out.append(item)
    return out


def find_rank(
    ranked: list[ScoredHit], req_id: str, document: str | None = None
) -> dict[str, Any]:
    for hit in ranked:
        if hit.candidate_id != req_id:
            continue
        if document and hit.document != document:
            continue
        return {
            "found": True,
            "rank": hit.rank,
            "document": hit.document,
            "lexical_score": hit.lexical_score,
            "semantic_score": hit.semantic_score,
            "hybrid_score": hit.hybrid_score,
            "evidence_snippet": hit.evidence_snippet,
            "matched_evidence": hit.matched_evidence,
        }
    # best across docs if document not specified
    if document is None:
        hits = [h for h in ranked if h.candidate_id == req_id]
        if hits:
            best = min(hits, key=lambda h: h.rank)
            return {
                "found": True,
                "rank": best.rank,
                "document": best.document,
                "lexical_score": best.lexical_score,
                "semantic_score": best.semantic_score,
                "hybrid_score": best.hybrid_score,
                "evidence_snippet": best.evidence_snippet,
                "matched_evidence": best.matched_evidence,
            }
    return {"found": False, "req_id": req_id, "document": document}
