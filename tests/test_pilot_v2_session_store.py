# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — session_store tests (workspace + manifest persistence)."""

from __future__ import annotations

import json

import pytest

from document_ai.pilot_v2 import security, session_store


# --- pilot root / sessions root -----------------------------------------------


def test_ensure_pilot_root_creates_dirs(tmp_path):
    root = tmp_path / "pilot"
    resolved = session_store.ensure_pilot_root(root)
    assert resolved.is_dir()
    assert (resolved / "sessions").is_dir()


def test_sessions_root_under_pilot_root(tmp_path):
    root = tmp_path / "pilot"
    sroot = session_store.sessions_root(root)
    assert sroot == root / "sessions"
    assert sroot.is_dir()


# --- manifest ------------------------------------------------------------------


def test_load_manifest_default_when_missing(tmp_path):
    manifest = session_store.load_manifest(tmp_path)
    assert manifest["sessions"] == []
    assert "meta" in manifest


def test_register_and_list_session_summaries(tmp_path):
    session_store.register_session_summary({"session_id": "s1", "participant_id": "P001", "created_at": "2026-01-01T00:00:00Z"}, root=tmp_path)
    session_store.register_session_summary({"session_id": "s2", "participant_id": "P002", "created_at": "2026-01-02T00:00:00Z"}, root=tmp_path)
    rows = session_store.list_session_summaries(tmp_path)
    assert {r["session_id"] for r in rows} == {"s1", "s2"}


def test_register_session_summary_dedupes_by_session_id(tmp_path):
    session_store.register_session_summary({"session_id": "s1", "status": "CREATED", "created_at": "2026-01-01T00:00:00Z"}, root=tmp_path)
    session_store.register_session_summary({"session_id": "s1", "status": "COMPLETED", "created_at": "2026-01-01T00:00:00Z"}, root=tmp_path)
    rows = session_store.list_session_summaries(tmp_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "COMPLETED"


def test_list_session_summaries_respects_limit(tmp_path):
    for i in range(5):
        session_store.register_session_summary(
            {"session_id": f"s{i}", "created_at": f"2026-01-0{i+1}T00:00:00Z"}, root=tmp_path
        )
    rows = session_store.list_session_summaries(tmp_path, limit=2)
    assert len(rows) == 2


def test_default_participant_id_starts_at_p001(tmp_path):
    assert session_store.default_participant_id(tmp_path) == "P001"


def test_default_participant_id_increments(tmp_path):
    session_store.register_session_summary({"session_id": "s1", "participant_id": "P001", "created_at": "2026-01-01T00:00:00Z"}, root=tmp_path)
    assert session_store.default_participant_id(tmp_path) == "P002"


# --- session id / workspace ----------------------------------------------------


def test_new_session_id_contains_scenario_and_participant():
    sid = session_store.new_session_id(scenario_id="pilot_ec_req_single", participant_id="P001")
    assert "pilot_ec_req_single" in sid
    assert "P001" in sid


def test_session_dir_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        session_store.session_dir("nope", root=tmp_path, must_exist=True)


def test_session_dir_allows_missing_when_not_required(tmp_path):
    path = session_store.session_dir("nope", root=tmp_path, must_exist=False)
    assert path.name == "nope"


def test_create_session_workspace_creates_subdirs(tmp_path):
    root = session_store.create_session_workspace("session_abc", root=tmp_path)
    for sub in session_store.SESSION_SUBDIRS:
        assert (root / sub).is_dir()


def test_create_session_workspace_raises_if_exists(tmp_path):
    session_store.create_session_workspace("session_abc", root=tmp_path)
    with pytest.raises(FileExistsError):
        session_store.create_session_workspace("session_abc", root=tmp_path)


# --- upload copy -----------------------------------------------------------------


def test_copy_upload_into_session_records_metadata(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    descriptor = session_store.copy_upload_into_session(session_root, "report.docx", b"PK\x03\x04fakecontent")
    assert descriptor["filename"] == "report.docx"
    assert descriptor["extension"] == ".docx"
    assert descriptor["sha256"] == session_store.sha256_bytes(b"PK\x03\x04fakecontent")
    assert (session_root / "input" / "report.docx").read_bytes() == b"PK\x03\x04fakecontent"


def test_copy_upload_into_session_rejects_unsupported_extension(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    with pytest.raises(security.PilotSecurityError):
        session_store.copy_upload_into_session(session_root, "report.exe", b"data")


def test_copy_upload_into_session_rejects_duplicate_filename(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    session_store.copy_upload_into_session(session_root, "report.docx", b"data-a")
    with pytest.raises(security.PilotSecurityError) as exc:
        session_store.copy_upload_into_session(session_root, "report.docx", b"data-b")
    assert exc.value.reason_code == "DUPLICATE_FILENAME"


def test_copy_upload_into_session_rejects_traversal_filename(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    with pytest.raises(security.PilotSecurityError):
        session_store.copy_upload_into_session(session_root, "../../escape.docx", b"data")


def test_copy_upload_into_session_rejects_oversized_file(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    with pytest.raises(security.PilotSecurityError):
        session_store.copy_upload_into_session(session_root, "big.docx", b"x" * (26 * 1024 * 1024))


def test_copy_upload_into_session_never_writes_outside_input_dir(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    session_store.copy_upload_into_session(session_root, "report.docx", b"data")
    all_files = list(session_root.rglob("*.docx"))
    assert all(f.parent.name == "input" for f in all_files)


# --- traces ------------------------------------------------------------------------


def test_write_trace_writes_json_under_category(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    dest = session_store.write_trace(session_root, "output", "analysis_trace", {"a": 1})
    assert dest.parent.name == "output"
    assert json.loads(dest.read_text(encoding="utf-8")) == {"a": 1}


def test_write_trace_rejects_invalid_category(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    with pytest.raises(security.PilotSecurityError) as exc:
        session_store.write_trace(session_root, "not_a_real_category", "x", {})
    assert exc.value.reason_code == "INVALID_TRACE_CATEGORY"


def test_write_trace_timestamped_names_are_unique(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    p1 = session_store.write_trace(session_root, "metrics", "timing", {"n": 1}, timestamped=True)
    p2 = session_store.write_trace(session_root, "metrics", "timing", {"n": 2}, timestamped=True)
    assert p1 != p2


# --- session record persistence -----------------------------------------------------


def test_save_and_load_session_record_roundtrip(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    record = {"session_id": "s1", "status": "CREATED", "participant_id": "P001", "document_set": "ec_sw"}
    session_store.save_session_record(session_root, record)
    loaded = session_store.load_session_record(session_root)
    assert loaded == record
    meta = json.loads((session_root / "meta.json").read_text(encoding="utf-8"))
    assert meta["session_id"] == "s1"


def test_load_session_record_raises_when_missing(tmp_path):
    session_root = session_store.create_session_workspace("s1", root=tmp_path)
    with pytest.raises(FileNotFoundError):
        session_store.load_session_record(session_root)


# --- original preservation check -----------------------------------------------------


def test_verify_original_preserved_ok_when_hash_matches(tmp_path):
    p = tmp_path / "doc.docx"
    p.write_bytes(b"original-bytes")
    digest = session_store.sha256_bytes(b"original-bytes")
    result = session_store.verify_original_preserved(p, digest)
    assert result["ok"] is True
    assert result["reason"] == "OK"


def test_verify_original_preserved_detects_tampering(tmp_path):
    p = tmp_path / "doc.docx"
    p.write_bytes(b"original-bytes")
    digest = session_store.sha256_bytes(b"original-bytes")
    p.write_bytes(b"TAMPERED-bytes")
    result = session_store.verify_original_preserved(p, digest)
    assert result["ok"] is False
    assert result["reason"] == "HASH_MISMATCH"


def test_verify_original_preserved_missing_file(tmp_path):
    p = tmp_path / "gone.docx"
    result = session_store.verify_original_preserved(p, "deadbeef")
    assert result["ok"] is False
    assert result["reason"] == "MISSING"
