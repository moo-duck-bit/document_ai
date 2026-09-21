# -*- coding: utf-8 -*-
"""Safe artifact path resolution inside workflow root."""

from __future__ import annotations

import urllib.parse
from pathlib import Path

ALLOWED_ARTIFACT_NAMES = frozenset(
    {
        "workflow.json",
        "workflow_summary.json",
        "workflow_validation.json",
        "workflow_timeline.json",
        "meta.json",
    }
)


class WorkflowPathError(ValueError):
    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}")


def _normalize_name(name: str) -> str:
    decoded = urllib.parse.unquote(name or "")
    return decoded.replace("\\", "/").strip()


def resolve_workflow_artifact(workflow_root: Path, name: str) -> Path:
    raw = _normalize_name(name)
    if not raw or raw in {".", "/"}:
        raise WorkflowPathError("ARTIFACT_NOT_FOUND", "empty artifact name")
    if ".." in raw.split("/"):
        raise WorkflowPathError("PATH_TRAVERSAL_BLOCKED", raw)
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        raise WorkflowPathError("PATH_TRAVERSAL_BLOCKED", raw)
    # only basename under workflow/ or root meta
    base = Path(raw).name
    if base != raw and "/" in raw:
        # allow workflow/<name> only
        parts = [p for p in raw.split("/") if p]
        if len(parts) != 2 or parts[0] != "workflow":
            raise WorkflowPathError("ARTIFACT_NOT_ALLOWED", raw)
        base = parts[1]
    if base not in ALLOWED_ARTIFACT_NAMES and not base.endswith(".docx"):
        # docx copies allowed by exact filename under copies/
        raise WorkflowPathError("ARTIFACT_NOT_ALLOWED", base)

    root = workflow_root.resolve()
    if base in ALLOWED_ARTIFACT_NAMES:
        if base == "meta.json":
            candidate = root / "meta.json"
        else:
            candidate = root / "workflow" / base
    else:
        candidate = root / "copies" / base

    resolved = candidate.resolve()
    if root not in resolved.parents and resolved != root:
        raise WorkflowPathError("ARTIFACT_OUTSIDE_WORKFLOW_ROOT", str(resolved))
    if not resolved.exists():
        raise WorkflowPathError("ARTIFACT_NOT_FOUND", base)
    if resolved.is_dir():
        raise WorkflowPathError("ARTIFACT_NOT_ALLOWED", "directory download forbidden")
    return resolved
