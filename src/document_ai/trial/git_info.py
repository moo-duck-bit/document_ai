"""Git / environment snapshot helpers for trials and baselines."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.paths import PROJECT_ROOT


def _run_git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return ""
    return (completed.stdout or "").strip()


def collect_git_info() -> dict[str, Any]:
    head = _run_git("rev-parse", "HEAD")
    short = _run_git("rev-parse", "--short", "HEAD")
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    describe = _run_git("describe", "--tags", "--always", "--dirty")
    tags = _run_git("tag", "--points-at", "HEAD")
    status = _run_git("status", "--porcelain")
    dirty = bool(status)
    return {
        "commit": head,
        "commit_short": short,
        "branch": branch,
        "describe": describe,
        "tags_at_head": [t for t in tags.splitlines() if t.strip()],
        "dirty": dirty,
        "status_porcelain": status.splitlines() if status else [],
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def collect_environment() -> dict[str, Any]:
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "project_root": str(PROJECT_ROOT),
        "env_markers": {
            "CI": os.environ.get("CI", ""),
            "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV", ""),
        },
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def assert_system_version_match(
    *,
    system_version: str,
    system_commit: str,
    git_info: dict[str, Any] | None = None,
    require_clean: bool = False,
) -> list[str]:
    """Return warnings (not hard errors) when freeze expectations differ."""
    info = git_info or collect_git_info()
    warnings: list[str] = []
    commit = str(info.get("commit", ""))
    short = str(info.get("commit_short", ""))
    expected = system_commit.strip().lower()
    if expected and commit:
        if not (commit.lower().startswith(expected) or short.lower().startswith(expected)):
            warnings.append(
                f"system_commit mismatch: expected {system_commit}, got {short or commit}"
            )
    tags = [t.lower() for t in info.get("tags_at_head", [])]
    if system_version and system_version.lower() not in tags and system_version not in str(
        info.get("describe", "")
    ):
        warnings.append(
            f"system_version tag not at HEAD: expected {system_version}, "
            f"tags={info.get('tags_at_head')}, describe={info.get('describe')}"
        )
    if require_clean and info.get("dirty"):
        warnings.append("working tree is dirty; freeze/trial generation should record dirty=true")
    return warnings
