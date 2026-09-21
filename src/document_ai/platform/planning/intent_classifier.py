from __future__ import annotations

import re
from typing import Literal

from document_ai.platform.planning.goal_parser import ParsedGoal, is_document_change_path

PlannerIntent = Literal[
    "document_change",
    "operation_analysis",
    "document_generation",
    "security_review",
    "knowledge_query",
]

EXPLICIT_INTENT_ALIASES = {
    "document_change": "document_change",
    "change_request": "document_change",
    "operation_analysis": "operation_analysis",
    "operation_request": "operation_analysis",
    "operation": "operation_analysis",
    "document_generation": "document_generation",
    "generate": "document_generation",
    "security_review": "security_review",
    "security": "security_review",
    "knowledge_query": "knowledge_query",
    "knowledge": "knowledge_query",
    "hybrid": "document_change",
}

OPERATION_PATTERNS = (
    re.compile(r"\bgpu\b", re.IGNORECASE),
    re.compile(r"\bdocker\b", re.IGNORECASE),
    re.compile(r"\bnvidia\b", re.IGNORECASE),
    re.compile(r"\bcuda\b", re.IGNORECASE),
    re.compile(r"\boom\b", re.IGNORECASE),
    re.compile(r"\bxid\b", re.IGNORECASE),
    re.compile(r"\bserver\b", re.IGNORECASE),
    re.compile(r"\blogs?\b", re.IGNORECASE),
    re.compile(r"\bincident\b", re.IGNORECASE),
    re.compile(r"서버"),
    re.compile(r"장애"),
    re.compile(r"로그(?!인)"),
)

SECURITY_PATTERNS = (
    re.compile(r"\bsecurity\b", re.IGNORECASE),
    re.compile(r"\bxxcs\b", re.IGNORECASE),
    re.compile(r"\bia-\d+", re.IGNORECASE),
    re.compile(r"\bsi-\d+", re.IGNORECASE),
    re.compile(r"보안"),
    re.compile(r"취약"),
)

GENERATION_PATTERNS = (
    re.compile(r"\bgenerate\b", re.IGNORECASE),
    re.compile(r"\brender\b", re.IGNORECASE),
    re.compile(r"\bmdsr\b", re.IGNORECASE),
    re.compile(r"\bmddr\b", re.IGNORECASE),
    re.compile(r"문서\s*생성"),
    re.compile(r"양식\s*작성"),
)

KNOWLEDGE_PATTERNS = (
    re.compile(r"\bknowledge\b", re.IGNORECASE),
    re.compile(r"\btraceability\b", re.IGNORECASE),
    re.compile(r"영향\s*분석"),
    re.compile(r"impact\s*query", re.IGNORECASE),
    re.compile(r"\bkg\b", re.IGNORECASE),
    re.compile(r"지식\s*그래프"),
)

DOCUMENT_CHANGE_PATTERNS = (
    re.compile(r"\brequirement\b", re.IGNORECASE),
    re.compile(r"\breq\.?\s*\d+", re.IGNORECASE),
    re.compile(r"요구사항"),
    re.compile(r"변경"),
    re.compile(r"\bchange\b", re.IGNORECASE),
)


def detect_operation_intent(text: str) -> bool:
    return any(pattern.search(text) for pattern in OPERATION_PATTERNS)


def detect_document_change_intent(parsed_goal: ParsedGoal) -> bool:
    if is_document_change_path(parsed_goal.change):
        return True
    return any(pattern.search(parsed_goal.combined_text) for pattern in DOCUMENT_CHANGE_PATTERNS)


def detect_hybrid_intent(parsed_goal: ParsedGoal) -> bool:
    return detect_document_change_intent(parsed_goal) and detect_operation_intent(parsed_goal.combined_text)


def _match_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def classify_intent(parsed_goal: ParsedGoal) -> PlannerIntent:
    if parsed_goal.explicit_intent:
        alias = EXPLICIT_INTENT_ALIASES.get(parsed_goal.explicit_intent.strip().lower())
        if alias:
            return alias  # type: ignore[return-value]

    if parsed_goal.metadata.get("harness") == "operation":
        return "operation_analysis"

    text = parsed_goal.combined_text

    if is_document_change_path(parsed_goal.change) and not detect_operation_intent(text):
        return "document_change"

    if detect_hybrid_intent(parsed_goal):
        return "document_change"

    if _match_any(text, OPERATION_PATTERNS):
        return "operation_analysis"
    if _match_any(text, SECURITY_PATTERNS):
        return "security_review"
    if _match_any(text, GENERATION_PATTERNS):
        return "document_generation"
    if _match_any(text, KNOWLEDGE_PATTERNS):
        return "knowledge_query"
    if detect_document_change_intent(parsed_goal):
        return "document_change"

    return "knowledge_query"
