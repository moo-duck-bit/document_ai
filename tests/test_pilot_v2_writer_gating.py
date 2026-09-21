# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — writer gating tests.

The gated copy-only writer must BLOCK unless every gate passes simultaneously:
explicit APPROVE decision, confirmed routing, enable_write flag, and the
CONTROLLED_WRITER_ENABLED environment flag. It must never touch the original
uploaded file and must always report Original Preservation.
"""

from __future__ import annotations

from document_ai.pilot_v2 import format_check, orchestrator as pv2, scenarios, session_store


def _setup_analyzed_session(tmp_path, scenario_id: str, *, routing_mode: str = "explicit"):
    scenario = scenarios.get_scenario(scenario_id)
    fixture_path = scenarios.ensure_fixture(scenario)
    session = pv2.create_session(
        document_set=scenario.document_set,
        change_request=scenario.change_request,
        scenario_id=scenario.scenario_id,
        root=tmp_path,
    )
    sid = session["session_id"]
    pv2.upload_documents(sid, [(fixture_path.name, fixture_path.read_bytes(), scenario.fixture_role)], root=tmp_path)
    pv2.resolve_identity(sid, routing_mode=routing_mode, user_confirmed=True, root=tmp_path)
    session = pv2.analyze(sid, root=tmp_path)
    return sid, session


def _approve_all_items(tmp_path, sid: str, session: dict) -> None:
    items = session.get("review_items") or []
    if not items:
        return
    decisions = [{"item_id": i["item_id"], "decision": "APPROVE"} for i in items]
    pv2.apply_decisions(sid, decisions, decided_by="tester", root=tmp_path)


# --- gate: no approval -----------------------------------------------------------


def test_writer_blocked_without_any_approved_items(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_ec_no_impact")
    # Deliberately do not approve anything.
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    wr = result["writer_result"]
    assert wr["status"] == "BLOCKED"
    assert "NOT_APPROVED" in wr["reason_codes"]
    assert wr["copies_written"] == []


def test_writer_gates_reflect_no_approval(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_ec_no_impact")
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    gates = result["writer_result"]["gates"]
    assert gates["explicit_approved_items"] is False


# --- gate: enable_write flag -------------------------------------------------------


def test_writer_blocked_when_enable_write_false_even_with_approval(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)
    result = pv2.run_writer_if_allowed(sid, enable_write=False, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    wr = result["writer_result"]
    if wr["gates"]["explicit_approved_items"]:
        assert wr["status"] == "BLOCKED"
        assert "WRITE_DISABLED" in wr["reason_codes"]


# --- gate: controlled writer env flag -----------------------------------------------


def test_writer_blocked_when_env_flag_disabled(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "false"}, root=tmp_path)
    wr = result["writer_result"]
    if wr["gates"]["explicit_approved_items"]:
        assert wr["status"] == "BLOCKED"
        assert "CONTROLLED_WRITER_ENV_DISABLED" in wr["reason_codes"]


def test_writer_blocked_when_env_flag_missing(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={}, root=tmp_path)
    wr = result["writer_result"]
    if wr["gates"]["explicit_approved_items"]:
        assert wr["status"] == "BLOCKED"


# --- gate: routing confirmation -----------------------------------------------------


def test_writer_blocked_when_routing_not_confirmed(tmp_path):
    # The normal state machine only reaches the writer step after analyze(),
    # which itself requires IDENTITY_RESOLVED (needs_user_confirmation already
    # False). To exercise the writer's own routing_confirmed gate in isolation,
    # flip the persisted identity flag back to "needs confirmation" directly on
    # the session record, then verify run_writer_if_allowed still blocks on it.
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)

    session_root = session_store.session_dir(sid, root=tmp_path)
    record = session_store.load_session_record(session_root)
    record["identity"]["needs_user_confirmation"] = True
    session_store.save_session_record(session_root, record)

    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    wr = result["writer_result"]
    if not wr["gates"]["explicit_approved_items"]:
        return  # scenario produced no approvable items; NOT_APPROVED already covers this path
    assert wr["status"] == "BLOCKED"
    assert "ROUTING_NOT_CONFIRMED" in wr["reason_codes"]
    assert wr["gates"]["routing_confirmed"] is False


# --- gate: fingerprint / original preservation --------------------------------------


def test_writer_blocked_on_fingerprint_mismatch(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)
    # Tamper with the session's own input copy after upload (never the "original"
    # upload bytes themselves, but the on-disk session copy used as the fingerprint
    # source) to simulate an integrity violation.
    session_root = session_store.session_dir(sid, root=tmp_path)
    input_files = list((session_root / "input").glob("*.docx"))
    assert input_files
    input_files[0].write_bytes(b"TAMPERED")
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    wr = result["writer_result"]
    assert wr["status"] == "BLOCKED"
    assert "FINGERPRINT_MISMATCH" in wr["reason_codes"]
    assert wr["gates"]["fingerprint_ok"] is False


# --- success path: all gates pass ---------------------------------------------------


def test_writer_writes_copy_when_all_gates_pass(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    wr = result["writer_result"]
    if not wr["gates"]["explicit_approved_items"]:
        return  # scenario produced no approvable items; gating already covered elsewhere
    assert wr["status"] == "WRITTEN_COPY_ONLY"
    assert wr["copies_written"]
    assert wr["original_preservation"]["ok"] is True


def test_writer_copy_is_placed_under_output_copies_not_input(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    wr = result["writer_result"]
    for copy in wr.get("copies_written") or []:
        out_path = copy["output"]
        assert "/output/copies/" in out_path.replace("\\", "/")
        assert "/input/" not in out_path.replace("\\", "/")


def test_writer_copy_content_matches_source_byte_for_byte(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    _approve_all_items(tmp_path, sid, session)
    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    wr = result["writer_result"]
    from pathlib import Path

    for copy in wr.get("copies_written") or []:
        src_bytes = Path(copy["source"]).read_bytes()
        out_bytes = Path(copy["output"]).read_bytes()
        assert src_bytes == out_bytes


def test_writer_never_mutates_original_upload_file(tmp_path):
    sid, session = _setup_analyzed_session(tmp_path, "pilot_gr_schedule_table")
    session_root = session_store.session_dir(sid, root=tmp_path)
    input_file = next((session_root / "input").glob("*.docx"))
    before_bytes = input_file.read_bytes()
    _approve_all_items(tmp_path, sid, session)
    pv2.run_writer_if_allowed(sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path)
    after_bytes = input_file.read_bytes()
    assert before_bytes == after_bytes


# --- format_check --------------------------------------------------------------------


def test_format_check_na_when_writer_not_run():
    result = format_check.check_writer_output(None, None)
    assert result["status"] == "N/A"


def test_format_check_na_when_files_missing(tmp_path):
    result = format_check.check_writer_output(tmp_path / "missing1.docx", tmp_path / "missing2.docx")
    assert result["status"] == "N/A"


def test_format_check_ok_for_identical_copy(tmp_path):
    from docx import Document

    src = tmp_path / "src.docx"
    doc = Document()
    doc.add_paragraph("hello")
    doc.save(str(src))
    dst = tmp_path / "dst.docx"
    dst.write_bytes(src.read_bytes())
    result = format_check.check_writer_output(src, dst)
    assert result["status"] == "OK"
    assert result["structure_preservation_rate"] == 1.0
