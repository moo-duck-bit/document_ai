"""Select few-shot examples by artifact category from a retrieved case."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ExampleCategory = Literal["requirement", "design", "sdt", "security"]


@dataclass
class SelectedExamples:
    source_case_id: str
    source_case_dir: str
    requirement: dict[str, Any] | None = None
    design: dict[str, Any] | None = None
    sdt: dict[str, Any] | None = None
    security: dict[str, Any] | None = None
    payloads: dict[str, Any] = field(default_factory=dict)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class ExampleSelector:
    """Pull category-specific payloads from a source case directory."""

    def select(self, case_dir: Path) -> SelectedExamples:
        case_dir = case_dir.resolve()
        case_id = case_dir.name
        requirements = _load_json(case_dir / "requirements.json")
        design_items = _load_json(case_dir / "design_items.json")
        design_content = _load_json(case_dir / "design_content.json")
        mdsr_content = _load_json(case_dir / "mdsr_content.json")
        mddr_content = _load_json(case_dir / "mddr_content.json")
        security_tests = _load_json(case_dir / "security_tests.json")

        sdt = None
        if mdsr_content:
            sdt = {
                "product_overview": mdsr_content.get("product_overview"),
                "unique_requirements": mdsr_content.get("unique_requirements"),
                "narrative": mdsr_content.get("narrative"),
            }

        security = None
        if requirements and requirements.get("traceability"):
            security = {
                "traceability": requirements.get("traceability", []),
                "security_requirements": [
                    row
                    for row in requirements.get("requirements", [])
                    if str(row.get("req_id", "")).startswith("Req. 1")
                ],
            }
        if security_tests:
            security = {**(security or {}), "security_tests": security_tests}

        return SelectedExamples(
            source_case_id=case_id,
            source_case_dir=str(case_dir),
            requirement=requirements,
            design={"items": design_items, "content": design_content, "mddr_content": mddr_content}
            if design_items or design_content or mddr_content
            else None,
            sdt=sdt,
            security=security,
            payloads={
                "requirements.json": requirements,
                "design_items.json": design_items,
                "design_content.json": design_content,
                "mdsr_content.json": mdsr_content,
                "mddr_content.json": mddr_content,
                "security_tests.json": security_tests,
            },
        )
