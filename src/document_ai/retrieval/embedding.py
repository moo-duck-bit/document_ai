"""Text embedding backends — TF-IDF default, swappable for dense/LLM embeddings."""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from typing import Protocol


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_]{2,}")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


class EmbeddingBackend(Protocol):
  def fit(self, documents: list[str]) -> None: ...
  def transform(self, documents: list[str]) -> list[dict[str, float]]: ...
  def query_vector(self, query: str) -> dict[str, float]: ...


class TfidfEmbedding:
    """Pure-Python TF-IDF vectors (no sklearn dependency)."""

    def __init__(self) -> None:
        self._doc_count = 0
        self._df: Counter[str] = Counter()
        self._fitted = False

    def fit(self, documents: list[str]) -> None:
        self._doc_count = len(documents)
        self._df = Counter()
        for doc in documents:
            for token in set(tokenize(doc)):
                self._df[token] += 1
        self._fitted = True

    def _vectorize(self, text: str) -> dict[str, float]:
        if not self._fitted:
            raise RuntimeError("TfidfEmbedding.fit() must be called first")
        counts = Counter(tokenize(text))
        total = sum(counts.values()) or 1
        vector: dict[str, float] = {}
        for token, count in counts.items():
            df = self._df.get(token, 0)
            if df == 0:
                continue
            idf = math.log((1 + self._doc_count) / (1 + df)) + 1.0
            vector[token] = (count / total) * idf
        return vector

    def transform(self, documents: list[str]) -> list[dict[str, float]]:
        return [self._vectorize(doc) for doc in documents]

    def query_vector(self, query: str) -> dict[str, float]:
        return self._vectorize(query)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_corpus(self, documents: list[str]) -> list[dict[str, float]]: ...

    @abstractmethod
    def embed_query(self, query: str) -> dict[str, float]: ...


class TfidfEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._backend = TfidfEmbedding()

    def fit(self, documents: list[str]) -> None:
        self._backend.fit(documents)

    def embed_corpus(self, documents: list[str]) -> list[dict[str, float]]:
        return self._backend.transform(documents)

    def embed_query(self, query: str) -> dict[str, float]:
        return self._backend.query_vector(query)
