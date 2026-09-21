# -*- coding: utf-8 -*-
"""EC-SW change-request identifier intent (no gold reads)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.domain_packs.ec_sw.identifier_parser import (
    parse_requirement_identifiers,
    valid_canonical_requirement_ids,
)
from document_ai.domain_packs.ec_sw.mdtm_schema import extract_design_ids, extract_test_ids

PrimaryIdentifierType = Literal["REQUIREMENT", "DESIGN", "TEST", "MIXED", "NONE"]


@dataclass
class QueryIntent:
    raw_change_request: str
    requirement_ids: list[str] = field(default_factory=list)
    design_ids: list[str] = field(default_factory=list)
    test_ids: list[str] = field(default_factory=list)
    identifier_status: str = "NONE"
    primary_identifier_type: PrimaryIdentifierType = "NONE"
    secondary_identifier_types: list[str] = field(default_factory=list)
    semantic_terms: list[str] = field(default_factory=list)
    ambiguity: bool = False
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DESIGN_HINT = re.compile(r"설계|design|mddr", re.IGNORECASE)
_TEST_HINT = re.compile(r"시험|test|mdut|검증", re.IGNORECASE)
_REQ_HINT = re.compile(r"요구|requirement|mdsr|(?<![A-Za-z])req(?![A-Za-z])", re.IGNORECASE)


def _semantic_terms(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9가-힣]{2,}", (text or "").lower())
    stop = {"관련", "검토", "변경", "추적성", "수정", "문서", "및", "또는"}
    return [t for t in toks if t not in stop][:24]


def _norm_design(d: str) -> str:
    s = str(d or "").strip()
    if re.match(r"^[A-Za-z]", s):
        return s.upper()
    return s


def parse_query_intent(
    change_request: str,
    *,
    requirement_ids: list[str] | None = None,
    design_ids: list[str] | None = None,
    test_ids: list[str] | None = None,
) -> QueryIntent:
    """Deterministic identifier intent from CR + optional explicit lists."""
    cr = change_request or ""
    reqs = list(dict.fromkeys([*(requirement_ids or []), *valid_canonical_requirement_ids(cr)]))
    malformed = [
        p
        for p in parse_requirement_identifiers(cr, source="change_request")
        if p.status == "MALFORMED"
    ]

    designs = list(
        dict.fromkeys([_norm_design(d) for d in [*(design_ids or []), *extract_design_ids(cr)]])
    )
    tests = list(
        dict.fromkeys([str(t).upper() for t in [*(test_ids or []), *extract_test_ids(cr)]])
    )

    if _DESIGN_HINT.search(cr) and not _TEST_HINT.search(cr):
        tests = [
            t
            for t in tests
            if t not in designs or t.startswith(("TC-", "UC-", "SI-", "IA-"))
        ]

    kinds: list[str] = []
    if reqs:
        kinds.append("REQUIREMENT")
    if designs:
        kinds.append("DESIGN")
    if tests:
        kinds.append("TEST")

    reasons: list[str] = []
    if malformed:
        reasons.append("malformed_requirement_excluded")

    primary: PrimaryIdentifierType = "NONE"
    secondary: list[str] = []
    ambiguity = False
    status = "NONE"

    if not kinds:
        reasons.append("no_identifier")
    elif len(kinds) == 1:
        primary = kinds[0]  # type: ignore[assignment]
        status = "SINGLE"
        reasons.extend([f"primary_{primary.lower()}", "single_identifier"])
    else:
        status = "MIXED"
        ambiguity = True
        design_hint = bool(_DESIGN_HINT.search(cr))
        test_hint = bool(_TEST_HINT.search(cr))
        req_hint = bool(_REQ_HINT.search(cr))
        if design_hint and "DESIGN" in kinds and not test_hint:
            primary = "DESIGN"
            reasons.append("mixed_with_primary_hint")
        elif test_hint and "TEST" in kinds and not design_hint:
            primary = "TEST"
            reasons.append("mixed_with_primary_hint")
        elif "REQUIREMENT" in kinds and (req_hint or (not design_hint and not test_hint)):
            primary = "REQUIREMENT"
            reasons.append("mixed_with_primary_hint")
        else:
            primary = "MIXED"
            reasons.append("mixed_identifiers")

        if primary == "MIXED":
            secondary = list(kinds)
        else:
            secondary = [k for k in kinds if k != primary]
            reasons.append(f"primary_{primary.lower()}")

    return QueryIntent(
        raw_change_request=cr,
        requirement_ids=reqs,
        design_ids=designs,
        test_ids=tests,
        identifier_status=status,
        primary_identifier_type=primary,
        secondary_identifier_types=secondary,
        semantic_terms=_semantic_terms(cr),
        ambiguity=ambiguity,
        reason_codes=sorted(set(reasons)),
    )
