# -*- coding: utf-8 -*-
"""PR-23: Build physical location candidates from DocumentModel."""

from __future__ import annotations

from document_ai.document_parser.structure import DocumentModel, SectionModel
from document_ai.physical_locator.schema import PhysicalLocationCandidate, PhysicalLocatorInput
from document_ai.semantic_locator.text_normalization import normalize_text


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


def build_physical_candidates(
    inp: PhysicalLocatorInput,
    doc: DocumentModel | None,
    *,
    seq_prefix: str = "PLC",
) -> list[PhysicalLocationCandidate]:
    """Enumerate SECTION/HEADING/PARAGRAPH/LIST/TABLE/TABLE_CELL candidates."""
    if doc is None:
        return []
    if doc.document_id != inp.document_id and inp.document_id:
        # still allow if caller mismatched — mark later as invalid via engine
        pass

    by_id = {s.section_id: s for s in doc.sections}
    out: list[PhysicalLocationCandidate] = []
    idx = 0
    char_cursor = 0

    for sec in sorted(doc.sections, key=lambda s: s.order):
        path = _heading_path(sec, by_id)

        # SECTION / HEADING
        for loc_type in ("SECTION", "HEADING"):
            if loc_type == "HEADING" and sec.heading_level <= 0:
                continue
            idx += 1
            out.append(
                PhysicalLocationCandidate(
                    physical_candidate_id=f"{seq_prefix}-{idx:04d}",
                    patch_target_candidate_id=inp.patch_target_candidate_id,
                    document_id=doc.document_id,
                    template_id=inp.template_id,
                    template_node_id=inp.template_node_id,
                    location_type=loc_type,
                    section_id=sec.section_id,
                    heading_path=path,
                    block_id=sec.section_id,
                    character_span=(char_cursor, char_cursor + len(sec.heading or "")),
                    span_kind="ESTIMATED_BLOCK_LOCAL",
                    evidence={
                        "heading_text": sec.heading,
                        "heading_level": sec.heading_level,
                        "document_order": sec.order,
                    },
                )
            )

        # PARAGRAPHS
        for pi, para in enumerate(sec.paragraphs):
            idx += 1
            start = char_cursor
            end = start + len(para.text or "")
            char_cursor = end + 1
            out.append(
                PhysicalLocationCandidate(
                    physical_candidate_id=f"{seq_prefix}-{idx:04d}",
                    patch_target_candidate_id=inp.patch_target_candidate_id,
                    document_id=doc.document_id,
                    template_id=inp.template_id,
                    template_node_id=inp.template_node_id,
                    location_type="PARAGRAPH",
                    section_id=sec.section_id,
                    heading_path=path,
                    paragraph_index=pi,
                    block_id=para.paragraph_id,
                    character_span=(start, end),
                    span_kind="ESTIMATED_BLOCK_LOCAL",
                    evidence={
                        "text": para.text,
                        "normalized_text": normalize_text(para.text),
                        "document_order": sec.order * 1000 + pi,
                    },
                )
            )

        # LISTS
        for li, lst in enumerate(sec.lists):
            idx += 1
            joined = " ".join(lst.items)
            out.append(
                PhysicalLocationCandidate(
                    physical_candidate_id=f"{seq_prefix}-{idx:04d}",
                    patch_target_candidate_id=inp.patch_target_candidate_id,
                    document_id=doc.document_id,
                    template_id=inp.template_id,
                    template_node_id=inp.template_node_id,
                    location_type="LIST",
                    section_id=sec.section_id,
                    heading_path=path,
                    list_index=li,
                    block_id=lst.list_id,
                    character_span=(char_cursor, char_cursor + len(joined)),
                    span_kind="ESTIMATED_BLOCK_LOCAL",
                    evidence={
                        "items": list(lst.items),
                        "ordered": lst.ordered,
                        "document_order": sec.order * 1000 + 100 + li,
                    },
                )
            )

        # TABLES + CELLS
        for ti, tbl in enumerate(sec.tables):
            idx += 1
            out.append(
                PhysicalLocationCandidate(
                    physical_candidate_id=f"{seq_prefix}-{idx:04d}",
                    patch_target_candidate_id=inp.patch_target_candidate_id,
                    document_id=doc.document_id,
                    template_id=inp.template_id,
                    template_node_id=inp.template_node_id,
                    location_type="TABLE",
                    section_id=sec.section_id,
                    heading_path=path,
                    table_index=ti,
                    block_id=tbl.table_id,
                    character_span=None,
                    span_kind="NONE",
                    evidence={
                        "headers": list(tbl.headers),
                        "row_count": len(tbl.rows),
                        "document_order": sec.order * 1000 + 200 + ti,
                    },
                )
            )
            for r_i, row in enumerate(tbl.rows):
                for c_i, cell in enumerate(row):
                    idx += 1
                    out.append(
                        PhysicalLocationCandidate(
                            physical_candidate_id=f"{seq_prefix}-{idx:04d}",
                            patch_target_candidate_id=inp.patch_target_candidate_id,
                            document_id=doc.document_id,
                            template_id=inp.template_id,
                            template_node_id=inp.template_node_id,
                            location_type="TABLE_CELL",
                            section_id=sec.section_id,
                            heading_path=path,
                            table_index=ti,
                            cell_coordinate=(r_i, c_i),
                            block_id=f"{tbl.table_id}:r{r_i}c{c_i}",
                            character_span=(0, len(cell or "")),
                            span_kind="ESTIMATED_BLOCK_LOCAL",
                            evidence={
                                "cell_text": cell,
                                "headers": list(tbl.headers),
                                "document_order": sec.order * 1000 + 300 + ti * 50 + r_i * 10 + c_i,
                                "span_note": "block-local cell span, not document absolute",
                            },
                        )
                    )

    return out
