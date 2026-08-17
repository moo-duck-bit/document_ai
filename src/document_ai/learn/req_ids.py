from __future__ import annotations

import re
from typing import Any

REQ_DOT_PATTERN = re.compile(r"Req\.?\s*(\d+)", re.IGNORECASE)
REQ_KOREAN_PATTERN = re.compile(r"요구사항\s*(\d+)", re.IGNORECASE)
PREFIX_ID_PATTERN = re.compile(r"^(FR|NFR|TC|IA|UC|SI|DC|RA)-(\d+)$", re.IGNORECASE)
FR_NFR_INLINE = re.compile(r"\b(FR|NFR)-(\d+)\b", re.IGNORECASE)
TC_INLINE = re.compile(r"\bTC-(\d+)\b", re.IGNORECASE)
REQ_INLINE = re.compile(r"\bReq\.?\s*(\d+)\b", re.IGNORECASE)
SECURITY_PREFIXES = frozenset({"IA", "UC", "SI", "DC", "RA"})


def normalize_requirement_id(text: str) -> str | None:
    raw = text.strip()
    if not raw:
        return None

    match = REQ_DOT_PATTERN.search(raw)
    if match:
        return f"Req. {int(match.group(1))}"

    match = REQ_KOREAN_PATTERN.search(raw)
    if match:
        return f"Req. {int(match.group(1))}"

    compact = raw.upper().replace(" ", "")
    for candidate in (raw, compact):
        m = PREFIX_ID_PATTERN.match(candidate)
        if m:
            prefix = m.group(1).upper()
            number = int(m.group(2))
            if prefix in {"FR", "NFR", "TC"}:
                return f"{prefix}-{number:02d}"
            if prefix in SECURITY_PREFIXES:
                return f"{prefix}-{number:02d}"
            return f"{prefix}-{number}"

    return None


def parse_linked_ids(linked: str) -> list[str]:
    if not linked or linked.strip().upper() == "N/A":
        return []
    ids: list[str] = []
    for part in re.split(r"[,;/]", linked):
        normalized = normalize_requirement_id(part.strip())
        if normalized and normalized not in ids:
            ids.append(normalized)
    return ids


def requirement_sort_key(req_id: str) -> tuple[str, int, str]:
    normalized = normalize_requirement_id(req_id) or req_id
    match = re.match(r"^([A-Z]+)[-.]?(\d+)$", normalized.replace(". ", "-"))
    if match:
        return (match.group(1), int(match.group(2)), normalized)
    match = REQ_DOT_PATTERN.search(normalized)
    if match:
        return ("REQ", int(match.group(1)), normalized)
    return (normalized, 0, normalized)


def parse_requirement_ids_from_text(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    pattern_builders: tuple[tuple[re.Pattern[str], Any], ...] = (
        (FR_NFR_INLINE, lambda m: f"{m.group(1).upper()}-{int(m.group(2)):02d}"),
        (TC_INLINE, lambda m: f"TC-{int(m.group(1)):02d}"),
        (REQ_INLINE, lambda m: f"Req. {int(m.group(1))}"),
        (REQ_KOREAN_PATTERN, lambda m: f"Req. {int(m.group(1))}"),
    )
    for pattern, builder in pattern_builders:
        for match in pattern.finditer(text):
            matches.append((match.start(), builder(match)))

    matches.sort(key=lambda item: item[0])
    found: list[str] = []
    for _, token in matches:
        if token not in found:
            found.append(token)
    return found
