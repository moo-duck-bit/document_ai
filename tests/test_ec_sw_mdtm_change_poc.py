# -*- coding: utf-8 -*-
"""Tests for EC-SW MDTM Change POC + safety."""

from __future__ import annotations

import hashlib
from pathlib import Path

from document_ai.document_set.loader import load_document_set_registry
from document_ai.document_set.observational import run_document_set_observational
from document_ai.document_set.schema import DocumentNode
from document_ai.domain_packs.ec_sw.mdtm_change_poc import (
    extract_requirement_ids_from_inputs,
    run_mdtm_change_poc,
)
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "data" / "examples" / "ec_sw" / "document_set_registry.json"
DESKTOP_MDTM = Path.home() / "Desktop" / "EC-SW-MDTM(XA) 추적성 매트릭스.docx"
EXAMPLE_MDTM = None


def _nodes():
    global EXAMPLE_MDTM
    loaded = load_document_set_registry(REGISTRY)
    mdtm = next(d for d in loaded["descriptors"] if d.short_id == "matrix_mdtm")
    EXAMPLE_MDTM = Path(mdtm.source_path)
    return index_mdtm_document(mdtm)["nodes"]


def test_exact_req_patch_candidate():
    result = run_mdtm_change_poc(_nodes(), requirement_ids=["Req. 101"])
    patches = result["patch_candidates"]
    assert patches
    assert all(c["status"] == "PATCH_CANDIDATE" for c in patches)
    assert any("Req. 101" in c["matched_requirement_ids"] for c in patches)


def test_multi_req():
    result = run_mdtm_change_poc(_nodes(), requirement_ids=["Req. 101", "Req. 204"])
    matched = set()
    for c in result["patch_candidates"]:
        matched.update(c["matched_requirement_ids"])
    assert "Req. 101" in matched
    assert "Req. 204" in matched


def test_design_only_review():
    # Use a design id that exists in MDTM body (section style)
    nodes = _nodes()
    # pick a design id from first node if present
    design = None
    for n in nodes:
        ids = n.source_identifiers.get("design_ids") or []
        if ids:
            design = ids[0]
            break
    assert design
    result = run_mdtm_change_poc(nodes, design_ids=[design], requirement_ids=[])
    assert result["summary"]["patch_candidate_count"] == 0
    assert result["summary"]["review_required_count"] >= 1


def test_semantic_only_no_patch():
    result = run_mdtm_change_poc(
        _nodes(),
        change_request="사용자 권한관리 기능을 추가하고 감사 로그를 남긴다",
        requirement_ids=[],
    )
    assert result["summary"]["patch_candidate_count"] == 0
    # may be REVIEW or UNRELATED — never PATCH
    assert all(c["status"] != "PATCH_CANDIDATE" for c in result["candidate_dicts"])


def test_missing_id_no_patch():
    empty = DocumentNode(
        node_id="x",
        document_id="MDTM",
        document_type="MDTM",
        document_role="traceability",
        node_type="TABLE_ROW",
        display_name="empty",
        text="no ids here",
        source_identifiers={"requirement_ids": [], "design_ids": [], "test_ids": []},
        source_locator={"table_index": 0, "row_index": 99},
    )
    result = run_mdtm_change_poc([empty], requirement_ids=["Req. 999"])
    assert result["summary"]["patch_candidate_count"] == 0


def test_duplicate_rows_review_flag():
    n1 = DocumentNode(
        "a",
        "MDTM",
        "MDTM",
        "traceability",
        "TABLE_ROW",
        "Req. 1",
        text="Req. 1",
        source_identifiers={"requirement_ids": ["Req. 1"], "design_ids": [], "test_ids": [], "cell_values": ["Req. 1", ""]},
        source_locator={"table_index": 0, "row_index": 1},
    )
    n2 = DocumentNode(
        "b",
        "MDTM",
        "MDTM",
        "traceability",
        "TABLE_ROW",
        "Req. 1",
        text="Req. 1 again",
        source_identifiers={"requirement_ids": ["Req. 1"], "design_ids": [], "test_ids": [], "cell_values": ["Req. 1", ""]},
        source_locator={"table_index": 0, "row_index": 2},
    )
    result = run_mdtm_change_poc([n1, n2], requirement_ids=["Req. 1"])
    assert result["summary"]["patch_candidate_count"] == 2
    assert all(c["human_review_required"] for c in result["patch_candidates"])
    assert any("duplicate_requirement_rows" in c["reason_codes"] for c in result["patch_candidates"])


def test_patch_preview_no_row_wide_replacement():
    result = run_mdtm_change_poc(_nodes(), requirement_ids=["Req. 101"])
    for prev in result["patch_previews"]:
        assert prev["row_wide_replacement"] is False
        assert prev["operation"] == "UPDATE"
        assert prev["generated_id"] is False
        assert "column_index" in prev


def test_no_new_id_generation():
    result = run_mdtm_change_poc(_nodes(), requirement_ids=["Req. 108"])
    for prev in result["patch_previews"]:
        assert prev.get("generated_id") is False
        # proposed text must not invent Req. 999 style
        assert "Req. 999" not in (prev.get("proposed_text") or "")


def test_extract_from_impact_results():
    ids = extract_requirement_ids_from_inputs(
        impact_results=[
            {"candidate_id": "Req. 101", "judgment": "IMPACTED", "document": "MDSR"},
            {"candidate_id": "Req. 2", "judgment": "NOT_IMPACTED", "document": "MDSR"},
        ]
    )
    assert "Req. 101" in ids


def test_observational_artifacts(tmp_path: Path):
    out = run_document_set_observational(
        output_dir=tmp_path,
        requirement_ids=["Req. 101"],
        document_set_mode="registry",
    )
    assert out["ok"] is True
    root = tmp_path / "document_set" / "ec_sw"
    for name in (
        "mdtm_structure_analysis.json",
        "mdtm_nodes.json",
        "mdtm_relation_hints.json",
        "mdtm_change_candidates.json",
        "mdtm_patch_preview.json",
        "mdtm_review_required.json",
        "mdtm_index_summary.json",
        "mdtm_index_validation.json",
    ):
        assert (root / name).is_file(), name


def test_desktop_untouched_hash():
    if not DESKTOP_MDTM.exists():
        return
    before = hashlib.sha256(DESKTOP_MDTM.read_bytes()).hexdigest()
    _ = run_mdtm_change_poc(_nodes(), requirement_ids=["Req. 101"])
    after = hashlib.sha256(DESKTOP_MDTM.read_bytes()).hexdigest()
    assert before == after


def test_example_copy_untouched_by_poc():
    nodes = _nodes()
    assert EXAMPLE_MDTM is not None
    before = hashlib.sha256(EXAMPLE_MDTM.read_bytes()).hexdigest()
    run_mdtm_change_poc(nodes, requirement_ids=["Req. 101", "Req. 204"])
    after = hashlib.sha256(EXAMPLE_MDTM.read_bytes()).hexdigest()
    assert before == after


def test_invalid_non_row():
    n = DocumentNode("s", "MDTM", "MDTM", "traceability", "SECTION", "sec")
    result = run_mdtm_change_poc([n], requirement_ids=["Req. 1"])
    assert result["invalid_count"] == 1
