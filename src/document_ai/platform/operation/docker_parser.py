from __future__ import annotations

import re
from pathlib import Path

from document_ai.platform.operation.models import DockerContainer

_CONTAINER_ROW_RE = re.compile(
    r"^([0-9a-f]{12})\s+(\S+)\s+(\S+)\s+(.+?)(?:\s*\((healthy|unhealthy)\))?\s*$"
)


def _parse_restart_count(status: str) -> int:
    match = re.search(r"Restarting\s*\((\d+)\)", status, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def _is_unhealthy(status: str, health: str | None) -> bool:
    if health and health.lower() == "unhealthy":
        return True
    lowered = status.lower()
    return "unhealthy" in lowered or lowered.startswith("restarting")


def parse_docker_ps(text: str) -> list[DockerContainer]:
    containers: list[DockerContainer] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("CONTAINER ID"):
            continue
        match = _CONTAINER_ROW_RE.match(stripped)
        if not match:
            continue
        status = match.group(4).strip()
        containers.append(
            DockerContainer(
                container_id=match.group(1),
                name=match.group(2).strip(),
                image=match.group(3).strip(),
                status=status,
                restart_count=_parse_restart_count(status),
                unhealthy=_is_unhealthy(status, match.group(5)),
            )
        )
    return containers


def parse_docker_ps_file(path: str | Path) -> list[DockerContainer]:
    return parse_docker_ps(Path(path).read_text(encoding="utf-8"))
