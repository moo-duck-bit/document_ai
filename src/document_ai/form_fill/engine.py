"""Form fill engine — Facts → Rules → Retrieved Example → LLM → payloads."""

from __future__ import annotations

from typing import Any

from document_ai.facts.fact_graph import FactGraph
from document_ai.form_fill.llm import FreeTextLLM, get_free_text_llm
from document_ai.form_fill.rules import (
    apply_rules_to_intake,
    build_design_content_from_graph,
    build_design_items_from_graph,
    build_mddr_content_from_graph,
    build_mdsr_content_from_graph,
    build_requirements_from_graph,
)
from document_ai.form_fill.security_tests import (
    load_default_security_seed,
    synthesize_security_tests,
)
from document_ai.retrieval.example_selector import SelectedExamples


class FormFillEngine:
    def __init__(self, llm: FreeTextLLM | None = None) -> None:
        # Default: optional env-gated free_text LLM; structured fields stay rules/facts.
        self.llm = llm or get_free_text_llm()

    def fill(
        self,
        intake: dict[str, Any],
        graph: FactGraph,
        examples: SelectedExamples | None,
        *,
        force_generate: bool = False,
    ) -> dict[str, Any]:
        """Return generated payload dicts (may be written to case dir by harness)."""
        intake = apply_rules_to_intake(intake)
        payloads = dict(graph.payloads)
        domain = intake.get("domain", "")

        need_req = force_generate or "requirements.json" not in payloads
        need_mdsr = force_generate or "mdsr_content.json" not in payloads
        need_mddr = force_generate or "mddr_content.json" not in payloads
        need_design = force_generate or "design_items.json" not in payloads
        need_design_content = force_generate or "design_content.json" not in payloads
        need_security = force_generate or "security_tests.json" not in payloads
        wants_xxcs = "report_security_verification" in (intake.get("templates_in_set") or [])

        if examples or payloads or wants_xxcs:
            if need_req:
                req = build_requirements_from_graph(intake, payloads)
                if req:
                    payloads["requirements.json"] = req
            if need_mdsr:
                mdsr = build_mdsr_content_from_graph(intake, payloads)
                if mdsr:
                    self._enrich_mdsr_narrative(intake, mdsr)
                    payloads["mdsr_content.json"] = mdsr
            if need_mddr:
                mddr = build_mddr_content_from_graph(intake, payloads)
                if mddr:
                    self._enrich_mddr_narrative(intake, mddr)
                    payloads["mddr_content.json"] = mddr
            if need_design:
                design = build_design_items_from_graph(intake, payloads)
                if design:
                    payloads["design_items.json"] = design
            if need_design_content:
                design_content = build_design_content_from_graph(intake, payloads)
                if design_content:
                    payloads["design_content.json"] = design_content
            if need_security and (wants_xxcs or examples or payloads.get("security_tests.json")):
                seed = payloads.get("security_tests.json") or (
                    (examples.payloads.get("security_tests.json") if examples else None)
                ) or load_default_security_seed()
                security = synthesize_security_tests(
                    intake=intake,
                    requirements_payload=payloads.get("requirements.json") or {},
                    design_payload=payloads.get("design_items.json") or {},
                    seed=seed if isinstance(seed, dict) else None,
                )
                if security.get("tests"):
                    payloads["security_tests.json"] = security

        graph.payloads = payloads
        return {
            "intake": intake,
            "payloads": payloads,
            "generated": [name for name in payloads if name.endswith(".json")],
        }

    def _enrich_mdsr_narrative(self, intake: dict[str, Any], mdsr: dict[str, Any]) -> None:
        hints = intake.get("free_text_hints") or {}
        narrative = mdsr.get("narrative") or []
        if not narrative:
            overview = self.llm.generate(
                "Write product overview narrative",
                context={"free_text_hints": hints, "fallback_text": hints.get("system_overview", "")},
            )
            arch = self.llm.generate(
                "Write architecture narrative",
                context={"free_text_hints": hints, "fallback_text": hints.get("architecture_narrative", "")},
            )
            mdsr["narrative"] = [text for text in (overview, arch) if text]
        mdsr.setdefault("cover_product_line", intake.get("facts", {}).get("author_org", ""))
        standards = intake.get("standards") or []
        if standards:
            mdsr["standards"] = standards

    def _enrich_mddr_narrative(self, intake: dict[str, Any], mddr: dict[str, Any]) -> None:
        hints = intake.get("free_text_hints") or {}
        paragraphs = mddr.get("paragraphs") or []
        if len(paragraphs) < 3:
            overview = self.llm.generate(
                "Write MDDR overview",
                context={"free_text_hints": hints, "fallback_text": hints.get("system_overview", "")},
            )
            arch = self.llm.generate(
                "Write architecture narrative",
                context={"free_text_hints": hints, "fallback_text": hints.get("architecture_narrative", "")},
            )
            mddr["paragraphs"] = [
                "Software Design Specification",
                *(mddr.get("standards") or intake.get("standards") or [])[:2],
                mddr.get("document_title")
                or f"EC-SW-MDDR({intake.get('facts', {}).get('product_code', 'APP')}) "
                f"{intake.get('product_name', '')} 소프트웨어 설계명세서",
                overview,
                arch,
            ]
