# -*- coding: utf-8 -*-
"""Generic concept normalization (no external models, deterministic)."""

from __future__ import annotations

import re
from typing import Iterable

# Canonical concepts
SCHEDULE = "SCHEDULE"
TABLE = "TABLE"
MILESTONE = "MILESTONE"
TIMELINE = "TIMELINE"
EXECUTION_PLAN = "EXECUTION_PLAN"
AUTHENTICATION = "AUTHENTICATION"
ACCESS_CONTROL = "ACCESS_CONTROL"
SECURITY = "SECURITY"
USER = "USER"
REQUIREMENT_INTENT = "REQUIREMENT_INTENT"
METHODOLOGY = "METHODOLOGY"
RESULTS = "RESULTS"
CONCLUSION = "CONCLUSION"
BUDGET = "BUDGET"
RISK = "RISK"
ORGANIZATION = "ORGANIZATION"
RECOMMENDATION = "RECOMMENDATION"
DATA_SOURCE = "DATA_SOURCE"
BACKGROUND = "BACKGROUND"
OBJECTIVES = "OBJECTIVES"
DISCUSSION = "DISCUSSION"
EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
EXPECTED_EFFECT = "EXPECTED_EFFECT"

_SYNONYMS: dict[str, frozenset[str]] = {
    SCHEDULE: frozenset(
        {
            "일정",
            "일정표",
            "추진일정",
            "추진 일정",
            "수행일정",
            "수행 일정",
            "계획일정",
            "계획 일정",
            "schedule",
            "schedules",
            "timeline",
            "타임라인",
        }
    ),
    TIMELINE: frozenset({"timeline", "타임라인", "로드맵", "roadmap"}),
    MILESTONE: frozenset({"마일스톤", "milestone", "milestones", "주요단계", "주요 단계"}),
    TABLE: frozenset({"표", "table", "tables", "일정표", "계획표", "로드맵", "통계표"}),
    EXECUTION_PLAN: frozenset(
        {"수행계획", "수행 계획", "추진계획", "추진 계획", "단계별계획", "단계별 계획", "월별계획", "주차별계획"}
    ),
    AUTHENTICATION: frozenset({"인증", "authentication", "auth", "로그인", "login"}),
    ACCESS_CONTROL: frozenset({"접근통제", "접근 통제", "accesscontrol", "access control", "권한", "인가"}),
    SECURITY: frozenset({"보안", "security", "secure"}),
    USER: frozenset({"사용자", "user", "users"}),
    REQUIREMENT_INTENT: frozenset({"요구", "요구사항", "requirement", "requirements", "변경", "change", "수정"}),
    METHODOLOGY: frozenset({"방법론", "methodology", "접근 방식", "approach"}),
    RESULTS: frozenset({"결과", "results", "핵심 발견", "findings"}),
    CONCLUSION: frozenset({"결론", "conclusion", "conclusions"}),
    BUDGET: frozenset({"예산", "budget", "비용", "cost", "사업비", "소요 예산", "금액", "단가"}),
    RISK: frozenset({"위험", "리스크", "risk", "risks", "위험관리", "위험 관리", "mitigation"}),
    ORGANIZATION: frozenset(
        {"조직", "organization", "인력", "수행조직", "수행 조직", "역할 분담", "추진 체계"}
    ),
    EXPECTED_EFFECT: frozenset(
        {"기대효과", "기대 효과", "expected outcomes", "outcomes"}
    ),
    RECOMMENDATION: frozenset({"권고", "권고사항", "recommendation"}),
    DATA_SOURCE: frozenset({"데이터 출처", "data source", "자료출처"}),
    BACKGROUND: frozenset({"배경", "background"}),
    OBJECTIVES: frozenset({"목표", "objective", "objectives", "목적"}),
    DISCUSSION: frozenset({"논의", "discussion"}),
    EXECUTIVE_SUMMARY: frozenset({"요약", "executive summary", "개요"}),
}

_TIME_UNIT_RE = re.compile(
    r"(?:"
    r"\bQ[1-4]\b|"
    r"\b20\d{2}\b|"
    r"\b20\d{2}-Q[1-4]\b|"
    r"\b20\d{2}-\d{1,2}\b|"
    r"[1-9]\d*\s*주차|"
    r"주차별|"
    r"월별|"
    r"분기|"
    r"\b타임라인\b"
    r")",
    re.IGNORECASE,
)


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _synonym_hit(text_low: str, compact: str, syn: str) -> bool:
    """Match synonyms without false hits from short Hangul substrings (e.g. 표 in 표지/목표)."""
    s = (syn or "").lower().strip()
    if not s:
        return False
    if " " in s:
        return s in text_low
    # Multi-char ASCII / long Hangul: allow compact substring
    if len(s) >= 2 and all("a" <= ch <= "z" or ch.isdigit() for ch in s):
        return s in compact or bool(re.search(rf"\b{re.escape(s)}\b", text_low))
    if len(s) >= 3:
        return s in compact or s in text_low
    # Short Hangul (1–2 chars): require token boundary — not embedded in longer token
    # Tokens are sequences of Hangul/alnum length >= 1 for boundary check
    tokens = re.findall(r"[a-z0-9가-힣]+", text_low)
    if s in tokens:
        return True
    # Allow exact phrase when spaced (이미 tokenized away) or whole compact equals syn
    if compact == s:
        return True
    return False


def normalize_concepts(text: str) -> set[str]:
    """Return canonical concepts present in text (token-boundary aware for short synonyms)."""
    raw = text or ""
    low = _norm_space(raw)
    compact = low.replace(" ", "")
    found: set[str] = set()
    for concept, syns in _SYNONYMS.items():
        for syn in syns:
            if _synonym_hit(low, compact, syn):
                found.add(concept)
                break
    return found


def extract_time_unit_hits(text: str) -> list[str]:
    return [m.group(0) for m in _TIME_UNIT_RE.finditer(text or "")]


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9가-힣]{2,}", (text or "").lower()))


def concept_overlap(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))
