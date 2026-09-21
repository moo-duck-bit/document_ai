"""Evidence sanitization, persistence, and hashing."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from document_ai.security_runner.models import EvidenceRecord

SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
    }
)
TOKEN_PATTERN = re.compile(
    r"(bearer\s+)[A-Za-z0-9._~+/=-]+|"
    r"(token|api[_-]?key|secret|password)\s*[=:]\s*[^,\s;]+",
    re.IGNORECASE,
)


def mask_sensitive_headers(headers: dict[str, Any]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for name, value in headers.items():
        lowered = str(name).lower()
        if lowered in SENSITIVE_HEADER_NAMES:
            sanitized[str(name)] = "[REDACTED]"
        else:
            sanitized[str(name)] = TOKEN_PATTERN.sub("[REDACTED]", str(value))
    return sanitized


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).lower() in SENSITIVE_HEADER_NAMES
                else sanitize_metadata(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, str):
        return TOKEN_PATTERN.sub("[REDACTED]", value)
    return value


def body_summary(body: bytes, *, content_type: str, truncated: bool) -> dict[str, Any]:
    return {
        "bytes_observed": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "content_type": content_type,
        "truncated": truncated,
        "body_stored": False,
    }


def write_evidence_json(
    evidence_dir: Path,
    filename: str,
    payload: dict[str, Any],
    *,
    output_parent: Path,
    description: str,
) -> EvidenceRecord:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / filename
    sanitized = sanitize_metadata(payload)
    serialized = json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(serialized + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        relative = path.resolve().relative_to(output_parent.resolve())
        path_text = str(relative).replace("\\", "/")
    except ValueError:
        path_text = path.name
    return EvidenceRecord(
        type="file",
        path=path_text,
        description=description,
        sha256=digest,
    )


def write_manifest(
    evidence_dir: Path,
    *,
    execution_id: str,
    records: list[EvidenceRecord],
    metrics: dict[str, Any],
) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "execution_id": execution_id,
                "evidence": [record.to_execution_dict() for record in records],
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
