# -*- coding: utf-8 -*-
"""PR-24: Deterministic observational fingerprints."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_for_fingerprint(
    text: str | None,
    *,
    normalize_whitespace: bool = True,
) -> str:
    """UTF-8 safe normalization with explicit policy.

    - Normalize CRLF/CR → LF
    - Optionally collapse internal whitespace runs to single space and strip
    """
    if text is None:
        return ""
    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    if normalize_whitespace:
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        s = s.strip()
    return s


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint_text(
    text: str | None,
    *,
    normalize_whitespace: bool = True,
) -> dict[str, Any]:
    """Return deterministic fingerprint metadata (never invents when NOT_AVAILABLE)."""
    if text is None:
        return {
            "fingerprint_status": "NOT_AVAILABLE",
            "fingerprint": None,
            "algorithm": "SHA-256",
            "encoding": "UTF-8",
            "normalized_line_endings": True,
            "normalized_whitespace": normalize_whitespace,
        }
    norm = normalize_for_fingerprint(text, normalize_whitespace=normalize_whitespace)
    return {
        "fingerprint_status": "AVAILABLE",
        "fingerprint": sha256_hex(norm),
        "algorithm": "SHA-256",
        "encoding": "UTF-8",
        "normalized_line_endings": True,
        "normalized_whitespace": normalize_whitespace,
        "normalized_length": len(norm),
    }


def compare_fingerprints(
    expected: str | None,
    observed: str | None,
    *,
    fingerprint_status: str = "AVAILABLE",
) -> tuple[str, list[str]]:
    """Return (status, reason_codes) for SOURCE_FINGERPRINT_MATCH."""
    if fingerprint_status == "NOT_AVAILABLE":
        return "NOT_APPLICABLE", ["FINGERPRINT_NOT_AVAILABLE"]
    if fingerprint_status == "STALE":
        return "UNSATISFIED", ["FINGERPRINT_STALE"]
    if expected is None or observed is None:
        return "NOT_APPLICABLE", ["FINGERPRINT_MISSING"]
    if expected == observed:
        return "SATISFIED", ["FINGERPRINT_MATCH"]
    return "UNSATISFIED", ["FINGERPRINT_MISMATCH"]
