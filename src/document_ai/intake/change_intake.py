from __future__ import annotations

import json
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from document_ai.impact.change import save_change
from document_ai.impact.graph import TraceabilityGraph, normalize_req_id, parse_linked_reqs
from document_ai.learn.req_ids import normalize_requirement_id, parse_requirement_ids_from_text, requirement_sort_key

REQ_PATTERNS = [
    re.compile(r"\b(FR|NFR)-(\d+)\b", re.IGNORECASE),
    re.compile(r"\bTC-(\d+)\b", re.IGNORECASE),
    re.compile(r"Req\.?\s*(\d+)", re.IGNORECASE),
    re.compile(r"요구사항\s*(\d+)", re.IGNORECASE),
]
SECURITY_PATTERN = re.compile(r"\b(IA|UC|SI|DC|RA)-(\d+)\b", re.IGNORECASE)
QUOTED_PATTERN = re.compile(r"[「『\"']([^「『\"']{8,})[」』\"']")
ARROW_PATTERN = re.compile(r"(?:→|->|로\s*변경|을?\s*다음과\s*같이)\s*[:\s]*(.+)", re.IGNORECASE | re.DOTALL)
LABEL_PATTERN = re.compile(
    r"(?:설명|내용|변경\s*내용|요구사항\s*설명)\s*[:：]\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)
REQ_COLON_PATTERN = re.compile(r"Req\.?\s*\d+\s*[:：]\s*(.+)", re.IGNORECASE | re.DOTALL)
FR_COLON_PATTERN = re.compile(r"\b(FR|NFR|TC)-\d+\s*[:：]\s*(.+)", re.IGNORECASE | re.DOTALL)
IMPERATIVE_NOISE = re.compile(
    r"^(?:please\s+)?(?:change|update|modify|변경|수정|업데이트|반영)(?:해\s*줘|해주세요|요)?[.!?\s]*$",
    re.IGNORECASE,
)
NOISE_PREFIX = re.compile(
    r"^(?:please\s+)?(?:change|update|modify|변경|수정|업데이트|반영)[:\s]*",
    re.IGNORECASE,
)


def _unique_req_ids(req_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for req_id in req_ids:
        normalized = normalize_req_id(req_id) if not req_id.startswith("Req.") else req_id
        if not normalized:
            normalized = normalize_req_id(f"Req. {req_id}")
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def parse_req_ids_from_text(text: str) -> list[str]:
    return parse_requirement_ids_from_text(text)


def parse_security_ids_from_text(text: str) -> list[str]:
    found: list[str] = []
    for match in SECURITY_PATTERN.finditer(text):
        token = normalize_requirement_id(f"{match.group(1).upper()}-{match.group(2)}")
        if token and token not in found:
            found.append(token)
    return sorted(found, key=requirement_sort_key)


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", text.lower())
    stop = {"요구사항", "변경", "수정", "설명", "다음", "같이", "반영", "해줘", "please", "change", "update"}
    return {t for t in tokens if t not in stop}


def find_reqs_by_keyword_overlap(text: str, requirements: list[dict[str, Any]], limit: int = 3) -> list[str]:
    query = _tokenize(text)
    if len(query) < 2:
        return []

    scored: list[tuple[float, str]] = []
    for row in requirements:
        req_id = row.get("req_id", "")
        corpus = f"{req_id} {row.get('description', '')}"
        doc_tokens = _tokenize(corpus)
        if not doc_tokens:
            continue
        overlap = len(query & doc_tokens)
        if overlap == 0:
            continue
        score = overlap / max(len(query), 1)
        scored.append((score, req_id))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [req_id for score, req_id in scored[:limit] if score >= 0.2]


def expand_security_ids_to_reqs(security_ids: list[str], traceability: list[dict[str, Any]]) -> list[str]:
    graph = TraceabilityGraph(traceability)
    combined: list[str] = []
    for security_id in security_ids:
        for req_id in graph.security_to_reqs.get(security_id, set()):
            if req_id not in combined:
                combined.append(req_id)
    return combined


def _is_meaningful_description(text: str) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 4:
        return False
    if IMPERATIVE_NOISE.match(cleaned):
        return False
    tokens = _tokenize(cleaned)
    if not tokens:
        return False
    noise_only = tokens <= {"변경", "수정", "해줘", "please", "change", "update", "modify"}
    return not noise_only


def extract_description_text(text: str, req_ids: list[str], security_ids: list[str]) -> str:
    for pattern in (QUOTED_PATTERN, LABEL_PATTERN, ARROW_PATTERN, REQ_COLON_PATTERN):
        match = pattern.search(text)
        if match and match.group(1).strip():
            candidate = match.group(1).strip()
            if _is_meaningful_description(candidate):
                return candidate

    fr_match = FR_COLON_PATTERN.search(text)
    if fr_match and _is_meaningful_description(fr_match.group(2)):
        return fr_match.group(2).strip()

    cleaned = text
    for pattern in REQ_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    for security_id in security_ids:
        cleaned = re.sub(re.escape(security_id), " ", cleaned, flags=re.IGNORECASE)
    cleaned = NOISE_PREFIX.sub("", cleaned.strip())
    cleaned = re.sub(r"^[:：\s]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;")
    if _is_meaningful_description(cleaned):
        return cleaned
    return ""


def draft_change_from_request(
    request_text: str,
    *,
    requirements_payload: dict[str, Any] | None = None,
    explicit_req_id: str | None = None,
    explicit_description: str | None = None,
    summary: str | None = None,
    sync_design_from_requirement: bool = True,
) -> dict[str, Any]:
    text = request_text.strip()
    traceability = (requirements_payload or {}).get("traceability", [])
    requirements = (requirements_payload or {}).get("requirements", [])

    req_ids = parse_req_ids_from_text(text)
    security_ids = parse_security_ids_from_text(text)
    clarifying: list[str] = []

    if explicit_req_id:
        explicit = normalize_req_id(explicit_req_id)
        if explicit and explicit not in req_ids:
            req_ids.insert(0, explicit)

    if security_ids and traceability:
        expanded = expand_security_ids_to_reqs(security_ids, traceability)
        explicit_req_in_text = bool(parse_req_ids_from_text(text))
        if explicit_req_in_text:
            for req_id in expanded:
                if req_id not in req_ids:
                    req_ids.append(req_id)
        elif len(expanded) == 1:
            req_ids = expanded
        elif len(expanded) > 1:
            clarifying_security = (
                f"{', '.join(security_ids)}는 {', '.join(expanded)}에 연결됩니다. "
                "변경할 Req. N을 명시해 주세요."
            )
            if clarifying_security not in clarifying:
                clarifying.append(clarifying_security)

    if not req_ids and requirements:
        req_ids = find_reqs_by_keyword_overlap(text, requirements)

    description = explicit_description or extract_description_text(text, req_ids, security_ids)

    if not req_ids:
        clarifying.append("어떤 Req. N(또는 IA/UC/SI-xx)을 변경할지 알려주세요.")
    if req_ids and not description:
        clarifying.append("변경할 요구사항 설명(description)을 입력해 주세요.")

    requirement_changes = [
        {"req_id": req_id, "description": description}
        for req_id in req_ids
        if description
    ]

    change_id = f"chg-{date.today().isoformat().replace('-', '')}-{uuid.uuid4().hex[:6]}"
    return {
        "change_id": change_id,
        "summary": summary or _default_summary(req_ids, security_ids, text),
        "sync_design_from_requirement": sync_design_from_requirement,
        "intake": {
            "channel": "natural_language",
            "raw_request": text,
            "parsed_req_ids": req_ids,
            "parsed_security_ids": security_ids,
            "confidence": _confidence(req_ids, description, clarifying),
            "clarifying_questions": clarifying,
            "confirmed": not clarifying,
        },
        "requirement_changes": requirement_changes,
    }


def _default_summary(req_ids: list[str], security_ids: list[str], text: str) -> str:
    if req_ids:
        joined = ", ".join(req_ids[:3])
        suffix = f" 외 {len(req_ids) - 3}건" if len(req_ids) > 3 else ""
        return f"{joined}{suffix} 변경"
    if security_ids:
        return f"{', '.join(security_ids)} 연결 요구사항 변경"
    return text[:80]


def _confidence(req_ids: list[str], description: str, clarifying: list[str]) -> float:
    if clarifying:
        return 0.4 if req_ids else 0.2
    if req_ids and description:
        return 0.9 if parse_req_ids_from_text(description) == [] else 0.75
    return 0.5


def append_intake_log(case_dir: Path, entry: dict[str, Any]) -> Path:
    log_path = case_dir / "intake_log.json"
    log: list[dict[str, Any]] = []
    if log_path.exists():
        log = json.loads(log_path.read_text(encoding="utf-8"))
    log.append(entry)
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return log_path


def load_requirements_payload(case_dir: Path) -> dict[str, Any]:
    req_path = case_dir / "requirements.json"
    if not req_path.exists():
        return {"requirements": [], "traceability": []}
    return json.loads(req_path.read_text(encoding="utf-8"))
