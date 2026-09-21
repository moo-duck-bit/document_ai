# -*- coding: utf-8 -*-
from document_ai.document_set.stable_node_identity import (
    IDENTITY_VERSION,
    assign_duplicate_instance_keys,
    build_legacy_to_stable_mapping,
    build_stable_node_id,
    canonical_identifier_key,
    mdtm_row_stable_identity,
    section_stable_identity,
)


def test_canonical_identifier_ordering_independence():
    a = canonical_identifier_key(
        requirement_ids=["Req. 11", "Req. 10"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
    )
    b = canonical_identifier_key(
        requirement_ids=["Req. 10", "Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
    )
    assert a == b


def test_deterministic_stable_id():
    a = build_stable_node_id(
        document_identity="EC_SW_MDTM",
        node_type="TABLE_ROW",
        logical_key="REQ[REQ. 11]",
        structural_role="traceability_row",
    )
    b = build_stable_node_id(
        document_identity="EC_SW_MDTM",
        node_type="TABLE_ROW",
        logical_key="REQ[REQ. 11]",
        structural_role="traceability_row",
    )
    assert a == b
    assert IDENTITY_VERSION in "stable_node_identity_v1"


def test_different_semantic_row_different_id():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 10"],
        design_ids=["5.1.1"],
        test_ids=["TC-10"],
    )
    assert a.stable_node_id != b.stable_node_id


def test_identity_version_recorded():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
    )
    assert a.identity_version in {IDENTITY_VERSION, "stable_node_identity_v2"}
    assert a.stable_node_id_v1


def test_writer_not_executable_by_stable_alone():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
        source_locator={"row_index": 2},
    )
    assert a.writer_executable is False
    assert a.physical_location_resolved is True


def test_duplicate_rows_preserved():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        legacy_node_id="L1",
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        legacy_node_id="L2",
    )
    out = assign_duplicate_instance_keys([a, b])
    assert out[0].stable_node_id == out[1].stable_node_id
    assert out[0].duplicate_instance_key != out[1].duplicate_instance_key


def test_legacy_mapping_deterministic():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
        legacy_node_id="LEGACY1",
    )
    m = build_legacy_to_stable_mapping([a])
    assert m[0]["legacy_node_id"] == "LEGACY1"
    assert m[0]["stable_node_id"] == a.stable_node_id


def test_note_text_does_not_change_core_stable_id():
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
        note_text="비고 내용",
    )
    assert a.stable_node_id == b.stable_node_id


def test_row_index_excluded_from_logical_key():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
        source_locator={"row_index": 2},
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11"],
        design_ids=[],
        test_ids=[],
        source_locator={"row_index": 99},
    )
    assert a.stable_node_id == b.stable_node_id
    assert "row_index_excluded" in a.reason_codes
