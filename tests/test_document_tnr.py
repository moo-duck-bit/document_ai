"""Tests for Document-TNR safety contract mapping."""

from __future__ import annotations

from document_ai.safety.document_tnr import (
    ablation_flags,
    assess_severity,
    baseline_from_session,
    map_safety_scorecard_to_mu,
)


def test_map_safety_scorecard_to_mu():
    scorecard = {
        "false_patch_count": 1,
        "unsafe_auto_patch_count": 0,
        "source_original_changed_count": 2,
        "writer_without_approval_count": 1,
    }
    mu = map_safety_scorecard_to_mu(scorecard)
    assert mu["false_patch"] == 1
    assert mu["original_broken"] == 2
    assert mu["unapproved_write"] == 1


def test_assess_severity_tnr_satisfied():
    clean = assess_severity(
        {"false_patch": 0, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0},
        baseline_ok=True,
    )
    assert clean["tnr_satisfied"] is True
    assert clean["total_violations"] == 0

    dirty = assess_severity(
        {"false_patch": 1, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0},
        baseline_ok=True,
    )
    assert dirty["tnr_satisfied"] is False


def test_ablation_flags_variants():
    full = ablation_flags("full")
    no_gate = ablation_flags("no_gate")
    assert full.require_copy_only is True
    assert no_gate.allow_unapproved_write is True


def test_map_pilot_scorecard_aliases():
    pilot = {
        "original_changed_count": 0,
        "unauthorized_writer_count": 0,
        "wrong_document_count": 0,
        "wrong_node_write_count": 0,
        "path_escape_count": 0,
        "auto_approve_count": 0,
        "safety_status": "PASS",
    }
    mu = map_safety_scorecard_to_mu(pilot)
    assert sum(mu.values()) == 0

    dirty = {
        "original_changed_count": 1,
        "unauthorized_writer_count": 2,
        "wrong_node_write_count": 1,
        "path_escape_count": 1,
    }
    mu2 = map_safety_scorecard_to_mu(dirty)
    assert mu2["original_broken"] == 1
    assert mu2["unapproved_write"] == 2
    assert mu2["false_patch"] == 1
    assert mu2["unsafe_write"] == 1


def test_assess_scorecard_nested_safety():
    from document_ai.safety.document_tnr import assess_scorecard

    payload = {
        "safety": {
            "false_patch_count": 0,
            "unsafe_auto_patch_count": 0,
            "source_original_changed_count": 0,
            "writer_without_approval_count": 0,
            "safety_status": "PASS",
        }
    }
    result = assess_scorecard(payload)
    assert result["tnr_satisfied"] is True
    assert result["safety_status"] == "PASS"


def test_baseline_from_session():
    session = {
        "documents": [{"original_fingerprint": "abc123"}],
    }
    assert baseline_from_session(session) == "abc123"
