from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENT_FIELDS = (
    "event_id",
    "event_type",
    "timestamp",
    "correlation_id",
    "case_id",
    "workflow_id",
    "task_id",
    "harness",
    "actor",
    "payload",
    "metadata",
)


@dataclass
class PlatformEvent:
    event_type: str
    correlation_id: str
    case_id: str
    workflow_id: str | None = None
    task_id: str | None = None
    harness: str | None = None
    actor: dict[str, Any] = field(default_factory=lambda: {"type": "system", "id": "platform_runtime"})
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "case_id": self.case_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "harness": self.harness,
            "actor": self.actor,
            "payload": self.payload,
            "metadata": self.metadata,
        }


class EventMemory:
    """Append-only event log stored at data/cases/{case_id}/events.jsonl."""

    def __init__(self, case_dir: Path | None = None) -> None:
        self._case_dir = Path(case_dir) if case_dir else None

    @property
    def case_dir(self) -> Path | None:
        return self._case_dir

    @property
    def events_path(self) -> Path | None:
        if self._case_dir is None:
            return None
        return self._case_dir / "events.jsonl"

    def bind_case(self, case_dir: str | Path) -> None:
        self._case_dir = Path(case_dir)

    def append_event(
        self,
        event_type: str,
        *,
        correlation_id: str,
        case_id: str,
        workflow_id: str | None = None,
        task_id: str | None = None,
        harness: str | None = None,
        actor: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._case_dir is None:
            self.bind_case(case_id)

        event = PlatformEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            timestamp=datetime.now(UTC).isoformat(),
            correlation_id=correlation_id,
            case_id=case_id,
            workflow_id=workflow_id,
            task_id=task_id,
            harness=harness,
            actor=actor or {"type": "system", "id": "platform_runtime"},
            payload=payload or {},
            metadata=metadata or {},
        )
        record = event.to_dict()
        self._validate_event(record)
        self._append_line(record)
        return record

    def list_events(self, *, correlation_id: str | None = None) -> list[dict[str, Any]]:
        events = self.load_events()
        if correlation_id is None:
            return events
        return [event for event in events if event.get("correlation_id") == correlation_id]

    def load_events(self) -> list[dict[str, Any]]:
        path = self.events_path
        if path is None or not path.exists():
            return []

        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            events.append(json.loads(text))
        return events

    def clear_events(self) -> None:
        path = self.events_path
        if path is None:
            return
        if path.exists():
            path.unlink()

    def _append_line(self, record: dict[str, Any]) -> None:
        path = self.events_path
        if path is None:
            raise ValueError("EventMemory requires a bound case_dir before append")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _validate_event(self, record: dict[str, Any]) -> None:
        missing = [field_name for field_name in EVENT_FIELDS if field_name not in record]
        if missing:
            raise ValueError(f"Event record missing fields: {missing}")
