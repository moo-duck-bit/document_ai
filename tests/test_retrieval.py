"""Tests for retrieval engine."""

from pathlib import Path

from document_ai.retrieval.example_selector import ExampleSelector
from document_ai.retrieval.retriever import CaseRetriever
from document_ai.retrieval.similarity import BM25, cosine_similarity


def test_bm25_ranks_relevant_document():
    bm25 = BM25()
    bm25.fit(["inventory warehouse stock", "hospital reservation clinic"])
    scores = bm25.score_all("warehouse inventory management")
    assert scores[0] > scores[1]


def test_cosine_similarity_identical_vectors():
    import pytest

    assert cosine_similarity({"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}) == pytest.approx(1.0)


def test_case_retriever_finds_jm_for_inventory_query():
    retriever = CaseRetriever(cases_root=Path("data/cases"))
    count = retriever.index_cases(exclude={"inventory_mgmt"})
    assert count >= 1
    hits = retriever.retrieve(
        "inventory_b2b warehouse stock management IMS Acme Logistics",
        top_k=3,
    )
    assert hits
    assert hits[0].case_id in {"jm_collection", "mindrium_xa"}


def test_example_selector_loads_payloads():
    selector = ExampleSelector()
    examples = selector.select(Path("data/cases/jm_collection"))
    assert examples.source_case_id == "jm_collection"
    assert examples.payloads.get("requirements.json")
    assert examples.payloads.get("mdsr_content.json")
    assert examples.payloads.get("design_items.json")
