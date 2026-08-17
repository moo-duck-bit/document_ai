from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentContext:
    """Shared state passed through the multi-agent pipeline."""

    case_dir: Path
    change: dict[str, Any]
    requirements_payload: dict[str, Any]
    design_payload: dict[str, Any] | None = None
    security_payload: dict[str, Any] | None = None
    dry_run: bool = True
    apply: bool = False
    prior: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent_id: str
    status: str  # ok | warning | error
    data: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "data": self.data,
            "issues": self.issues,
        }


class BaseAgent(ABC):
    agent_id: str

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
