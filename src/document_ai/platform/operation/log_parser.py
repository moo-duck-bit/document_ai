from __future__ import annotations

import re
from pathlib import Path

from document_ai.platform.operation.models import LogEvent, LogEventType

_LOG_PATTERNS: list[tuple[LogEventType, re.Pattern[str]]] = [
    ("oom", re.compile(r"(out of memory|oom|cuda out of memory)", re.IGNORECASE)),
    ("cuda_error", re.compile(r"(cuda error|cudaerror|cudnn error)", re.IGNORECASE)),
    ("nvidia_xid", re.compile(r"\bXid\b", re.IGNORECASE)),
    ("restart_loop", re.compile(r"(restart loop|restarting|back-off restarting)", re.IGNORECASE)),
    ("disk_full", re.compile(r"(no space left on device|disk full|filesystem full)", re.IGNORECASE)),
    ("permission_denied", re.compile(r"permission denied", re.IGNORECASE)),
]


def detect_log_events(text: str, *, source: str = "log") -> list[LogEvent]:
    events: list[LogEvent] = []
    seen: set[tuple[str, int]] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        for event_type, pattern in _LOG_PATTERNS:
            if not pattern.search(line):
                continue
            key = (event_type, line_number)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                LogEvent(
                    event_type=event_type,
                    source=source,
                    line=line.strip(),
                    line_number=line_number,
                )
            )
            break
    return events


def detect_log_events_from_file(path: str | Path, *, source: str | None = None) -> list[LogEvent]:
    resolved = Path(path)
    return detect_log_events(resolved.read_text(encoding="utf-8"), source=source or resolved.name)
