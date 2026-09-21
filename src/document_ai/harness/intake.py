"""Case intake — validate and normalize input.json."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from document_ai.facts.fact_builder import load_input


@dataclass
class IntakeResult:
    case_id: str
    payload: dict[str, Any]
    confirmed: bool
    query_text: str


class CaseIntake:
    def run(self, case_dir) -> IntakeResult:
        from pathlib import Path

        case_dir = Path(case_dir)
        payload = load_input(case_dir)
        case_id = payload.get("case_id", case_dir.name)
        confirmed = payload.get("confirmed", False) is not False
        query_parts = [
            payload.get("domain", ""),
            payload.get("product_name", ""),
            str(payload.get("facts", {})),
            str(payload.get("free_text_hints", {})),
        ]
        query_text = "\n".join(p for p in query_parts if p)
        return IntakeResult(
            case_id=case_id,
            payload=payload,
            confirmed=confirmed,
            query_text=query_text,
        )
