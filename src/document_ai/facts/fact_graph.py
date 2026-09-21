"""FactGraph — canonical merged case facts for form-fill and LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactNode:
    key: str
    value: Any
    source: str
    category: str = "fact"


@dataclass
class FactGraph:
    case_id: str
    nodes: dict[str, FactNode] = field(default_factory=dict)
    payloads: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any, *, source: str, category: str = "fact") -> None:
        self.nodes[key] = FactNode(key=key, value=value, source=source, category=category)

    def get(self, key: str, default: Any = None) -> Any:
        node = self.nodes.get(key)
        return node.value if node else default

    def facts_dict(self) -> dict[str, Any]:
        return {k: n.value for k, n in self.nodes.items() if n.category == "fact"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "facts": self.facts_dict(),
            "payloads": self.payloads,
            "retrieval": self.retrieval,
            "nodes": {
                k: {"value": n.value, "source": n.source, "category": n.category}
                for k, n in self.nodes.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
