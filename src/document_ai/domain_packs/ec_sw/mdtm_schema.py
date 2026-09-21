# -*- coding: utf-8 -*-
"""MDTM column/row schema helpers."""

from __future__ import annotations

import re
from typing import Any

REQ_RE = re.compile(r"Req\.?\s*(\d+)", re.IGNORECASE)
# Design-ish section refs like 4.2.1, 5.2.2 (not Req.)
DESIGN_SECTION_RE = re.compile(r"\b\d+\.\d+(?:\.\d+)*\b")
# Unit-test style refs often appear as 4.1.1.1 — keep as test_ids when from MDUT column
IA_RE = re.compile(r"\bIA-\d+\b", re.IGNORECASE)
TC_RE = re.compile(r"\bTC-?\d+\b", re.IGNORECASE)
UC_RE = re.compile(r"\bUC-\d+\b", re.IGNORECASE)
SI_RE = re.compile(r"\bSI-\d+\b", re.IGNORECASE)

HEADER_MARKERS = {
    "requirement": ("req", "mds r", "mdsr", "요구", "requirement"),
    "design": ("mddr", "design", "설계"),
    "test": ("mdut", "test", "시험", "unit"),
    "vv": ("mdvv", "vv", "검증", "유효"),
}


def normalize_req_id(text: str) -> str | None:
    """Normalize a single token/span; rejects glued forms like REQ2."""
    from document_ai.domain_packs.ec_sw.identifier_parser import parse_requirement_identifiers

    for p in parse_requirement_identifiers(text or "", source="normalize"):
        if p.status in {"VALID_EXACT", "VALID_NORMALIZED"} and p.canonical_id:
            return p.canonical_id
    return None


def extract_requirement_ids(text: str) -> list[str]:
    """Extract only VALID_EXACT / VALID_NORMALIZED requirement IDs (canonical form)."""
    from document_ai.domain_packs.ec_sw.identifier_parser import valid_canonical_requirement_ids

    return valid_canonical_requirement_ids(text or "")


def extract_design_ids(text: str) -> list[str]:
    found: list[str] = []
    for m in IA_RE.finditer(text or ""):
        v = m.group(0).upper()
        if v not in found:
            found.append(v)
    # section-style design refs (exclude those that are clearly "5.1 Req.x" leftovers handled elsewhere)
    for m in DESIGN_SECTION_RE.finditer(text or ""):
        v = m.group(0)
        if v not in found:
            found.append(v)
    return found


def extract_test_ids(text: str) -> list[str]:
    found: list[str] = []
    for rx in (TC_RE, UC_RE, SI_RE, IA_RE):
        for m in rx.finditer(text or ""):
            v = m.group(0).upper().replace("TC", "TC-") if False else m.group(0).upper()
            # normalize TC12 -> TC-12 lightly
            if v.startswith("TC") and not v.startswith("TC-") and len(v) > 2 and v[2:].isdigit():
                v = f"TC-{v[2:]}"
            if v not in found:
                found.append(v)
    # MDUT section numbers
    for m in DESIGN_SECTION_RE.finditer(text or ""):
        v = m.group(0)
        if v not in found:
            found.append(v)
    return found


def guess_column_roles(header_cells: list[str]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for idx, raw in enumerate(header_cells):
        h = (raw or "").strip().lower()
        role = "UNKNOWN"
        status = "UNKNOWN"
        evidence: list[str] = []
        if not h:
            roles.append(
                {
                    "column_index": idx,
                    "header": raw,
                    "role": role,
                    "status": status,
                    "evidence": evidence,
                }
            )
            continue
        scores = {k: 0 for k in HEADER_MARKERS}
        for role_name, markers in HEADER_MARKERS.items():
            for m in markers:
                if m in h:
                    scores[role_name] += 1
                    evidence.append(f"marker:{m}")
        best = max(scores, key=lambda k: scores[k])
        if scores[best] >= 1:
            role = {
                "requirement": "requirement",
                "design": "design",
                "test": "test",
                "vv": "vv",
            }[best]
            # Keyword alone → CANDIDATE, never CONFIRMED
            status = "CANDIDATE"
            if scores[best] >= 2 or ("ec-sw-" in h and scores[best] >= 1):
                status = "CANDIDATE"
        roles.append(
            {
                "column_index": idx,
                "header": raw,
                "role": role,
                "status": status,
                "evidence": evidence,
            }
        )
    return roles


def refine_roles_with_body(
    column_roles: list[dict[str, Any]],
    sample_rows: list[list[str]],
) -> list[dict[str, Any]]:
    """Promote CANDIDATE→CONFIRMED when body cells consistently match ID patterns."""
    out = []
    for col in column_roles:
        idx = col["column_index"]
        role = col["role"]
        status = col["status"]
        cells = [(r[idx] if idx < len(r) else "") for r in sample_rows]
        nonempty = [c for c in cells if c.strip()]
        if role == "requirement" or (
            status in {"UNKNOWN", "CANDIDATE"}
            and nonempty
            and sum(1 for c in nonempty if REQ_RE.search(c)) / max(len(nonempty), 1) >= 0.6
        ):
            if sum(1 for c in nonempty if REQ_RE.search(c)) / max(len(nonempty), 1) >= 0.6:
                role = "requirement"
                status = "CONFIRMED"
        elif role == "design" and nonempty:
            # design column often section numbers without Req.
            ratio = sum(
                1 for c in nonempty if DESIGN_SECTION_RE.search(c) and not REQ_RE.search(c)
            ) / max(len(nonempty), 1)
            if ratio >= 0.5:
                status = "CONFIRMED"
                role = "design"
        elif role == "test" and nonempty:
            ratio = sum(1 for c in nonempty if DESIGN_SECTION_RE.search(c) or TC_RE.search(c)) / max(
                len(nonempty), 1
            )
            if ratio >= 0.5:
                status = "CONFIRMED"
                role = "test"
        elif role == "UNKNOWN" and nonempty:
            # left-most req-heavy column
            if sum(1 for c in nonempty if REQ_RE.search(c)) / max(len(nonempty), 1) >= 0.6:
                role = "requirement"
                status = "CONFIRMED"
        out.append({**col, "role": role, "status": status})
    return out
