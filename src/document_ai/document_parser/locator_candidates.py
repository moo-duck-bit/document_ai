# -*- coding: utf-8 -*-
"""PR-20: Rule-based locator candidates (no semantic / embedding / LLM)."""

from __future__ import annotations

from document_ai.document_parser.structure import DocumentModel, LocatorCandidate, SectionModel


def _heading_path(sec: SectionModel, by_id: dict[str, SectionModel]) -> list[str]:
    path: list[str] = []
    cur: SectionModel | None = sec
    guard = 0
    while cur is not None and guard < 64:
        if cur.heading_level > 0 and cur.heading:
            path.append(cur.heading)
        if not cur.parent or cur.parent not in by_id:
            break
        cur = by_id[cur.parent]
        guard += 1
    path.reverse()
    return path


def build_locator_candidates(doc: DocumentModel) -> list[LocatorCandidate]:
    """Generate deterministic locator candidates per section (rule scores only)."""
    by_id = {s.section_id: s for s in doc.sections}
    candidates: list[LocatorCandidate] = []
    idx = 0
    for sec in sorted(doc.sections, key=lambda s: s.order):
        if sec.heading_level <= 0 and not sec.heading:
            continue
        path = _heading_path(sec, by_id)
        name = sec.heading or sec.section_id

        # heading_path candidate
        idx += 1
        path_score = 0.55
        if path:
            path_score += min(0.30, 0.05 * len(path))
        if sec.paragraphs or sec.tables or sec.lists:
            path_score += 0.10
        path_score = round(min(path_score, 1.0), 4)
        candidates.append(
            LocatorCandidate(
                candidate_id=f"LC-{idx:04d}",
                section_id=sec.section_id,
                heading_path=path,
                section_name=name,
                heading_text=sec.heading,
                locator_type="heading_path",
                score=path_score,
                metadata={"heading_level": sec.heading_level},
            )
        )

        # section_name candidate
        idx += 1
        name_score = 0.45 + (0.15 if name else 0.0)
        if sec.metadata.get("source_key"):
            name_score += 0.10
        name_score = round(min(name_score, 1.0), 4)
        candidates.append(
            LocatorCandidate(
                candidate_id=f"LC-{idx:04d}",
                section_id=sec.section_id,
                heading_path=path,
                section_name=name,
                heading_text=sec.heading,
                locator_type="section_name",
                score=name_score,
                metadata={"heading_level": sec.heading_level},
            )
        )

        # heading_text candidate
        idx += 1
        text_score = 0.40 + (0.20 if (sec.heading or "").strip() else 0.0)
        text_score = round(min(text_score, 1.0), 4)
        candidates.append(
            LocatorCandidate(
                candidate_id=f"LC-{idx:04d}",
                section_id=sec.section_id,
                heading_path=path,
                section_name=name,
                heading_text=sec.heading,
                locator_type="heading_text",
                score=text_score,
                metadata={"heading_level": sec.heading_level},
            )
        )

    # Deterministic order: section order already applied; stable by candidate_id
    return sorted(candidates, key=lambda c: c.candidate_id)
