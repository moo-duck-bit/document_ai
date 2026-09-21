# -*- coding: utf-8 -*-
"""Index MDTM rows as TABLE_ROW DocumentNodes."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from docx import Document

from document_ai.document_set.schema import DocumentDescriptor, DocumentNode, RelationHint
from document_ai.document_set.validation import validate_nodes
from document_ai.document_set.stable_node_identity import (
    IDENTITY_VERSION_V2,
    assign_duplicate_instance_keys,
    build_duplicate_groups,
    build_legacy_to_stable_mapping,
    mdtm_row_stable_identity,
)
from document_ai.domain_packs.ec_sw.canonical_key_fields import (
    columns_by_role,
    detect_canonical_key_fields,
)
from document_ai.domain_packs.ec_sw.mdtm_analyzer import analyze_mdtm_structure
from document_ai.domain_packs.ec_sw.mdtm_schema import (
    extract_design_ids,
    extract_requirement_ids,
    extract_test_ids,
)


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _stable_row_hash(cells: list[str]) -> str:
    blob = "|".join(_norm_space(c).lower() for c in cells)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:10]


def _make_node_id(table_index: int, row_index: int, cells: list[str]) -> str:
    h = _stable_row_hash(cells)
    return f"ec_sw_v1.mdtm.table_{table_index:02d}.row_{row_index:04d}.{h}"


def _column_maps(roles: list[dict[str, Any]]) -> dict[str, list[int]]:
    m: dict[str, list[int]] = {"requirement": [], "design": [], "test": [], "vv": []}
    for r in roles:
        role = r.get("role")
        if role in m:
            m[role].append(int(r["column_index"]))
    return m


def _union_ids_from_cells(cells: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Scan all cells — column-order independent identifier harvest for identity."""
    req_ids: list[str] = []
    design_ids: list[str] = []
    test_ids: list[str] = []
    for c in cells:
        req_ids.extend(extract_requirement_ids(c))
        design_ids.extend(extract_design_ids(c))
        test_ids.extend(extract_test_ids(c))
    return (
        list(dict.fromkeys(req_ids)),
        list(dict.fromkeys(design_ids)),
        list(dict.fromkeys(test_ids)),
    )


def index_mdtm_document(
    descriptor: DocumentDescriptor | None = None,
    *,
    source_path: str | Path | None = None,
    document_id: str = "MDTM",
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(source_path or (descriptor.source_path if descriptor else ""))
    doc_id = document_id if descriptor is None else descriptor.document_id
    role = descriptor.document_role if descriptor else "traceability"
    doc_type = descriptor.document_type if descriptor else "MDTM"

    analysis = analysis or analyze_mdtm_structure(path, document_id=doc_id)
    if analysis.get("analysis_status") == "INVALID" or analysis.get("primary_table_index") is None:
        return {
            "nodes": [],
            "relation_hints": [],
            "index_summary": {
                "document_id": doc_id,
                "row_node_count": 0,
                "status": "INVALID",
                "warnings": analysis.get("warnings") or [],
            },
            "index_validation": validate_nodes([], document_id=doc_id),
            "analysis": analysis,
        }

    primary = int(analysis["primary_table_index"])
    roles = analysis.get("column_role_candidates") or []
    colmap = _column_maps(roles)

    doc = Document(str(path))
    table = doc.tables[primary]

    header_cells: list[str] = []
    sample_rows: list[list[str]] = []
    if len(table.rows) >= 2:
        header_cells = [(c.text or "").strip() for c in table.rows[1].cells]
    elif table.rows:
        header_cells = [(c.text or "").strip() for c in table.rows[0].cells]
    for ri, row in enumerate(table.rows):
        if ri < 2:
            continue
        cells = [(c.text or "").strip() for c in row.cells]
        if any(cells):
            sample_rows.append(cells)
        if len(sample_rows) >= 12:
            break

    key_fields = detect_canonical_key_fields(header_cells, sample_rows)
    key_colmap = columns_by_role(key_fields)
    for k in ("requirement", "design", "test"):
        if key_colmap.get(k):
            colmap[k] = key_colmap[k]
        elif not colmap.get(k):
            if k == "requirement":
                colmap[k] = [0] if header_cells else []
            elif k == "design":
                colmap[k] = [min(3, max(0, len(header_cells) - 1))] if len(header_cells) > 1 else []
            elif k == "test":
                colmap[k] = [min(4, max(0, len(header_cells) - 1))] if len(header_cells) > 2 else []

    nodes: list[DocumentNode] = []
    hints: list[RelationHint] = []
    order = 0
    key_field_dicts = [f.to_dict() for f in key_fields]

    for ri, row in enumerate(table.rows):
        if ri < 2:
            continue
        cells = [(c.text or "").strip() for c in row.cells]
        if not any(cells):
            continue
        joined = " | ".join(cells)

        req_ids: list[str] = []
        design_ids: list[str] = []
        test_ids: list[str] = []
        for ci in colmap.get("requirement") or []:
            if ci < len(cells):
                req_ids.extend(extract_requirement_ids(cells[ci]))
        for ci in colmap.get("design") or []:
            if ci < len(cells):
                design_ids.extend(extract_design_ids(cells[ci]))
        for ci in colmap.get("test") or []:
            if ci < len(cells):
                test_ids.extend(extract_test_ids(cells[ci]))

        u_req, u_des, u_tes = _union_ids_from_cells(cells)
        req_ids = list(dict.fromkeys([*req_ids, *u_req]))
        design_ids = list(dict.fromkeys([*design_ids, *u_des]))
        test_ids = list(dict.fromkeys([*test_ids, *u_tes]))

        req_set = set(req_ids)
        design_ids = [d for d in design_ids if d not in req_set]
        test_ids = [t for t in test_ids if t not in req_set]

        node_id = _make_node_id(primary, ri, cells)
        order += 1
        display = req_ids[0] if req_ids else f"MDTM Trace Row {ri}"

        note_parts: list[str] = []
        for f in key_fields:
            if f.used_for_instance_identity or f.canonical_role == "NON_IDENTITY":
                if f.column_index < len(cells) and cells[f.column_index]:
                    note_parts.append(cells[f.column_index])
        if not note_parts and len(cells) > 3:
            last = cells[-1]
            if last and last not in set(req_ids + design_ids + test_ids):
                note_parts.append(last)
        note_text = " ".join(note_parts)

        stable = mdtm_row_stable_identity(
            document_identity=f"EC_SW_{doc_id}" if not str(doc_id).startswith("EC_SW_") else str(doc_id),
            requirement_ids=req_ids,
            design_ids=design_ids,
            test_ids=test_ids,
            legacy_node_id=node_id,
            source_locator={
                "table_index": primary,
                "row_index": ri,
                "column_count": len(cells),
            },
            note_text=note_text,
            domain_pack_id="ec_sw_v1",
            document_role=role or "traceability",
            cell_values=cells,
            canonical_key_fields=key_field_dicts,
            local_texts=note_parts,
        )
        node = DocumentNode(
            node_id=node_id,
            document_id=doc_id,
            document_type=doc_type,
            document_role=role,
            node_type="TABLE_ROW",
            display_name=display,
            text=joined,
            normalized_text=_norm_space(joined).lower(),
            order=order,
            section_id=f"table_{primary:02d}",
            block_id=f"row_{ri:04d}",
            source_locator={
                "table_index": primary,
                "row_index": ri,
                "column_count": len(cells),
            },
            source_identifiers={
                "trace_row_id": f"MDTM-ROW-{ri:04d}",
                "requirement_ids": req_ids,
                "design_ids": design_ids,
                "test_ids": test_ids,
                "cell_values": cells,
                "stable_node_id": stable.stable_node_id,
                "stable_node_id_base": stable.stable_node_id_base,
                "stable_node_id_v1": stable.stable_node_id_v1,
                "stable_node_id_v2": stable.stable_node_id_v2,
                "logical_key": stable.logical_key,
                "identity_version": stable.identity_version,
                "instance_signature": stable.instance_signature,
            },
            metadata={
                "pack_id": "ec_sw_v1",
                "primary_table": True,
                "legacy_node_id": node_id,
                "stable_node_id": stable.stable_node_id,
                "stable_node_id_base": stable.stable_node_id_base,
                "stable_node_id_v1": stable.stable_node_id_v1,
                "stable_node_id_v2": stable.stable_node_id_v2,
                "stable_identity": stable.to_dict(),
                "instance_signature": stable.instance_signature,
                "logical_identity_resolved": True,
                "physical_location_resolved": True,
                "writer_executable": False,
            },
        )
        nodes.append(node)

        targets = []
        for r in req_ids:
            targets.append({"type": "requirement", "value": r})
        for d in design_ids:
            targets.append({"type": "design", "value": d})
        for t in test_ids:
            targets.append({"type": "test", "value": t})
        if targets:
            hints.append(
                RelationHint(
                    relation_hint_id=f"RH-{order:04d}",
                    source_node_id=node_id,
                    relation_type="TRACE_ROW_CONTAINS",
                    target_identifiers=targets,
                )
            )

    validation = validate_nodes(nodes, document_id=doc_id)
    stables = []
    for n in nodes:
        sid = (n.metadata or {}).get("stable_identity")
        if sid:
            from document_ai.document_set.stable_node_identity import StableNodeIdentity

            fields = StableNodeIdentity.__dataclass_fields__
            stables.append(StableNodeIdentity(**{k: sid[k] for k in fields if k in sid}))
    stables = assign_duplicate_instance_keys(stables)
    by_legacy = {s.legacy_node_id: s for s in stables if s.legacy_node_id}
    for n in nodes:
        s = by_legacy.get(n.node_id)
        if not s:
            continue
        n.metadata["stable_identity"] = s.to_dict()
        n.metadata["duplicate_instance_key"] = s.duplicate_instance_key
        n.metadata["stable_node_id"] = s.stable_node_id
        n.metadata["stable_node_id_base"] = s.stable_node_id_base
        n.metadata["instance_signature"] = s.instance_signature
        n.source_identifiers["duplicate_instance_key"] = s.duplicate_instance_key
        n.source_identifiers["stable_node_id"] = s.stable_node_id
        n.source_identifiers["stable_node_id_base"] = s.stable_node_id_base
    legacy_map = build_legacy_to_stable_mapping(stables)
    dup_groups = build_duplicate_groups(stables)
    v1_v2 = [
        {
            "legacy_node_id": s.legacy_node_id,
            "stable_node_id_v1": s.stable_node_id_v1,
            "stable_node_id_v2": s.stable_node_id_v2,
            "stable_node_id_base": s.stable_node_id_base,
            "logical_key": s.logical_key,
        }
        for s in stables
    ]

    summary = {
        "document_id": doc_id,
        "source_path": str(path).replace("\\", "/"),
        "primary_table_index": primary,
        "row_node_count": len(nodes),
        "requirement_id_mentions": sum(len(n.source_identifiers.get("requirement_ids") or []) for n in nodes),
        "rows_with_requirement_ids": sum(1 for n in nodes if n.source_identifiers.get("requirement_ids")),
        "rows_with_design_ids": sum(1 for n in nodes if n.source_identifiers.get("design_ids")),
        "rows_with_test_ids": sum(1 for n in nodes if n.source_identifiers.get("test_ids")),
        "relation_hint_count": len(hints),
        "status": "OK" if validation.get("ok") else "REVIEW_REQUIRED",
        "stable_node_count": len(stables),
        "legacy_to_stable_count": len(legacy_map),
        "identity_version": IDENTITY_VERSION_V2,
    }

    return {
        "nodes": nodes,
        "relation_hints": hints,
        "index_summary": summary,
        "index_validation": validation,
        "analysis": analysis,
        "node_dicts": [n.to_dict() for n in nodes],
        "relation_hint_dicts": [h.to_dict() for h in hints],
        "stable_node_identities": [s.to_dict() for s in stables],
        "stable_node_identities_v2": [s.to_dict() for s in stables],
        "legacy_to_stable_node_mapping": legacy_map,
        "canonical_key_fields": key_field_dicts,
        "stable_duplicate_groups": dup_groups,
        "stable_node_identity_comparison_v1_v2": v1_v2,
    }
