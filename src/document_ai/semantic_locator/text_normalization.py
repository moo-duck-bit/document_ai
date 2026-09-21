# -*- coding: utf-8 -*-
"""PR-21: Deterministic text normalization (local only)."""

from __future__ import annotations

import re
import unicodedata

_PAREN_RE = re.compile(r"[\[\(\{（【].*?[\]\)\}）】]")
_NUM_PREFIX_RE = re.compile(r"^\s*\d+[.)]\s*")
_NON_ALNUM_RE = re.compile(r"[^\w가-힣]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_text(text: str | None) -> str:
    """Normalize Korean/English text for deterministic matching."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = s.strip().lower()
    s = _PAREN_RE.sub(" ", s)
    s = _NUM_PREFIX_RE.sub("", s)
    s = s.replace("_", " ")
    s = _NON_ALNUM_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def tokenize(text: str | None) -> list[str]:
    norm = normalize_text(text)
    if not norm:
        return []
    return [t for t in norm.split(" ") if t]


def normalize_path(path: list[str] | None) -> list[str]:
    return [normalize_text(p) for p in (path or []) if normalize_text(p)]
