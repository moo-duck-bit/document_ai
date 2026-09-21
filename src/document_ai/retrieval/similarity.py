"""Similarity scoring — cosine (TF-IDF) and BM25."""

from __future__ import annotations

import math
from collections import Counter

from document_ai.retrieval.embedding import tokenize


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class BM25:
    """Okapi BM25 over token lists."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._avg_dl = 1.0
        self._doc_freq: Counter[str] = Counter()
        self._doc_count = 0
        self._doc_lens: list[int] = []
        self._corpus_tokens: list[list[str]] = []

    def fit(self, documents: list[str]) -> None:
        self._corpus_tokens = [tokenize(doc) for doc in documents]
        self._doc_count = len(self._corpus_tokens)
        self._doc_lens = [len(tokens) for tokens in self._corpus_tokens]
        self._avg_dl = sum(self._doc_lens) / self._doc_count if self._doc_count else 1.0
        self._doc_freq = Counter()
        for tokens in self._corpus_tokens:
            for token in set(tokens):
                self._doc_freq[token] += 1

    def score(self, query: str, doc_index: int) -> float:
        if doc_index < 0 or doc_index >= self._doc_count:
            return 0.0
        query_tokens = tokenize(query)
        doc_tokens = self._corpus_tokens[doc_index]
        doc_len = self._doc_lens[doc_index]
        tf_counter = Counter(doc_tokens)
        total = 0.0
        for term in query_tokens:
            df = self._doc_freq.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self._doc_count - df + 0.5) / (df + 0.5))
            tf = tf_counter.get(term, 0)
            denom = tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_dl)
            total += idf * (tf * (self.k1 + 1)) / (denom or 1)
        return total

    def score_all(self, query: str) -> list[float]:
        return [self.score(query, i) for i in range(self._doc_count)]
