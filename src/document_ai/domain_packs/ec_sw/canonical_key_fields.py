# -*- coding: utf-8 -*-
"""MDTM column role detection for stable identity (order-independent)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from document_ai.domain_packs.ec_sw.mdtm_schema import (
    extract_design_ids,
    extract_requirement_ids,
    extract_test_ids,
)

HEADER_MARKERS = {
    "REQUIREMENT_ID": ("req", "mdsr", "요구", "requirement", "요구사항"),
    "DESIGN_ID": ("mddr", "design", "설계", "ia-"),
    "TEST_ID": ("mdut", "test", "시험", "unit", "tc-", "시험항목"),
    "VERIFICATION_ID": ("mdvv", "vv", "검증", "유효"),
    "NON_IDENTITY": ("비고", "note", "remark", "status", "상태", "결과", "pass", "fail"),
}

CanonicalRole = str  # REQUIREMENT_ID | DESIGN_ID | TEST_ID | VERIFICATION_ID | OPTIONAL_KEY | NON_IDENTITY


@dataclass
class CanonicalKeyField:
    column_index: int
    header_text: str
    canonical_role: CanonicalRole
    confidence: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    used_for_base_identity: bool = False
    used_for_instance_identity: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _header_role(header: str) -> tuple[CanonicalRole, float, list[str]]:
    h = (header or "").strip().lower()
    if not h:
        return "OPTIONAL_KEY", 0.1, ["empty_header"]
    scores: dict[str, int] = {k: 0 for k in HEADER_MARKERS}
    reasons: list[str] = []
    for role, markers in HEADER_MARKERS.items():
        for m in markers:
            if m in h:
                scores[role] += 1
                reasons.append(f"header:{m}")
    best = max(scores, key=lambda k: scores[k])
    if scores[best] <= 0:
        return "OPTIONAL_KEY", 0.2, ["no_header_marker"]
    conf = min(1.0, 0.45 + 0.2 * scores[best])
    if best == "NON_IDENTITY":
        return "NON_IDENTITY", conf, reasons
    return best, conf, reasons


def _body_role_votes(cells: list[str]) -> dict[str, float]:
    nonempty = [c for c in cells if (c or "").strip()]
    if not nonempty:
        return {}
    n = len(nonempty)
    req = sum(1 for c in nonempty if extract_requirement_ids(c)) / n
    des = sum(1 for c in nonempty if extract_design_ids(c) and not extract_requirement_ids(c)) / n
    tes = sum(1 for c in nonempty if extract_test_ids(c) and not extract_requirement_ids(c)) / n
    return {"REQUIREMENT_ID": req, "DESIGN_ID": des, "TEST_ID": tes}


def detect_canonical_key_fields(
    header_cells: list[str],
    sample_rows: list[list[str]] | None = None,
) -> list[CanonicalKeyField]:
    """Detect column roles without relying on display order alone.

    Does not finalize role from a single row value.
    """
    sample_rows = sample_rows or []
    out: list[CanonicalKeyField] = []
    for idx, header in enumerate(header_cells):
        role, conf, reasons = _header_role(header)
        col_cells = [(r[idx] if idx < len(r) else "") for r in sample_rows]
        votes = _body_role_votes(col_cells)
        if votes:
            body_best = max(votes, key=lambda k: votes[k])
            body_score = votes[body_best]
            if body_score >= 0.5:
                if role in {"OPTIONAL_KEY", "NON_IDENTITY"} or conf < 0.6:
                    role = body_best
                    conf = max(conf, 0.55 + 0.4 * body_score)
                    reasons = list(reasons) + [f"body_distribution:{body_best}:{body_score:.2f}"]
                elif role == body_best:
                    conf = min(1.0, conf + 0.25)
                    reasons = list(reasons) + ["header_body_agree"]
                elif body_score >= 0.7 and conf < 0.75:
                    # Conflict — prefer body when strong, mark ambiguous
                    role = body_best
                    conf = 0.55
                    reasons = list(reasons) + ["header_body_conflict_prefer_body"]
        used_base = role in {"REQUIREMENT_ID", "DESIGN_ID", "TEST_ID", "VERIFICATION_ID"} and conf >= 0.45
        used_inst = role in {"NON_IDENTITY", "OPTIONAL_KEY"} or (
            role in {"REQUIREMENT_ID", "DESIGN_ID", "TEST_ID"} and conf < 0.45
        )
        if conf < 0.45 and role not in {"NON_IDENTITY"}:
            reasons = list(reasons) + ["low_confidence_review"]
        out.append(
            CanonicalKeyField(
                column_index=idx,
                header_text=header or "",
                canonical_role=role,
                confidence=round(conf, 4),
                reason_codes=reasons,
                used_for_base_identity=used_base,
                used_for_instance_identity=used_inst or role == "NON_IDENTITY",
            )
        )
    return out


def columns_by_role(fields: list[CanonicalKeyField]) -> dict[str, list[int]]:
    m: dict[str, list[int]] = {
        "requirement": [],
        "design": [],
        "test": [],
        "vv": [],
        "non_identity": [],
    }
    for f in fields:
        if not f.used_for_base_identity and f.canonical_role != "NON_IDENTITY":
            continue
        if f.canonical_role == "REQUIREMENT_ID":
            m["requirement"].append(f.column_index)
        elif f.canonical_role == "DESIGN_ID":
            m["design"].append(f.column_index)
        elif f.canonical_role == "TEST_ID":
            m["test"].append(f.column_index)
        elif f.canonical_role == "VERIFICATION_ID":
            m["vv"].append(f.column_index)
        elif f.canonical_role == "NON_IDENTITY":
            m["non_identity"].append(f.column_index)
    return m


_WS = re.compile(r"\s+")


def normalize_instance_text(text: str) -> str:
    t = _WS.sub(" ", (text or "").strip().lower())
    t = re.sub(r"[^\w가-힣\s.\-_/]", "", t)
    return t
