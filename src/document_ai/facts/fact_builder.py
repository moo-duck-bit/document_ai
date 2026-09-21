"""Build FactGraph from intake + retrieval + on-disk case payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.facts.fact_graph import FactGraph
from document_ai.retrieval.example_selector import SelectedExamples


PAYLOAD_FILES = (
    "requirements.json",
    "mdsr_content.json",
    "mddr_content.json",
    "design_items.json",
    "design_content.json",
    "security_tests.json",
)


def load_input(case_dir: Path) -> dict[str, Any]:
    path = case_dir / "input.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing_payloads(case_dir: Path) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for name in PAYLOAD_FILES:
        path = case_dir / name
        if path.exists():
            payloads[name] = json.loads(path.read_text(encoding="utf-8"))
    return payloads


class FactBuilder:
    """Merge input.json, retrieved examples, and generated payloads into FactGraph."""

    def build(
        self,
        case_dir: Path,
        *,
        intake: dict[str, Any],
        examples: SelectedExamples | None = None,
        generated_payloads: dict[str, Any] | None = None,
        refresh_from_examples: bool = False,
    ) -> FactGraph:
        case_dir = case_dir.resolve()
        case_id = intake.get("case_id", case_dir.name)
        graph = FactGraph(case_id=case_id)

        for key, value in (intake.get("facts") or {}).items():
            graph.set(key, value, source="input.json", category="fact")

        for key in ("product_name", "product_code", "domain", "standards"):
            if intake.get(key) is not None:
                graph.set(key, intake[key], source="input.json", category="meta")

        if intake.get("free_text_hints"):
            graph.set("free_text_hints", intake["free_text_hints"], source="input.json", category="hint")

        existing = {} if refresh_from_examples else _load_existing_payloads(case_dir)
        merged_payloads = dict(existing)
        if examples:
            graph.retrieval = {
                "source_case_id": examples.source_case_id,
                "source_case_dir": examples.source_case_dir,
            }
            for name, payload in examples.payloads.items():
                if not payload:
                    continue
                if refresh_from_examples or name not in merged_payloads:
                    merged_payloads[name] = payload

        if generated_payloads:
            merged_payloads.update(generated_payloads)

        graph.payloads = merged_payloads
        return graph

    def materialize_payloads(self, case_dir: Path, graph: FactGraph, *, overwrite: bool = False) -> list[str]:
        """Write payload JSON files from FactGraph when missing or overwrite=True."""
        written: list[str] = []
        case_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in graph.payloads.items():
            if not payload or not name.endswith(".json"):
                continue
            path = case_dir / name
            if path.exists() and not overwrite:
                continue
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(name)
        return written
