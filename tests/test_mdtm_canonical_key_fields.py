# -*- coding: utf-8 -*-
from document_ai.domain_packs.ec_sw.canonical_key_fields import (
    columns_by_role,
    detect_canonical_key_fields,
)


def test_detect_roles_order_independent():
    headers_a = ["요구사항", "설명", "설계", "시험", "비고"]
    headers_b = ["시험", "설계", "요구사항", "설명", "비고"]
    rows = [
        ["Req. 11", "desc", "5.1.2", "TC-11", "note"],
        ["Req. 10", "desc2", "5.1.1", "TC-10", ""],
    ]
    fa = detect_canonical_key_fields(headers_a, rows)
    fb = detect_canonical_key_fields(headers_b, rows)
    ma = columns_by_role(fa)
    mb = columns_by_role(fb)
    assert ma["requirement"]
    assert mb["requirement"]
    # different column indices for requirement
    assert ma["requirement"] != mb["requirement"]


def test_note_column_non_identity():
    fields = detect_canonical_key_fields(
        ["Req", "Design", "Test", "비고"],
        [["Req. 1", "5.1", "TC-1", "ok"]],
    )
    roles = {f.column_index: f.canonical_role for f in fields}
    assert roles[3] == "NON_IDENTITY"
    assert fields[3].used_for_base_identity is False


def test_requirement_header_and_body():
    fields = detect_canonical_key_fields(
        ["Requirement ID", "Other"],
        [["Req. 11", "x"], ["Req. 12", "y"], ["Req. 13", "z"]],
    )
    assert fields[0].canonical_role == "REQUIREMENT_ID"
    assert fields[0].used_for_base_identity is True


def test_empty_header_optional():
    fields = detect_canonical_key_fields(["", "Req"], [["", "Req. 1"]])
    assert fields[0].canonical_role in {"OPTIONAL_KEY", "NON_IDENTITY"}


def test_design_and_test_markers():
    fields = detect_canonical_key_fields(
        ["MDDR 설계", "MDUT 시험"],
        [["5.1.2", "TC-11"], ["5.1.1", "TC-10"]],
    )
    assert fields[0].canonical_role == "DESIGN_ID"
    assert fields[1].canonical_role == "TEST_ID"


def test_low_confidence_does_not_use_single_row_only():
    # single sample should not over-confirm unknown
    fields = detect_canonical_key_fields(["ColA"], [["hello"]])
    assert fields[0].confidence < 0.9


def test_columns_by_role_mapping():
    fields = detect_canonical_key_fields(
        ["요구", "설계", "시험"],
        [["Req. 1", "IA-01", "TC-1"]] * 3,
    )
    m = columns_by_role(fields)
    assert 0 in m["requirement"] or fields[0].canonical_role == "REQUIREMENT_ID"
