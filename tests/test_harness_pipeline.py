"""End-to-end tests for Document Harness generation pipeline."""

import json
import shutil
from pathlib import Path

import pytest

from document_ai.facts.fact_builder import FactBuilder
from document_ai.harness.document_harness import DocumentHarness
from document_ai.harness.pipeline import GenerationPipeline
from document_ai.retrieval.example_selector import ExampleSelector
from document_ai.retrieval.retriever import CaseRetriever


@pytest.fixture
def inventory_case(tmp_path):
    case_dir = tmp_path / "inventory_mgmt"
    case_dir.mkdir()
    src = Path("data/cases/inventory_mgmt/input.json")
    shutil.copy(src, case_dir / "input.json")
    return case_dir


def test_fact_builder_merges_retrieved_examples(inventory_case):
    retriever = CaseRetriever(cases_root=Path("data/cases"))
    retriever.index_cases(exclude={"inventory_mgmt"})
    hits = retriever.retrieve("inventory_b2b warehouse IMS Acme Logistics", top_k=1)
    assert hits
    examples = ExampleSelector().select(Path(hits[0].case_dir))
    intake = json.loads((inventory_case / "input.json").read_text(encoding="utf-8"))
    graph = FactBuilder().build(inventory_case, intake=intake, examples=examples)
    assert graph.payloads.get("requirements.json")
    assert graph.retrieval.get("source_case_id")


def test_harness_generates_mdsr_mddr_from_minimal_input(inventory_case):
    harness = DocumentHarness(force_form_fill=True)
    report = harness.generate(inventory_case)
    assert report["steps"]["intake"]["case_id"] == "inventory_mgmt"
    assert (inventory_case / "requirements.json").exists()
    assert (inventory_case / "mdsr_content.json").exists()
    assert (inventory_case / "design_items.json").exists()
    assert (inventory_case / "output_mdsr.docx").exists()
    assert (inventory_case / "output_mddr.docx").exists()
    mdsr_review = report["steps"]["review"].get("mdsr", {})
    assert mdsr_review.get("mindrium_hits", 1) == 0


def test_pipeline_blocks_unconfirmed_intake(tmp_path):
    case_dir = tmp_path / "draft"
    case_dir.mkdir()
    (case_dir / "input.json").write_text(
        json.dumps({"case_id": "draft", "confirmed": False}, ensure_ascii=False),
        encoding="utf-8",
    )
    report = GenerationPipeline(use_retrieval=False).run(case_dir)
    assert "error" in report.steps
