# -*- coding: utf-8 -*-
"""Stable node reference matching policies."""

from __future__ import annotations

from document_ai.evaluation.document_set.node_evaluation import (
    StableNodeReference,
    match_stable_reference,
)


def test_exact_node_id():
    r = match_stable_reference(
        predicted_node_id="n1",
        predicted_meta={},
        gold_node_id="n1",
    )
    assert r["matched"] and r["policy"] == "EXACT_NODE_ID"


def test_exact_via_acceptable():
    r = match_stable_reference(
        predicted_node_id="alt",
        predicted_meta={},
        gold_node_id="n1",
        acceptable_node_ids=["alt"],
    )
    assert r["matched"] and r["policy"] == "EXACT_NODE_ID"


def test_stable_locator_fallback():
    ref = StableNodeReference(
        document_id="MDTM",
        node_type="TABLE_ROW",
        source_locator={"table_index": 3, "row_index": 2},
    ).to_dict()
    r = match_stable_reference(
        predicted_node_id="different_hash_id",
        predicted_meta={
            "document_id": "MDTM",
            "node_type": "TABLE_ROW",
            "source_locator": {"table_index": 3, "row_index": 2},
        },
        gold_node_id="original_id",
        stable_ref=ref,
    )
    assert r["matched"] and r["policy"] == "STABLE_LOCATOR"


def test_identifier_match_fallback():
    ref = {"document_id": "MDTM", "identifier_values": ["Req. 101"], "fallback_match_policy": ["IDENTIFIER_MATCH"]}
    r = match_stable_reference(
        predicted_node_id="x",
        predicted_meta={"matched_identifiers": ["Req. 101"]},
        gold_node_id="y",
        stable_ref=ref,
    )
    assert r["matched"] and r["policy"] == "IDENTIFIER_MATCH"


def test_text_hash_match():
    ref = {
        "normalized_text_hash": "abc123",
        "fallback_match_policy": ["TEXT_HASH_MATCH"],
    }
    r = match_stable_reference(
        predicted_node_id="x",
        predicted_meta={"normalized_text_hash": "abc123"},
        gold_node_id="y",
        stable_ref=ref,
    )
    assert r["matched"] and r["policy"] == "TEXT_HASH_MATCH"


def test_wrong_document_reject():
    ref = StableNodeReference(
        document_id="MDTM",
        section_id="schedule",
        source_locator={"table_index": 1},
    ).to_dict()
    r = match_stable_reference(
        predicted_node_id="n",
        predicted_meta={
            "document_id": "OTHER",
            "section_id": "schedule",
            "source_locator": {"table_index": 1},
        },
        gold_node_id="want",
        stable_ref=ref,
    )
    # STABLE_LOCATOR skipped due to wrong doc; EXACT fails → unmatched
    assert r["matched"] is False


def test_wrong_node_type_reject():
    ref = StableNodeReference(
        document_id="MDTM",
        node_type="TABLE_ROW",
        source_locator={"table_index": 1, "row_index": 0},
    ).to_dict()
    r = match_stable_reference(
        predicted_node_id="n",
        predicted_meta={
            "document_id": "MDTM",
            "node_type": "SECTION",
            "source_locator": {"table_index": 1, "row_index": 0},
        },
        gold_node_id="want",
        stable_ref=ref,
    )
    assert r["matched"] is False


def test_acceptable_group_policy():
    r = match_stable_reference(
        predicted_node_id="s2",
        predicted_meta={},
        gold_node_id="s1",
        acceptable_groups=[["s1", "s2"]],
        stable_ref={"fallback_match_policy": ["ACCEPTABLE_GROUP"]},
    )
    assert r["matched"] and r["policy"] == "ACCEPTABLE_GROUP"


def test_no_free_semantic_similarity():
    r = match_stable_reference(
        predicted_node_id="totally_different",
        predicted_meta={"score": 0.99, "reason": "semantic"},
        gold_node_id="gold",
        stable_ref={"document_id": "D"},
    )
    assert r["matched"] is False
