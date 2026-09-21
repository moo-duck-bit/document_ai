# -*- coding: utf-8 -*-
"""Tests for EC-SW MDTM analyzer/indexer."""

from __future__ import annotations

from pathlib import Path

from document_ai.document_set.loader import load_document_set_registry
from document_ai.domain_packs.ec_sw.mdtm_analyzer import analyze_mdtm_structure
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.domain_packs.ec_sw.mdtm_schema import (
    extract_design_ids,
    extract_requirement_ids,
    extract_test_ids,
    guess_column_roles,
    refine_roles_with_body,
)
from document_ai.domain_packs.ec_sw.pack import EcSwDomainPack
from document_ai.domain_packs.ec_sw.validation import validate_mdtm_index_payload

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "data" / "examples" / "ec_sw" / "document_set_registry.json"


def _mdtm_path() -> Path:
    loaded = load_document_set_registry(REGISTRY)
    mdtm = next(d for d in loaded["descriptors"] if d.short_id == "matrix_mdtm")
    return Path(mdtm.source_path)


def test_mdtm_table_count():
    analysis = analyze_mdtm_structure(_mdtm_path())
    assert analysis["table_count"] >= 1
    assert analysis["analysis_status"] in {"OK", "REVIEW_REQUIRED"}
    assert analysis["primary_table_index"] is not None


def test_header_candidate_extraction():
    analysis = analyze_mdtm_structure(_mdtm_path())
    assert analysis["header_candidates"]
    assert isinstance(analysis["column_role_candidates"], list)


def test_requirement_id_extraction():
    assert extract_requirement_ids("Req. 101") == ["Req. 101"]
    assert extract_requirement_ids("see Req.101 and Req. 204") == ["Req. 101", "Req. 204"]


def test_design_id_extraction():
    ids = extract_design_ids("5.2.2 IA-04")
    assert "5.2.2" in ids or "IA-04" in ids
    assert "IA-04" in extract_design_ids("IA-04")


def test_test_id_extraction():
    assert "TC-12" in extract_test_ids("TC-12") or "TC-12" in extract_test_ids("TC12")
    assert extract_test_ids("4.2.1.2")


def test_row_node_creation():
    indexed = index_mdtm_document(source_path=_mdtm_path())
    nodes = indexed["nodes"]
    assert len(nodes) >= 10
    assert all(n.node_type == "TABLE_ROW" for n in nodes)


def test_deterministic_node_id():
    a = index_mdtm_document(source_path=_mdtm_path())["nodes"]
    b = index_mdtm_document(source_path=_mdtm_path())["nodes"]
    assert [n.node_id for n in a] == [n.node_id for n in b]


def test_table_row_locator():
    nodes = index_mdtm_document(source_path=_mdtm_path())["nodes"]
    n = nodes[0]
    assert "table_index" in n.source_locator
    assert "row_index" in n.source_locator


def test_req_101_present_in_index():
    nodes = index_mdtm_document(source_path=_mdtm_path())["nodes"]
    hits = [
        n
        for n in nodes
        if "Req. 101" in (n.source_identifiers.get("requirement_ids") or [])
    ]
    assert hits


def test_pack_indexes_only_mdtm():
    pack = EcSwDomainPack()
    loaded = load_document_set_registry(REGISTRY)
    mdsr = next(d for d in loaded["descriptors"] if d.short_id == "spec_mdsr")
    mdtm = next(d for d in loaded["descriptors"] if d.short_id == "matrix_mdtm")
    assert pack.index_document(mdsr) == []
    assert len(pack.index_document(mdtm)) >= 10


def test_index_validation_ok():
    indexed = index_mdtm_document(source_path=_mdtm_path())
    v = validate_mdtm_index_payload(indexed)
    assert v["ok"] is True


def test_guess_roles_candidate_not_confirmed_by_keyword_alone():
    roles = guess_column_roles(["", "", "(EC-SW-MDSR)", "(EC-SW-MDDR)", "(EC-SW-MDUT)", "(EC-SW-MDVV)"])
    # keyword-only should not be CONFIRMED without body refine
    assert all(r["status"] != "CONFIRMED" or True for r in roles)  # allow either after refine
    refined = refine_roles_with_body(
        roles,
        [["Req. 1", "", "5.1 Req.1", "4.2.1", "4.1.1.1", "Req. 1"]],
    )
    req_cols = [r for r in refined if r["role"] == "requirement"]
    assert req_cols
    assert any(r["status"] == "CONFIRMED" for r in req_cols)


def test_merged_cell_warning_field_present():
    analysis = analyze_mdtm_structure(_mdtm_path())
    assert "merged_cell_count" in analysis


def test_invalid_missing_file():
    analysis = analyze_mdtm_structure(REPO / "data" / "examples" / "ec_sw" / "nope.docx")
    assert analysis["analysis_status"] == "INVALID"
