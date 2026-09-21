# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — security guards.

Covers: path traversal, extension allowlist, upload size limit, session-root
escape, source/copy collision, and text sanitization. Reuses the ``_safe`` id
pattern already used by ``document_ai.workflow.orchestrator``.
"""

from __future__ import annotations

import re
from pathlib import Path

ALLOWED_UPLOAD_EXTENSIONS: frozenset[str] = frozenset({".docx"})
MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024  # 25MB
MAX_TEXT_LEN: int = 20_000


class PilotSecurityError(ValueError):
    def __init__(self, reason_code: str, message: str = ""):
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}" if message else reason_code)


def safe_id(name: str, *, prefix: str = "pilot", max_len: int = 64) -> str:
    """Sanitize an arbitrary string into a filesystem-safe identifier segment."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip())
    cleaned = cleaned.strip("-._")
    return (cleaned or prefix)[:max_len]


def safe_filename(filename: str | None) -> str:
    """Return the basename only; reject filenames carrying traversal segments."""
    raw = str(filename or "")
    if not raw.strip():
        raise PilotSecurityError("INVALID_FILENAME", "empty filename")
    normalized = raw.replace("\\", "/")
    if ".." in normalized.split("/"):
        raise PilotSecurityError("PATH_TRAVERSAL_BLOCKED", raw)
    if normalized.startswith("/") or (len(normalized) >= 2 and normalized[1] == ":"):
        raise PilotSecurityError("PATH_TRAVERSAL_BLOCKED", raw)
    name = Path(normalized).name
    if not name or name in {".", ".."}:
        raise PilotSecurityError("INVALID_FILENAME", raw)
    return name


def validate_extension(
    filename: str, *, allowed: frozenset[str] = ALLOWED_UPLOAD_EXTENSIONS
) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise PilotSecurityError("UNSUPPORTED_EXTENSION", ext or "(none)")
    return ext


def validate_upload_size(content: bytes, *, max_bytes: int = MAX_UPLOAD_BYTES) -> int:
    size = len(content or b"")
    if size <= 0:
        raise PilotSecurityError("EMPTY_DOCUMENT", "0 bytes")
    if size > max_bytes:
        raise PilotSecurityError("FILE_TOO_LARGE", f"{size} > {max_bytes}")
    return size


def validate_upload(filename: str, content: bytes) -> tuple[str, str]:
    """Full upload guard: filename traversal + extension allowlist + size limit."""
    name = safe_filename(filename)
    ext = validate_extension(name)
    validate_upload_size(content)
    return name, ext


def ensure_within_root(
    path: Path, root: Path, *, reason_code: str = "PATH_ESCAPE_BLOCKED"
) -> Path:
    """Resolve ``path`` and assert it stays inside ``root`` (session root escape guard)."""
    root_r = root.resolve()
    resolved = path.resolve()
    if resolved != root_r and root_r not in resolved.parents:
        raise PilotSecurityError(reason_code, str(resolved))
    return resolved


def resolve_session_dir(sessions_root: Path, session_id: str) -> Path:
    """Sanitize ``session_id`` and guarantee the resolved dir stays under sessions_root."""
    raw = str(session_id or "")
    if not raw or ".." in raw.replace("\\", "/").split("/") or "/" in raw or "\\" in raw:
        cleaned = safe_id(raw, prefix="session")
        if cleaned != raw:
            raise PilotSecurityError("SESSION_PATH_ESCAPE", raw)
    candidate = sessions_root / raw
    return ensure_within_root(candidate, sessions_root, reason_code="SESSION_PATH_ESCAPE")


def assert_source_copy_distinct(source: Path, copy: Path) -> None:
    """Guard against a session copy accidentally aliasing its source upload path."""
    if source.resolve() == copy.resolve():
        raise PilotSecurityError("SOURCE_COPY_COLLISION", str(source))


def assert_not_original_path(
    target: Path, *, forbidden_roots: tuple[Path, ...]
) -> None:
    """Guard the writer against ever targeting a source upload / frozen path."""
    resolved = target.resolve()
    for forbidden in forbidden_roots:
        forbidden_r = forbidden.resolve()
        if resolved == forbidden_r or forbidden_r in resolved.parents:
            raise PilotSecurityError("WRITE_TARGET_FORBIDDEN", str(resolved))


def sanitize_text(text: str, *, max_len: int = MAX_TEXT_LEN) -> str:
    cleaned = (text or "").replace("\x00", "").strip()
    return cleaned[:max_len]


def resolve_artifact_path(
    session_root: Path, relative: str, *, allowed_subdirs: frozenset[str]
) -> Path:
    """Session-scoped artifact resolution for downloads (no traversal, allowlisted subdir)."""
    raw = (relative or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or ".." in raw.split("/"):
        raise PilotSecurityError("PATH_TRAVERSAL_BLOCKED", raw)
    parts = [p for p in raw.split("/") if p]
    if not parts or parts[0] not in allowed_subdirs:
        raise PilotSecurityError("ARTIFACT_NOT_ALLOWED", raw)
    candidate = session_root.joinpath(*parts)
    resolved = ensure_within_root(candidate, session_root, reason_code="ARTIFACT_OUTSIDE_SESSION_ROOT")
    if not resolved.exists() or resolved.is_dir():
        raise PilotSecurityError("ARTIFACT_NOT_FOUND", raw)
    return resolved
