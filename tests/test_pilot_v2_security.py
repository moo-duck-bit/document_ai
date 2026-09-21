# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — security guard tests.

Covers: id/filename sanitization, extension allowlist, upload size limit,
session-root escape prevention, source/copy collision, artifact path
resolution, and text sanitization.
"""

from __future__ import annotations

import pytest

from document_ai.pilot_v2 import security


# --- safe_id / safe_filename -------------------------------------------------


def test_safe_id_strips_unsafe_chars():
    assert security.safe_id("hello world!!") == "hello-world"


def test_safe_id_empty_falls_back_to_prefix():
    assert security.safe_id("", prefix="fallback") == "fallback"
    assert security.safe_id("...", prefix="fallback") == "fallback"


def test_safe_id_truncates_to_max_len():
    long_name = "a" * 200
    assert len(security.safe_id(long_name, max_len=32)) == 32


def test_safe_filename_returns_basename_only():
    assert security.safe_filename("some/dir/report.docx") == "report.docx"


def test_safe_filename_rejects_parent_traversal():
    with pytest.raises(security.PilotSecurityError) as exc:
        security.safe_filename("../../etc/passwd.docx")
    assert exc.value.reason_code == "PATH_TRAVERSAL_BLOCKED"


def test_safe_filename_rejects_absolute_unix_path():
    with pytest.raises(security.PilotSecurityError):
        security.safe_filename("/etc/passwd.docx")


def test_safe_filename_rejects_absolute_windows_path():
    with pytest.raises(security.PilotSecurityError):
        security.safe_filename("C:/Windows/system32/evil.docx")


def test_safe_filename_rejects_empty():
    with pytest.raises(security.PilotSecurityError) as exc:
        security.safe_filename("")
    assert exc.value.reason_code == "INVALID_FILENAME"


# --- extension allowlist -----------------------------------------------------


def test_validate_extension_accepts_docx():
    assert security.validate_extension("report.docx") == ".docx"


@pytest.mark.parametrize("filename", ["report.exe", "report.pdf", "report", "report.DOCX.exe"])
def test_validate_extension_rejects_non_docx(filename):
    with pytest.raises(security.PilotSecurityError) as exc:
        security.validate_extension(filename)
    assert exc.value.reason_code == "UNSUPPORTED_EXTENSION"


def test_validate_extension_accepts_uppercase_docx():
    assert security.validate_extension("REPORT.DOCX") == ".docx"


# --- size limit ---------------------------------------------------------------


def test_validate_upload_size_rejects_empty():
    with pytest.raises(security.PilotSecurityError) as exc:
        security.validate_upload_size(b"")
    assert exc.value.reason_code == "EMPTY_DOCUMENT"


def test_validate_upload_size_rejects_oversized():
    with pytest.raises(security.PilotSecurityError) as exc:
        security.validate_upload_size(b"x" * 100, max_bytes=50)
    assert exc.value.reason_code == "FILE_TOO_LARGE"


def test_validate_upload_size_accepts_within_limit():
    assert security.validate_upload_size(b"x" * 10, max_bytes=50) == 10


def test_validate_upload_full_guard_combines_checks():
    name, ext = security.validate_upload("MyReport.docx", b"PK\x03\x04fake")
    assert name == "MyReport.docx"
    assert ext == ".docx"


def test_validate_upload_rejects_traversal_and_bad_extension():
    with pytest.raises(security.PilotSecurityError):
        security.validate_upload("../evil.exe", b"data")


# --- session root escape -----------------------------------------------------


def test_ensure_within_root_allows_nested_path(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = root / "sub" / "file.txt"
    resolved = security.ensure_within_root(target, root)
    assert str(resolved).startswith(str(root.resolve()))


def test_ensure_within_root_blocks_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside" / "file.txt"
    with pytest.raises(security.PilotSecurityError) as exc:
        security.ensure_within_root(outside, root)
    assert exc.value.reason_code == "PATH_ESCAPE_BLOCKED"


def test_ensure_within_root_blocks_dotdot_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    escape = root / ".." / "escaped.txt"
    with pytest.raises(security.PilotSecurityError):
        security.ensure_within_root(escape, root)


def test_resolve_session_dir_normal_id(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    resolved = security.resolve_session_dir(sessions_root, "session_abc123")
    assert resolved == (sessions_root / "session_abc123").resolve()


def test_resolve_session_dir_blocks_traversal_id(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    with pytest.raises(security.PilotSecurityError) as exc:
        security.resolve_session_dir(sessions_root, "../../escape")
    assert exc.value.reason_code == "SESSION_PATH_ESCAPE"


def test_resolve_session_dir_blocks_slash_in_id(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    with pytest.raises(security.PilotSecurityError):
        security.resolve_session_dir(sessions_root, "sub/dir")


# --- source/copy collision + writer target guard -----------------------------


def test_assert_source_copy_distinct_raises_when_equal(tmp_path):
    p = tmp_path / "same.docx"
    p.write_bytes(b"data")
    with pytest.raises(security.PilotSecurityError) as exc:
        security.assert_source_copy_distinct(p, p)
    assert exc.value.reason_code == "SOURCE_COPY_COLLISION"


def test_assert_source_copy_distinct_passes_when_different(tmp_path):
    a = tmp_path / "a.docx"
    b = tmp_path / "b.docx"
    a.write_bytes(b"data")
    security.assert_source_copy_distinct(a, b)  # should not raise


def test_assert_not_original_path_blocks_forbidden_root(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    target = input_dir / "source.docx"
    with pytest.raises(security.PilotSecurityError) as exc:
        security.assert_not_original_path(target, forbidden_roots=(input_dir,))
    assert exc.value.reason_code == "WRITE_TARGET_FORBIDDEN"


def test_assert_not_original_path_allows_outside_forbidden_root(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    target = output_dir / "copy.docx"
    security.assert_not_original_path(target, forbidden_roots=(input_dir,))  # should not raise


# --- text sanitization --------------------------------------------------------


def test_sanitize_text_strips_null_bytes_and_whitespace():
    assert security.sanitize_text("  hello\x00world  ") == "helloworld"


def test_sanitize_text_truncates_to_max_len():
    long_text = "a" * 100
    assert len(security.sanitize_text(long_text, max_len=10)) == 10


def test_sanitize_text_handles_none():
    assert security.sanitize_text(None) == ""


# --- artifact path resolution -------------------------------------------------


def test_resolve_artifact_path_blocks_traversal(tmp_path):
    session_root = tmp_path / "session"
    session_root.mkdir()
    with pytest.raises(security.PilotSecurityError) as exc:
        security.resolve_artifact_path(session_root, "../escape.txt", allowed_subdirs=frozenset({"output"}))
    assert exc.value.reason_code == "PATH_TRAVERSAL_BLOCKED"


def test_resolve_artifact_path_blocks_disallowed_subdir(tmp_path):
    session_root = tmp_path / "session"
    (session_root / "input").mkdir(parents=True)
    (session_root / "input" / "f.docx").write_bytes(b"x")
    with pytest.raises(security.PilotSecurityError) as exc:
        security.resolve_artifact_path(session_root, "input/f.docx", allowed_subdirs=frozenset({"output"}))
    assert exc.value.reason_code == "ARTIFACT_NOT_ALLOWED"


def test_resolve_artifact_path_returns_existing_file(tmp_path):
    session_root = tmp_path / "session"
    (session_root / "output").mkdir(parents=True)
    target = session_root / "output" / "f.docx"
    target.write_bytes(b"x")
    resolved = security.resolve_artifact_path(session_root, "output/f.docx", allowed_subdirs=frozenset({"output"}))
    assert resolved == target.resolve()


def test_resolve_artifact_path_raises_for_missing_file(tmp_path):
    session_root = tmp_path / "session"
    (session_root / "output").mkdir(parents=True)
    with pytest.raises(security.PilotSecurityError) as exc:
        security.resolve_artifact_path(session_root, "output/missing.docx", allowed_subdirs=frozenset({"output"}))
    assert exc.value.reason_code == "ARTIFACT_NOT_FOUND"
