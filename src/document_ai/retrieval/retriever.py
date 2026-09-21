"""Case-level retrieval over completed example cases."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from document_ai.paths import CASES, PROJECT_ROOT
from document_ai.retrieval.embedding import TfidfEmbeddingProvider
from document_ai.retrieval.similarity import BM25, cosine_similarity


@dataclass
class CaseRecord:
    case_id: str
    case_dir: Path
    document: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalHit:
    case_id: str
    case_dir: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def _case_document_text(case_dir: Path) -> str:
    parts: list[str] = []
    input_path = case_dir / "input.json"
    if input_path.exists():
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        parts.extend(
            [
                payload.get("case_id", ""),
                payload.get("domain", ""),
                payload.get("product_name", ""),
                json.dumps(payload.get("facts", {}), ensure_ascii=False),
                json.dumps(payload.get("free_text_hints", {}), ensure_ascii=False),
            ]
        )
    for name in ("requirements.json", "mdsr_content.json", "mddr_content.json"):
        path = case_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8")[:4000])
    return "\n".join(p for p in parts if p)


class CaseRetriever:
    """Retrieve similar completed cases using BM25 + TF-IDF cosine blend."""

    def __init__(self, cases_root: Path | None = None) -> None:
        self.cases_root = cases_root or CASES
        self._records: list[CaseRecord] = []
        self._bm25 = BM25()
        self._tfidf = TfidfEmbeddingProvider()
        self._tfidf_vectors: list[dict[str, float]] = []

    def index_cases(self, *, exclude: set[str] | None = None) -> int:
        exclude = exclude or set()
        self._records = []
        if not self.cases_root.exists():
            return 0
        for case_dir in sorted(self.cases_root.iterdir()):
            if not case_dir.is_dir():
                continue
            if not (case_dir / "input.json").exists():
                continue
            if not (case_dir / "requirements.json").exists():
                continue
            case_id = case_dir.name
            if case_id in exclude:
                continue
            payload = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
            if payload.get("confirmed") is False:
                continue
            if payload.get("intake_channel") == "harness_minimal_input":
                continue
            doc = _case_document_text(case_dir)
            self._records.append(
                CaseRecord(
                    case_id=case_id,
                    case_dir=case_dir,
                    document=doc,
                    metadata={
                        "domain": payload.get("domain", ""),
                        "product_name": payload.get("product_name", ""),
                        "templates_in_set": payload.get("templates_in_set", []),
                    },
                )
            )
        documents = [r.document for r in self._records]
        if documents:
            self._bm25.fit(documents)
            self._tfidf.fit(documents)
            self._tfidf_vectors = self._tfidf.embed_corpus(documents)
        return len(self._records)

    def retrieve(self, query: str, *, top_k: int = 3) -> list[RetrievalHit]:
        if not self._records:
            return []
        bm25_scores = self._bm25.score_all(query)
        query_vec = self._tfidf.embed_query(query)
        blended: list[RetrievalHit] = []
        for index, record in enumerate(self._records):
            cosine = cosine_similarity(query_vec, self._tfidf_vectors[index])
            score = 0.6 * bm25_scores[index] + 0.4 * cosine
            blended.append(
                RetrievalHit(
                    case_id=record.case_id,
                    case_dir=str(record.case_dir),
                    score=score,
                    metadata=dict(record.metadata),
                )
            )
        blended.sort(key=lambda hit: hit.score, reverse=True)
        return blended[:top_k]

    def resolve_cases_root(self) -> Path:
        return self.cases_root if self.cases_root.is_absolute() else (PROJECT_ROOT / self.cases_root)
