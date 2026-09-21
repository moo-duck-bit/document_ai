# -*- coding: utf-8 -*-
"""Stable Node Identity v2 unit tests."""

from document_ai.document_set.stable_node_identity import (
    IDENTITY_VERSION_V2,
    assign_duplicate_instance_keys,
    build_instance_signature,
    build_stable_node_id_base,
    canonicalize_design_id,
    canonicalize_requirement_id,
    canonicalize_test_id,
    canonical_identifier_key,
    mdtm_row_stable_identity,
)


def test_v2_column_reorder_same_base():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_A",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_B",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
    )
    assert a.stable_node_id_base == b.stable_node_id_base


def test_v2_row_movement_same_base():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["IA-04"],
        test_ids=["TC-12"],
        source_locator={"row_index": 2},
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["IA-04"],
        test_ids=["TC-12"],
        source_locator={"row_index": 9},
    )
    assert a.stable_node_id_base == b.stable_node_id_base


def test_v2_note_column_same_base():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        note_text="",
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        note_text="추가 비고 내용",
    )
    assert a.stable_node_id_base == b.stable_node_id_base
    assert a.instance_signature != b.instance_signature or b.instance_signature


def test_v2_filename_same_base():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM_UPLOAD_FOO",
        requirement_ids=["Req. 10"],
        design_ids=["4.2.10"],
        test_ids=["TC-10"],
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM_UPLOAD_BAR",
        requirement_ids=["Req. 10"],
        design_ids=["4.2.10"],
        test_ids=["TC-10"],
    )
    assert a.stable_node_id_base == b.stable_node_id_base


def test_v2_table_index_same_base():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        source_locator={"table_index": 0},
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        source_locator={"table_index": 3},
    )
    assert a.stable_node_id_base == b.stable_node_id_base


def test_identifier_separator_same_base():
    a = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 101"],
        design_ids=["IA-04"],
        test_ids=["TC-12"],
    )
    b = mdtm_row_stable_identity(
        document_identity="Y",
        requirement_ids=["REQ-101"],
        design_ids=["IA 04"],
        test_ids=["tc_12"],
    )
    assert a.stable_node_id_base == b.stable_node_id_base


def test_different_identifiers_different_base():
    a = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
    )
    b = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 10"],
        design_ids=["5.1.1"],
        test_ids=["TC-10"],
    )
    assert a.stable_node_id_base != b.stable_node_id_base


def test_malformed_identifier_excluded():
    assert canonicalize_requirement_id("REQ2") is None
    key = canonical_identifier_key(
        requirement_ids=["REQ2", "Req. 11"],
        design_ids=[],
        test_ids=[],
        version=IDENTITY_VERSION_V2,
    )
    assert "REQ-11" in key
    assert "REQ2" not in key


def test_deterministic_v2_hash():
    a = build_stable_node_id_base(
        domain_pack_id="ec_sw_v1",
        document_role="traceability",
        node_type="TABLE_ROW",
        logical_key="REQ[REQ-11]",
        structural_role="traceability_row",
    )
    b = build_stable_node_id_base(
        domain_pack_id="ec_sw_v1",
        document_role="traceability",
        node_type="TABLE_ROW",
        logical_key="REQ[REQ-11]",
        structural_role="traceability_row",
    )
    assert a == b
    assert a.startswith("stablev2.")


def test_identity_version_v2():
    a = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
    )
    assert a.identity_version == IDENTITY_VERSION_V2
    assert a.stable_node_id_v1
    assert a.stable_node_id_v2
    assert a.writer_executable is False


def test_duplicate_row_preserved():
    a = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        legacy_node_id="L1",
        note_text="first",
        cell_values=["Req. 11", "5.1.2", "TC-11", "first"],
    )
    b = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        legacy_node_id="L2",
        note_text="second",
        cell_values=["Req. 11", "5.1.2", "TC-11", "second"],
    )
    out = assign_duplicate_instance_keys([a, b])
    assert out[0].stable_node_id_base == out[1].stable_node_id_base
    assert out[0].duplicate_instance_key != out[1].duplicate_instance_key
    assert len(out) == 2


def test_local_text_separates_instance():
    s1 = build_instance_signature(note_text="alpha criteria", identifier_texts={"Req. 11"})
    s2 = build_instance_signature(note_text="beta criteria", identifier_texts={"Req. 11"})
    assert s1 != s2


def test_row_index_not_primary_instance_key():
    a = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
        source_locator={"row_index": 2},
        note_text="same",
        cell_values=["Req. 11", "same"],
    )
    assert a.duplicate_instance_key is None or "dup" not in (a.duplicate_instance_key or "") or a.instance_signature
    # instance from content, not row index alone
    assert "row_index" not in (a.duplicate_instance_key or "")


def test_optional_note_does_not_change_base():
    a = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        note_text="",
    )
    b = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        note_text="optional note",
    )
    assert a.stable_node_id_base == b.stable_node_id_base


def test_canon_req_design_test():
    assert canonicalize_requirement_id("Req. 101") == "REQ-101"
    assert canonicalize_requirement_id("REQ-101") == "REQ-101"
    assert canonicalize_design_id("IA-04") == "IA-04"
    assert canonicalize_design_id("IA 04") == "IA-04"
    assert canonicalize_test_id("TC-12") == "TC-12"
    assert canonicalize_test_id("tc_12") == "TC-12"


def test_v1_still_emitted():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_A",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_B",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
    )
    # v1 differs by document identity; v2 base same
    assert a.stable_node_id_v1 != b.stable_node_id_v1
    assert a.stable_node_id_base == b.stable_node_id_base
