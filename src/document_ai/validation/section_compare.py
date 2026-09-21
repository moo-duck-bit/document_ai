"""Section heading coverage between gold and generated documents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_ai.learn.docx_io import load_document, paragraph_deep_text

SECTION_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.\s+(.+)$")
SKIP_HEADINGS = frozenset({"목차", "table of contents"})


def extract_section_headings(doc_path: Path) -> list[dict[str, str]]:
    doc = load_document(doc_path)
    headings: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in doc.paragraphs:
        text = paragraph_deep_text(paragraph).strip()
        if not text or len(text) > 120:
            continue
        match = SECTION_HEADING_RE.match(text)
        if not match:
            continue
        number = match.group(1)
        title = match.group(2).strip()
        if title.lower() in SKIP_HEADINGS:
            continue
        key = f"{number} {title}"
        if key in seen:
            continue
        seen.add(key)
        headings.append({"number": number, "title": title, "text": text})
    return headings


def compare_sections(
    generated_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    generated_path = generated_path.resolve()
    gold_path = gold_path.resolve()
    gen_sections = extract_section_headings(generated_path)
    gold_sections = extract_section_headings(gold_path)

    gen_keys = {f"{s['number']} {s['title']}" for s in gen_sections}
    gold_keys = {f"{s['number']} {s['title']}" for s in gold_sections}
    matched = gen_keys & gold_keys
    missing_in_generated = sorted(gold_keys - gen_keys)
    extra_in_generated = sorted(gen_keys - gold_keys)

    coverage = len(matched) / len(gold_keys) if gold_keys else 1.0
    return {
        "section_coverage": round(coverage, 3),
        "gold_section_count": len(gold_sections),
        "generated_section_count": len(gen_sections),
        "matched_section_count": len(matched),
        "missing_in_generated": missing_in_generated[:20],
        "extra_in_generated": extra_in_generated[:20],
        "gold_sections": gold_sections[:30],
        "generated_sections": gen_sections[:30],
    }
