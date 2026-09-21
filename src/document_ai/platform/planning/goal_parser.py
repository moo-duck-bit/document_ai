from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParsedGoal:
    text: str
    case_dir: Path
    change: dict[str, Any] | Path | str
    metadata: dict[str, Any]
    explicit_intent: str | None = None
    goal: str | None = None

    @property
    def combined_text(self) -> str:
        parts = [self.goal or "", self.text, self.explicit_intent or ""]
        if self.metadata.get("intent"):
            parts.append(str(self.metadata["intent"]))
        if self.metadata.get("description"):
            parts.append(str(self.metadata["description"]))
        if isinstance(self.change, str):
            parts.append(self.change)
        elif isinstance(self.change, Path):
            parts.append(self.change.name)
        return " ".join(part for part in parts if part).strip()


def parse_goal(
    *,
    case_dir: str | Path,
    change: dict[str, Any] | Path | str,
    metadata: dict[str, Any] | None = None,
    intent: str | None = None,
    goal: str | None = None,
) -> ParsedGoal:
    resolved_metadata = dict(metadata or {})
    text_parts: list[str] = []
    if goal:
        text_parts.append(goal)
    if intent:
        text_parts.append(intent)
    if isinstance(change, str):
        text_parts.append(change)

    return ParsedGoal(
        text=" ".join(text_parts),
        case_dir=Path(case_dir),
        change=change,
        metadata=resolved_metadata,
        explicit_intent=intent or resolved_metadata.get("intent"),
        goal=goal or resolved_metadata.get("goal"),
    )


def is_document_change_path(change: Any) -> bool:
    if not isinstance(change, Path):
        return False
    return change.suffix == ".json" and "changes" in change.parts
