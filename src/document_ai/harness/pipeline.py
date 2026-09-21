"""Unified document generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from document_ai.facts.fact_builder import FactBuilder
from document_ai.form_fill.engine import FormFillEngine
from document_ai.harness.evaluation import evaluate_case
from document_ai.harness.intake import CaseIntake
from document_ai.harness.render import render_all, render_document
from document_ai.harness.review import review_case
from document_ai.retrieval.example_selector import ExampleSelector
from document_ai.retrieval.retriever import CaseRetriever


@dataclass
class PipelineReport:
    case_dir: str
    steps: dict[str, Any] = field(default_factory=dict)
    ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_dir": self.case_dir,
            "mode": "harness_generate",
            "ok": self.ok,
            "steps": self.steps,
        }


class GenerationPipeline:
    """Case Intake → Retrieval → Fact Builder → Form Fill → Render → Review → Evaluation."""

    def __init__(
        self,
        *,
        use_retrieval: bool = True,
        materialize: bool = True,
        force_form_fill: bool = False,
    ) -> None:
        self.use_retrieval = use_retrieval
        self.materialize = materialize
        self.force_form_fill = force_form_fill
        self.intake = CaseIntake()
        self.retriever = CaseRetriever()
        self.selector = ExampleSelector()
        self.fact_builder = FactBuilder()
        self.form_fill = FormFillEngine()

    def run(self, case_dir: Path, *, template_id: str | None = None) -> PipelineReport:
        case_dir = case_dir.resolve()
        report = PipelineReport(case_dir=str(case_dir))

        intake_result = self.intake.run(case_dir)
        report.steps["intake"] = {
            "case_id": intake_result.case_id,
            "confirmed": intake_result.confirmed,
        }
        if not intake_result.confirmed:
            report.steps["error"] = "input.json confirmed=false — intake blocked"
            return report

        examples = None
        retrieval_hits: list[dict[str, Any]] = []
        if self.use_retrieval:
            indexed = self.retriever.index_cases(exclude={intake_result.case_id})
            hits = self.retriever.retrieve(intake_result.query_text, top_k=1)
            retrieval_hits = [hit.__dict__ for hit in hits]
            report.steps["retrieval"] = {"indexed_cases": indexed, "hits": retrieval_hits}
            if hits:
                examples = self.selector.select(Path(hits[0].case_dir))

        graph = self.fact_builder.build(
            case_dir,
            intake=intake_result.payload,
            examples=examples,
            refresh_from_examples=self.force_form_fill,
        )
        fill_result = self.form_fill.fill(
            intake_result.payload,
            graph,
            examples,
            force_generate=self.force_form_fill,
        )
        report.steps["fact_builder"] = {"payload_keys": list(graph.payloads.keys())}
        report.steps["form_fill"] = {
            "generated": fill_result.get("generated", []),
        }

        if self.materialize:
            written = self.fact_builder.materialize_payloads(
                case_dir,
                graph,
                overwrite=self.force_form_fill,
            )
            report.steps["materialize"] = {"written": written}

        if template_id:
            render_result = render_document(case_dir, template_id, intake=fill_result["intake"])
            report.steps["render"] = render_result
        else:
            render_result = render_all(case_dir, intake=fill_result["intake"])
            report.steps["render"] = render_result

        review_result = review_case(case_dir)
        report.steps["review"] = review_result
        eval_result = evaluate_case(case_dir)
        report.steps["evaluation"] = eval_result
        report.ok = bool(review_result.get("ok")) and bool(eval_result.get("passed"))
        return report
