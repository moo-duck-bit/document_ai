"""Shared models for read-only security checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class EvidenceRecord:
    type: str
    path: str = ""
    description: str = ""
    sha256: str = ""

    def to_execution_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "type": self.type,
                "path": self.path,
                "description": self.description,
                "sha256": self.sha256,
            }.items()
            if value
        }


@dataclass(slots=True)
class SecurityCheckResult:
    security_test_id: str
    status: str
    actual_result: str
    evidence: list[EvidenceRecord] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_execution_dict(self) -> dict[str, Any]:
        note_parts = [
            f"duration_ms={self.duration_ms}",
            f"error={self.error}" if self.error else "",
        ]
        return {
            "security_test_id": self.security_test_id,
            "status": self.status,
            "actual_result": self.actual_result,
            "evidence": [item.to_execution_dict() for item in self.evidence],
            "executed_at": self.completed_at or self.started_at,
            "executor_note": "; ".join(part for part in note_parts if part),
            "runner_metadata": self.metadata,
        }


@dataclass(slots=True)
class RunnerContext:
    case_id: str
    execution_id: str
    output_path: Path
    evidence_dir: Path
    target: dict[str, Any]
    policy: dict[str, Any]
    timeout: float
    synthetic: bool
    no_network: bool
    max_body_bytes: int
    max_redirects: int
    retry_count: int
    min_request_interval_ms: int
    check_config: dict[str, Any]
    attempts: list[dict[str, Any]] = field(default_factory=list)


class SecurityCheck(Protocol):
    check_id: str
    security_test_id: str

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        ...

    def run(self, context: RunnerContext) -> SecurityCheckResult:
        ...
