# -*- coding: utf-8 -*-
"""Tests for Trial 2 B1–B2 semantic index/retrieve (no expected leakage)."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_ai.impact.semantic_index import (
    index_documents,
    load_traceability,
    save_index_jsonl,
    load_index_jsonl,
)
from document_ai.impact.semantic_retrieve import retrieve_candidates, score_block

TRIAL1_REF = Path("data/trials/trial-001-mindrium-xa/reference")
CASE_REQ = Path("data/cases/mindrium_xa/requirements.json")
CR = Path("data/trials/trial-002-lockout-multireq/input/change_request.txt")


@pytest.fixture(scope="module")
def mindrium_blocks():
    if not TRIAL1_REF.exists():
        pytest.skip("trial-001 reference missing")
    mdsr = next(TRIAL1_REF.glob("spec_mdsr*.docx"), None)
    mddr = next(TRIAL1_REF.glob("spec_mddr*.docx"), None)
    if not mdsr or not mddr:
        pytest.skip("Mindrium reference docx missing")
    trace = load_traceability(CASE_REQ)
    return index_documents(mdsr_path=mdsr, mddr_path=mddr, traceability=trace)


def test_b1_index_contains_focus_reqs(mindrium_blocks):
    ids = {(b.req_id, b.document_type) for b in mindrium_blocks}
    assert ("Req. 6", "MDSR") in ids
    assert ("Req. 105", "MDSR") in ids or ("Req. 105", "MDDR") in ids
    assert ("Req. 103", "MDSR") in ids or ("Req. 103", "MDDR") in ids
    # source reference preserved
    for b in mindrium_blocks:
        assert b.source_path
        assert b.source_locator
        assert b.document_type in {"MDSR", "MDDR"}


def test_b1_req105_body_has_lock_signal(mindrium_blocks):
    hits = [b for b in mindrium_blocks if b.req_id == "Req. 105"]
    assert hits
    blob = "\n".join(f"{b.title}\n{b.body_text}" for b in hits)
    assert any(k in blob for k in ("잠금", "임계", "로그인", "인증 실패", "실패"))


def test_b1_jsonl_roundtrip(mindrium_blocks, tmp_path):
    path = tmp_path / "idx.jsonl"
    save_index_jsonl(mindrium_blocks[:5], path)
    loaded = load_index_jsonl(path)
    assert len(loaded) == 5
    assert loaded[0].req_id == mindrium_blocks[0].req_id


def test_b2_cr_has_no_exact_ids():
    text = CR.read_text(encoding="utf-8")
    for banned in ("Req. 6", "Req. 103", "Req. 105", "Req.6", "Req.103", "Req.105"):
        assert banned not in text


def test_b2_retrieval_includes_req105(mindrium_blocks):
    cr = CR.read_text(encoding="utf-8")
    cands = retrieve_candidates(cr, mindrium_blocks, top_k=15)
    assert cands
    ids = [c.candidate_id for c in cands]
    assert "Req. 105" in ids
    # each candidate has required fields
    top = cands[0]
    assert top.rank == 1
    assert top.score > 0
    assert top.document in {"MDSR", "MDDR"}
    assert top.retrieval_reason
    assert top.matched_evidence is not None


def test_b2_does_not_need_expected_file(mindrium_blocks, monkeypatch):
    """Retrieval API has no expected_impact parameter — structural guarantee."""
    import inspect
    from document_ai.impact import semantic_retrieve as mod

    sig = inspect.signature(mod.retrieve_candidates)
    assert "expected" not in sig.parameters
    assert "expected_impact" not in sig.parameters
    cr = CR.read_text(encoding="utf-8")
    cands = retrieve_candidates(cr, mindrium_blocks, top_k=5)
    assert len(cands) <= 5
