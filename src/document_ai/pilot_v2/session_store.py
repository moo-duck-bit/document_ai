# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — session workspace + manifest persistence.

Layout under ``data/pilot/real_user_document_pilot/sessions/<session_id>/``::

    input/      session-owned copies of uploaded documents (never the original path)
    requests/   raw request payloads (upload/decision/human-review requests) for audit
    output/     analysis + writer output (workflow mirror, writer copies)
    review/     review item snapshots, decisions, human review record
    metrics/    computed scorecards + timing traces

Original Preservation invariant: nothing under this module ever writes to a path
outside the session's own root, and the *original* upload bytes handed to
``copy_upload_into_session`` are only ever read, never opened for writing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.pilot_v2 import security

REPO = Path(__file__).resolve().parents[3]
DEFAULT_PILOT_ROOT = REPO / "data" / "pilot" / "real_user_document_pilot"
SESSION_SUBDIRS: tuple[str, ...] = ("input", "requests", "output", "review", "metrics")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_pilot_root(root: Path | None = None) -> Path:
    path = root or DEFAULT_PILOT_ROOT
    path.mkdir(parents=True, exist_ok=True)
    (path / "sessions").mkdir(parents=True, exist_ok=True)
    return path


def sessions_root(root: Path | None = None) -> Path:
    return ensure_pilot_root(root) / "sessions"


def manifest_path(root: Path | None = None) -> Path:
    return ensure_pilot_root(root) / "manifest.json"


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.is_file():
        return {"meta": {"name": "real_user_document_pilot", "version": "1.0"}, "sessions": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def register_session_summary(summary: dict[str, Any], *, root: Path | None = None) -> None:
    manifest = load_manifest(root)
    rows = list(manifest.get("sessions") or [])
    sid = summary.get("session_id")
    rows = [r for r in rows if r.get("session_id") != sid]
    rows.append(summary)
    manifest["sessions"] = rows
    manifest.setdefault("meta", {"name": "real_user_document_pilot", "version": "1.0"})
    _write_json(manifest_path(root), manifest)


def list_session_summaries(root: Path | None = None, limit: int = 100) -> list[dict[str, Any]]:
    manifest = load_manifest(root)
    rows = list(manifest.get("sessions") or [])
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows[:limit]


def default_participant_id(root: Path | None = None) -> str:
    """Generate anonymous participant ids in the P001, P002, ... style."""
    existing = {str(r.get("participant_id") or "") for r in list_session_summaries(root, limit=10_000)}
    n = 1
    while f"P{n:03d}" in existing:
        n += 1
    return f"P{n:03d}"


def new_session_id(*, scenario_id: str | None, participant_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    base = security.safe_id(scenario_id or "session", prefix="session")
    part = security.safe_id(participant_id or "anon", prefix="anon", max_len=16)
    return security.safe_id(f"{base}_{part}_{stamp}", prefix="session", max_len=96)


def session_dir(session_id: str, *, root: Path | None = None, must_exist: bool = True) -> Path:
    base = sessions_root(root)
    resolved = security.resolve_session_dir(base, session_id)
    if must_exist and not resolved.is_dir():
        raise FileNotFoundError(f"session not found: {session_id}")
    return resolved


def create_session_workspace(session_id: str, *, root: Path | None = None) -> Path:
    base = sessions_root(root)
    resolved = security.resolve_session_dir(base, session_id)
    if resolved.exists():
        raise FileExistsError(f"session already exists: {session_id}")
    resolved.mkdir(parents=True)
    for sub in SESSION_SUBDIRS:
        (resolved / sub).mkdir(parents=True, exist_ok=True)
    return resolved


def copy_upload_into_session(
    session_root: Path,
    filename: str,
    content: bytes,
    *,
    role: str | None = None,
) -> dict[str, Any]:
    """Validate + copy an uploaded document into session input/ (session copy only)."""
    safe_name, ext = security.validate_upload(filename, content)
    dest = session_root / "input" / safe_name
    dest = security.ensure_within_root(dest, session_root, reason_code="SESSION_PATH_ESCAPE")
    if dest.exists():
        raise security.PilotSecurityError("DUPLICATE_FILENAME", safe_name)
    dest.write_bytes(content)
    digest = sha256_bytes(content)
    return {
        "filename": safe_name,
        "extension": ext,
        "role": role or "custom",
        "path": str(dest).replace("\\", "/"),
        "size_bytes": len(content),
        "sha256": digest,
        "uploaded_at": utc_now(),
    }


def write_trace(
    session_root: Path,
    category: str,
    name: str,
    payload: Any,
    *,
    timestamped: bool = False,
) -> Path:
    if category not in SESSION_SUBDIRS:
        raise security.PilotSecurityError("INVALID_TRACE_CATEGORY", category)
    fname = security.safe_id(name, prefix="trace", max_len=80)
    if timestamped:
        fname = f"{fname}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
    dest = session_root / category / f"{fname}.json"
    dest = security.ensure_within_root(dest, session_root, reason_code="SESSION_PATH_ESCAPE")
    _write_json(dest, payload)
    return dest


def save_session_record(session_root: Path, record: dict[str, Any]) -> Path:
    dest = session_root / "session.json"
    _write_json(dest, record)
    meta = {
        "session_id": record.get("session_id"),
        "scenario_id": record.get("scenario_id"),
        "participant_id": record.get("participant_id"),
        "document_set": record.get("document_set"),
        "status": record.get("status"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }
    _write_json(session_root / "meta.json", meta)
    return dest


def load_session_record(session_root: Path) -> dict[str, Any]:
    path = session_root / "session.json"
    if not path.is_file():
        raise FileNotFoundError(f"session record missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_original_preserved(original_path: Path, expected_sha256: str) -> dict[str, Any]:
    """Check the uploaded source file on disk still matches its upload-time hash."""
    if not original_path.is_file():
        return {"ok": False, "reason": "MISSING", "path": str(original_path)}
    current = sha256_bytes(original_path.read_bytes())
    return {
        "ok": current == expected_sha256,
        "reason": "OK" if current == expected_sha256 else "HASH_MISMATCH",
        "path": str(original_path).replace("\\", "/"),
        "expected_sha256": expected_sha256,
        "actual_sha256": current,
    }
