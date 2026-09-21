# -*- coding: utf-8 -*-
"""EC-SW requirement identifier parser with validity status."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ReqIdStatus = Literal[
    "VALID_EXACT",
    "VALID_NORMALIZED",
    "AMBIGUOUS",
    "MALFORMED",
    "NOT_FOUND",
]

# Valid forms require a clear separator between Req/REQ and digits.
# Use ASCII alnum boundaries so Korean suffixes (e.g. "Req. 1과") still match.
_VALID_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![A-Za-z0-9])Req\.\s*(\d+)(?![A-Za-z0-9])", re.IGNORECASE), "REQ_ID_EXACT"),
    (re.compile(r"(?<![A-Za-z0-9])Req\s+(\d+)(?![A-Za-z0-9])", re.IGNORECASE), "REQ_ID_NORMALIZED"),
    (re.compile(r"(?<![A-Za-z0-9])REQ-(\d+)(?![A-Za-z0-9])", re.IGNORECASE), "REQ_ID_NORMALIZED"),
    (re.compile(r"(?<![A-Za-z0-9])REQ\.(\d+)(?![A-Za-z0-9])", re.IGNORECASE), "REQ_ID_NORMALIZED"),
]

# Malformed / incomplete (checked after valid spans are reserved)
_MALFORMED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![A-Za-z0-9])Req\.\s*$", re.IGNORECASE | re.MULTILINE), "REQ_ID_NUMBER_MISSING"),
    (re.compile(r"(?<![A-Za-z0-9])Req\.\s+(?!\d)", re.IGNORECASE), "REQ_ID_NUMBER_MISSING"),
    (re.compile(r"(?<![A-Za-z0-9])Req\s+[A-Za-z]+\b", re.IGNORECASE), "REQ_ID_INVALID_CHARACTER"),
    (re.compile(r"(?<![A-Za-z0-9])Req\s+\d+[A-Za-z]+\b", re.IGNORECASE), "REQ_ID_INVALID_CHARACTER"),
    (re.compile(r"(?<![A-Za-z0-9])Req\.\s*\d*[OoIl][\dOoIl]*\b", re.IGNORECASE), "REQ_ID_INVALID_CHARACTER"),
    # REQ2 / Req2 — letters glued to digits without separator
    (re.compile(r"(?<![A-Za-z0-9])REQ(?![.\-\s])(\d+)(?![A-Za-z0-9])", re.IGNORECASE), "REQ_ID_MALFORMED"),
    (re.compile(r"(?<![A-Za-z0-9])Req(?![.\-\s])(\d+)(?![A-Za-z0-9])", re.IGNORECASE), "REQ_ID_MALFORMED"),
]


@dataclass
class ParsedRequirementId:
    raw_text: str
    canonical_id: str | None
    status: ReqIdStatus
    span: tuple[int, int]
    reason_codes: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "change_request"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["span"] = list(self.span)
        return d


def canonicalize_req_number(num: int | str) -> str:
    return f"Req. {int(num)}"


def parse_requirement_identifiers(
    text: str,
    *,
    source: str = "change_request",
) -> list[ParsedRequirementId]:
    """Parse requirement identifiers with explicit validity status."""
    s = text or ""
    results: list[ParsedRequirementId] = []
    occupied: list[tuple[int, int]] = []

    def _overlaps(a: int, b: int) -> bool:
        for x, y in occupied:
            if a < y and b > x:
                return True
        return False

    for rx, reason in _VALID_PATTERNS:
        for m in rx.finditer(s):
            start, end = m.span()
            if _overlaps(start, end):
                continue
            occupied.append((start, end))
            canonical = canonicalize_req_number(m.group(1))
            status: ReqIdStatus = "VALID_EXACT" if reason == "REQ_ID_EXACT" else "VALID_NORMALIZED"
            conf = 1.0 if status == "VALID_EXACT" else 0.92
            results.append(
                ParsedRequirementId(
                    raw_text=m.group(0),
                    canonical_id=canonical,
                    status=status,
                    span=(start, end),
                    reason_codes=[reason],
                    confidence=conf,
                    source=source,
                )
            )

    for rx, reason in _MALFORMED_PATTERNS:
        for m in rx.finditer(s):
            start, end = m.span()
            if _overlaps(start, end):
                continue
            occupied.append((start, end))
            num = None
            if m.lastindex and m.group(1) and str(m.group(1)).isdigit():
                num = int(m.group(1))
            results.append(
                ParsedRequirementId(
                    raw_text=m.group(0),
                    canonical_id=canonicalize_req_number(num) if num is not None else None,
                    status="MALFORMED",
                    span=(start, end),
                    reason_codes=[reason, "REQ_ID_MALFORMED"],
                    confidence=0.2,
                    source=source,
                )
            )

    # Ambiguous: multiple conflicting valid forms for same span region — rare; mark duplicates
    by_canon: dict[str, list[ParsedRequirementId]] = {}
    for r in results:
        if r.canonical_id and r.status in {"VALID_EXACT", "VALID_NORMALIZED"}:
            by_canon.setdefault(r.canonical_id, []).append(r)

    results.sort(key=lambda r: (r.span[0], r.span[1]))
    if not results and s.strip():
        # soft NOT_FOUND marker when Req-like token absent
        if re.search(r"\breq(?:uirement)?\b", s, re.IGNORECASE) and not re.search(
            r"\bReq[\s.\-]?\d|\bREQ[\s.\-]?\d", s, re.IGNORECASE
        ):
            results.append(
                ParsedRequirementId(
                    raw_text="",
                    canonical_id=None,
                    status="AMBIGUOUS",
                    span=(0, 0),
                    reason_codes=["REQ_ID_AMBIGUOUS"],
                    confidence=0.1,
                    source=source,
                )
            )
        else:
            results.append(
                ParsedRequirementId(
                    raw_text="",
                    canonical_id=None,
                    status="NOT_FOUND",
                    span=(0, 0),
                    reason_codes=["REQ_ID_NOT_FOUND"],
                    confidence=0.0,
                    source=source,
                )
            )
    return results


def valid_canonical_requirement_ids(text: str) -> list[str]:
    """Return unique canonical IDs that are VALID_EXACT or VALID_NORMALIZED only."""
    out: list[str] = []
    for p in parse_requirement_identifiers(text):
        if p.status in {"VALID_EXACT", "VALID_NORMALIZED"} and p.canonical_id:
            if p.canonical_id not in out:
                out.append(p.canonical_id)
    return out


def has_malformed_requirement_ids(text: str) -> bool:
    return any(p.status == "MALFORMED" for p in parse_requirement_identifiers(text))
