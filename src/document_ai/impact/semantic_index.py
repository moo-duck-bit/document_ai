# -*- coding: utf-8 -*-
"""B1: Requirement-level indexing for MDSR/MDDR (Trial 2).

Does not read expected_impact.* — indexing is source-document only.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from document_ai.learn.extract_design_items import _design_text_from_item, extract_design_items_docx
from document_ai.learn.req_ids import normalize_requirement_id

REQ_SPLIT = re.compile(r"(?=Req\.\s*\d+\b)", re.IGNORECASE)
REQ_HEAD = re.compile(
    r"^Req\.\s*(\d+)\.?\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")

DOMAIN_KEYWORDS = (
    "로그인",
    "잠금",
    "계정",
    "실패",
    "임계",
    "감사",
    "인증",
    "토큰",
    "관리자",
    "알림",
    "해제",
    "제한",
    "재시도",
    "세션",
    "오류",
    "에러",
    "보안",
)


@dataclass
class RequirementBlock:
    req_id: str
    title: str
    body_text: str
    document_type: str  # MDSR | MDDR
    source_path: str
    source_locator: str
    keywords: list[str] = field(default_factory=list)
    trace_security_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ooxml_plain(docx_path: Path) -> str:
    with ZipFile(docx_path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    plain = re.sub(r"</w:p>", "\n", xml)
    plain = re.sub(r"<[^>]+>", "", plain)
    return (
        plain.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("\r", "")
    )


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def _keywords_from_text(text: str) -> list[str]:
    found: list[str] = []
    for kw in DOMAIN_KEYWORDS:
        if kw in (text or ""):
            found.append(kw)
    # also keep high-signal tokens already in domain sense
    return found


def build_req_to_security(traceability: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Invert security→reqs rows into req_id → [security ids]."""
    mapping: dict[str, set[str]] = {}
    for row in traceability:
        security = normalize_requirement_id(str(row.get("requirement") or "").strip())
        if not security:
            continue
        linked = str(row.get("linked_reqs") or "")
        for part in re.split(r"[,;/]", linked):
            rid = normalize_requirement_id(part.strip())
            if not rid or rid.upper() == "N/A":
                continue
            # normalize Req.6 style
            if re.match(r"^Req\.?\s*\d+$", rid, re.I) or rid.startswith("Req."):
                mapping.setdefault(rid, set()).add(security)
            elif re.match(r"^\d+$", rid):
                mapping.setdefault(f"Req. {rid}", set()).add(security)
    # Also handle "Req.6" without space via normalize
    return {k: sorted(v) for k, v in mapping.items()}


def _parse_mdsr_blocks(plain: str, source_path: Path) -> list[RequirementBlock]:
    chunks = [c.strip() for c in REQ_SPLIT.split(plain) if c.strip()]
    blocks: list[RequirementBlock] = []
    for idx, chunk in enumerate(chunks):
        m = REQ_HEAD.match(chunk)
        if not m:
            continue
        req_id = normalize_requirement_id(f"Req. {m.group(1)}")
        if not req_id:
            continue
        rest = (m.group(2) or "").strip()
        lines = chunk.split("\n")
        title = rest
        if not title and len(lines) > 1:
            title = lines[1].strip()
        # body = full chunk minus first heading line
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else rest
        if title and body.startswith(title):
            # keep title in body for search richness; also store separately
            pass
        blocks.append(
            RequirementBlock(
                req_id=req_id,
                title=title[:200],
                body_text=body,
                document_type="MDSR",
                source_path=str(source_path).replace("\\", "/"),
                source_locator=f"ooxml_req_block:{idx}",
                keywords=_keywords_from_text(f"{title}\n{body}"),
                metadata={"extractor": "ooxml_plain_split"},
            )
        )
    return blocks


def index_mdsr_docx(
    docx_path: Path,
    *,
    traceability: list[dict[str, Any]] | None = None,
) -> list[RequirementBlock]:
    plain = _ooxml_plain(docx_path)
    blocks = _parse_mdsr_blocks(plain, docx_path)
    req_sec = build_req_to_security(traceability or [])
    for b in blocks:
        b.trace_security_ids = req_sec.get(b.req_id, [])
        if b.trace_security_ids:
            b.metadata["traceability_attached"] = True
    return blocks


def index_mddr_docx(
    docx_path: Path,
    *,
    traceability: list[dict[str, Any]] | None = None,
) -> list[RequirementBlock]:
    payload = extract_design_items_docx(docx_path)
    req_sec = build_req_to_security(traceability or [])
    blocks: list[RequirementBlock] = []
    for item in payload.get("items", []):
        req_id = normalize_requirement_id(str(item.get("req_id") or ""))
        if not req_id:
            continue
        title = (item.get("title_suffix") or "").strip()
        body = _design_text_from_item(item)
        locator = (
            f"block_kind={item.get('block_kind')};"
            f"block_index={item.get('block_index')}"
        )
        blocks.append(
            RequirementBlock(
                req_id=req_id,
                title=title[:200],
                body_text=body,
                document_type="MDDR",
                source_path=str(docx_path).replace("\\", "/"),
                source_locator=locator,
                keywords=_keywords_from_text(f"{title}\n{body}"),
                trace_security_ids=req_sec.get(req_id, []),
                metadata={
                    "extractor": "extract_design_items_docx",
                    "section_prefix": item.get("section_prefix") or "",
                },
            )
        )
    return blocks


def dedupe_blocks(blocks: list[RequirementBlock]) -> list[RequirementBlock]:
    """Keep the richest block per (document_type, req_id) — drop TOC stubs."""
    best: dict[tuple[str, str], RequirementBlock] = {}
    for block in blocks:
        key = (block.document_type, block.req_id)
        prev = best.get(key)
        if prev is None:
            best[key] = block
            continue
        prev_len = len(prev.body_text or "") + len(prev.title or "")
        new_len = len(block.body_text or "") + len(block.title or "")
        if new_len > prev_len:
            best[key] = block
    return sorted(best.values(), key=lambda b: (b.document_type, b.req_id))


def index_documents(
    *,
    mdsr_path: Path | None = None,
    mddr_path: Path | None = None,
    traceability: list[dict[str, Any]] | None = None,
) -> list[RequirementBlock]:
    blocks: list[RequirementBlock] = []
    if mdsr_path and mdsr_path.exists():
        blocks.extend(index_mdsr_docx(mdsr_path, traceability=traceability))
    if mddr_path and mddr_path.exists():
        blocks.extend(index_mddr_docx(mddr_path, traceability=traceability))
    return dedupe_blocks(blocks)


def save_index_jsonl(blocks: Iterable[RequirementBlock], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for block in blocks:
            fh.write(json.dumps(block.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_index_jsonl(path: Path) -> list[RequirementBlock]:
    blocks: list[RequirementBlock] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        blocks.append(RequirementBlock(**data))
    return blocks


def load_traceability(requirements_json: Path) -> list[dict[str, Any]]:
    if not requirements_json.exists():
        return []
    payload = json.loads(requirements_json.read_text(encoding="utf-8"))
    return list(payload.get("traceability") or [])
