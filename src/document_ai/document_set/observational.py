# -*- coding: utf-8 -*-
"""Observational document-set orchestration (does not mutate MDSR/MDDR path)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.document_set.loader import load_document_set_registry
from document_ai.document_set.registry import build_default_pack_registry
from document_ai.domain_packs.ec_sw.mdtm_analyzer import analyze_mdtm_structure
from document_ai.domain_packs.ec_sw.mdtm_change_poc import run_mdtm_change_poc
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.domain_packs.ec_sw.registry_adapter import get_mdtm_descriptor
from document_ai.domain_packs.ec_sw.validation import validate_mdtm_index_payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_document_set_observational(
    *,
    output_dir: Path,
    change_request: str = "",
    requirement_ids: list[str] | None = None,
    impact_results: list[dict[str, Any]] | None = None,
    document_set_mode: str = "registry",
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Run registry load + MDTM index + change POC; write artifacts under output_dir/document_set."""
    root = output_dir / "document_set"
    ec_dir = root / "ec_sw"
    ec_dir.mkdir(parents=True, exist_ok=True)

    loaded = load_document_set_registry(registry_path)
    descriptors = loaded["descriptors"]
    pack_registry = build_default_pack_registry()

    summary = {
        "document_set_mode": document_set_mode,
        "document_set": loaded.get("document_set"),
        "descriptor_count": len(descriptors),
        "enabled_count": sum(1 for d in descriptors if d.enabled),
        "packs": pack_registry.list_pack_ids(),
        "mdtm_included": any(d.short_id == "matrix_mdtm" for d in descriptors),
        "newly_supported": ["MDTM"],
        "note": "Observational path only; MDSR/MDDR actual path unchanged.",
    }
    _write_json(root / "document_descriptors.json", loaded["descriptor_dicts"])
    _write_json(root / "document_set_summary.json", summary)
    _write_json(root / "document_set_validation.json", loaded["validation"])

    mdtm = get_mdtm_descriptor(descriptors)
    if mdtm is None:
        result = {
            "ok": False,
            "summary": summary,
            "error": "mdtm_descriptor_missing",
        }
        _write_json(ec_dir / "mdtm_index_summary.json", result)
        return result

    pack = pack_registry.select_for(mdtm)
    analysis = analyze_mdtm_structure(mdtm.source_path, document_id=mdtm.document_id)
    _write_json(ec_dir / "mdtm_structure_analysis.json", analysis)

    indexed = index_mdtm_document(mdtm, analysis=analysis)
    _write_json(ec_dir / "mdtm_nodes.json", indexed.get("node_dicts") or [])
    _write_json(ec_dir / "mdtm_relation_hints.json", indexed.get("relation_hint_dicts") or [])
    _write_json(ec_dir / "mdtm_index_summary.json", indexed.get("index_summary") or {})
    idx_val = validate_mdtm_index_payload(indexed)
    _write_json(ec_dir / "mdtm_index_validation.json", idx_val)

    change = run_mdtm_change_poc(
        list(indexed.get("nodes") or []),
        change_request=change_request,
        requirement_ids=requirement_ids,
        impact_results=impact_results,
    )
    _write_json(ec_dir / "mdtm_change_candidates.json", change.get("candidate_dicts") or [])
    _write_json(ec_dir / "mdtm_patch_preview.json", change.get("patch_previews") or [])
    _write_json(ec_dir / "mdtm_review_required.json", change.get("review_required") or [])

    ranking = change.get("ranking") or {}
    _write_json(ec_dir / "ec_sw_query_intent.json", change.get("query_intent") or {})
    _write_json(
        ec_dir / "ec_sw_identifier_match_matrix.json",
        ranking.get("identifier_match_matrix") or [],
    )
    _write_json(
        ec_dir / "ec_sw_node_ranking_candidates.json",
        ranking.get("ranking_candidates") or [],
    )
    _write_json(
        ec_dir / "ec_sw_node_ranking_results.json",
        ranking.get("ranking_results") or {},
    )
    _write_json(
        ec_dir / "ec_sw_neighbor_context_analysis.json",
        ranking.get("neighbor_context_analysis") or [],
    )
    _write_json(
        ec_dir / "ec_sw_duplicate_identifier_groups.json",
        ranking.get("duplicate_identifier_groups") or [],
    )
    _write_json(
        ec_dir / "ec_sw_node_ranking_validation.json",
        ranking.get("validation") or {},
    )

    return {
        "ok": True,
        "summary": summary,
        "pack_id": pack.pack_id if pack else None,
        "mdtm_descriptor": mdtm.to_dict(),
        "analysis_status": analysis.get("analysis_status"),
        "index_summary": indexed.get("index_summary"),
        "change_summary": change.get("summary"),
        "query_intent": change.get("query_intent"),
        "ranking_validation": ranking.get("validation"),
        "artifact_dir": str(root).replace("\\", "/"),
    }
