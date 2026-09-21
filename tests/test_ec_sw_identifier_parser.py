# -*- coding: utf-8 -*-
"""EC-SW identifier parser tests."""

from __future__ import annotations

from document_ai.domain_packs.ec_sw.identifier_parser import (
    parse_requirement_identifiers,
    valid_canonical_requirement_ids,
)
from document_ai.domain_packs.ec_sw.mdtm_schema import extract_requirement_ids, normalize_req_id


def test_exact_req_dot_space():
    assert valid_canonical_requirement_ids("Req. 101 변경") == ["Req. 101"]
    p = parse_requirement_identifiers("Req. 101")[0]
    assert p.status == "VALID_EXACT"
    assert "REQ_ID_EXACT" in p.reason_codes


def test_exact_req_dot_nospace():
    assert valid_canonical_requirement_ids("see Req.101") == ["Req. 101"]


def test_normalized_req_space():
    p = parse_requirement_identifiers("Req 2 update")[0]
    assert p.status == "VALID_NORMALIZED"
    assert p.canonical_id == "Req. 2"


def test_normalized_req_hyphen():
    assert valid_canonical_requirement_ids("REQ-101") == ["Req. 101"]


def test_normalized_req_dot_prefix():
    assert valid_canonical_requirement_ids("REQ.7") == ["Req. 7"]


def test_malformed_glued_digits():
    ps = parse_requirement_identifiers("REQ2 형식 오류")
    assert any(p.status == "MALFORMED" for p in ps)
    assert valid_canonical_requirement_ids("REQ2 형식 오류") == []
    assert extract_requirement_ids("REQ2 형식 오류") == []


def test_malformed_req2_lowercase_prefix():
    assert extract_requirement_ids("Req2 changes") == []


def test_malformed_missing_number():
    ps = parse_requirement_identifiers("Req.")
    assert any(p.status == "MALFORMED" and "REQ_ID_NUMBER_MISSING" in p.reason_codes for p in ps)


def test_malformed_alphabetic():
    ps = parse_requirement_identifiers("Req ABC")
    assert any(p.status == "MALFORMED" for p in ps)


def test_malformed_alphanumeric_suffix():
    ps = parse_requirement_identifiers("Req 10A")
    assert any(p.status == "MALFORMED" for p in ps)


def test_multiple_valid_ids():
    ids = valid_canonical_requirement_ids("Req. 1과 Req. 3을 수정")
    assert ids == ["Req. 1", "Req. 3"]


def test_valid_plus_malformed_mixed():
    text = "Req. 2 및 REQ9 혼재"
    assert "Req. 2" in valid_canonical_requirement_ids(text)
    assert any(p.status == "MALFORMED" for p in parse_requirement_identifiers(text))


def test_deterministic_spans():
    a = parse_requirement_identifiers("Req. 2 and Req. 3")
    b = parse_requirement_identifiers("Req. 2 and Req. 3")
    assert [p.span for p in a] == [p.span for p in b]


def test_canonicalization():
    assert normalize_req_id("Req 5") == "Req. 5"
    assert normalize_req_id("REQ-5") == "Req. 5"
    assert normalize_req_id("REQ5") is None


def test_not_found_plain_text():
    assert extract_requirement_ids("마케팅 슬로건 XYZABCQUUX") == []
