# -*- coding: utf-8 -*-
"""Tests for B4 consistency gate + B5 propagation planning."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_ai.impact.consistency_gate import check_consistency, parse_requirement_fields
from document_ai.impact.propagation import build_propagation_plan, proposed_mdsr_description
from document_ai.impact.semantic_index import RequirementBlock, load_index_jsonl

TRIAL = Path("data/trials/trial-002-lockout-multireq")
CR = TRIAL / "input" / "change_request.txt"
IDX = TRIAL / "retrieval" / "lexical_baseline" / "index_all.jsonl"


@pytest.fixture(scope="module")
def cr_text():
    return CR.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def blocks():
    path = IDX if IDX.exists() else TRIAL / "retrieval" / "index_all.jsonl"
    if not path.exists():
        pytest.skip("index missing")
    return load_index_jsonl(path)


def _block(blocks, rid, doc="MDSR"):
    for b in blocks:
        if b.req_id == rid and b.document_type == doc:
            return b
    pytest.skip(f"missing {rid} {doc}")


def test_parse_fields_req6(blocks):
    b = _block(blocks, "Req. 6")
    fields = parse_requirement_fields(b)
    assert "안내" in fields.title
    assert fields.description
    assert fields.purpose
    assert fields.criteria


def test_req6_conflict_blocks_trial1_pattern(blocks, cr_text):
    d = check_consistency(cr_text, _block(blocks, "Req. 6"), b3_judgment="IMPACTED")
    assert d.status == "CONFLICT"
    assert d.allow_auto_patch is False
    assert d.conflict_evidence_spans
    assert proposed_mdsr_description(d, cr_text) is None


def test_req105_consistent(blocks, cr_text):
    d = check_consistency(cr_text, _block(blocks, "Req. 105"), b3_judgment="IMPACTED")
    assert d.status == "CONSISTENT"
    assert d.allow_auto_patch is True
    text = proposed_mdsr_description(d, cr_text)
    assert text and ("계정 잠금" in text or "변경 요청 반영" in text)


def test_req103_consistent_audit_extension(blocks, cr_text):
    d = check_consistency(cr_text, _block(blocks, "Req. 103"), b3_judgment="IMPACTED")
    assert d.status == "CONSISTENT"
    assert d.allow_auto_patch is True


def test_propagation_req6_skipped(blocks, cr_text):
    cons = [
        check_consistency(cr_text, _block(blocks, "Req. 6"), b3_judgment="IMPACTED"),
        check_consistency(cr_text, _block(blocks, "Req. 103"), b3_judgment="IMPACTED"),
        check_consistency(cr_text, _block(blocks, "Req. 105"), b3_judgment="IMPACTED"),
    ]
    traces = build_propagation_plan(cr_text, cons, blocks)
    by_id = {t.source_mdsr_req_id: t for t in traces}
    assert by_id["Req. 6"].outcome == "SKIPPED_WITH_REASON"
    assert by_id["Req. 103"].outcome in {"PATCHED", "SKIPPED_WITH_REASON"}
    assert by_id["Req. 105"].outcome in {"PATCHED", "SKIPPED_WITH_REASON"}
    # ID alone is not enough — alignment flag recorded
    assert "design_responsibility_aligned" in by_id["Req. 105"].to_dict()


def test_impacted_not_enough_without_fields():
    cr = "연속 로그인 실패 시 계정 잠금 및 자동 해제"
    block = RequirementBlock(
        req_id="Req. 6",
        title="서버와의 통신 중 인증 관련 에러 발생 시 사용자 안내",
        body_text="설명\n인증 에러 안내\n목적\n사용자 혼란 방지\n기준\n에러 메시지 표시",
        document_type="MDSR",
        source_path="x",
        source_locator="t",
        keywords=[],
    )
    d = check_consistency(cr, block, b3_judgment="IMPACTED")
    assert d.status == "CONFLICT"
