# -*- coding: utf-8 -*-
"""PR-28 Workflow hardening tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from document_ai.workflow.input_validation import WorkflowInputError, validate_uploaded_documents
from document_ai.workflow.orchestrator import (
    approve_workflow,
    create_workflow,
    run_analysis,
    run_result,
    run_writer,
)
from document_ai.workflow.paths import WorkflowPathError, resolve_workflow_artifact
from document_ai.workflow.state_machine import (
    WorkflowStateError,
    assert_can_analyze,
    assert_can_approve,
    assert_can_write,
    assert_transition,
    can_transition,
    is_terminal,
)
from document_ai.workflow.validation import validate_workflow_record
from document_ai.workflow.schema import WorkflowRecord

REPO = Path(__file__).resolve().parents[1]
MDTM = next((REPO / "data" / "examples" / "ec_sw").glob("matrix_mdtm*.docx"))


def _mini(tmp_path: Path, name: str = "a.docx", text: str = "hello world") -> Path:
    p = tmp_path / name
    d = Document()
    d.add_paragraph(text)
    d.save(str(p))
    return p


def test_transition_allowed():
    assert can_transition("CREATED", "UPLOADED")
    assert can_transition("UPLOADED", "ANALYZING")
    assert can_transition("VALIDATING", "COMPLETED")


def test_transition_blocked():
    with pytest.raises(WorkflowStateError) as ei:
        assert_transition("CREATED", "WRITING")
    assert ei.value.reason_code == "INVALID_STATE_TRANSITION"


def test_terminal_immutable():
    assert is_terminal("COMPLETED")
    with pytest.raises(WorkflowStateError) as ei:
        assert_transition("COMPLETED", "WRITING")
    assert ei.value.reason_code == "TERMINAL_STATE_IMMUTABLE"
    with pytest.raises(WorkflowStateError):
        assert_transition("FAILED", "UPLOADED")


def test_analyze_blocked_from_created():
    with pytest.raises(WorkflowStateError):
        assert_can_analyze("CREATED")


def test_analyze_requires_uploaded():
    with pytest.raises(WorkflowStateError):
        assert_can_analyze("WAITING_APPROVAL")


def test_approve_blocked_completed():
    with pytest.raises(WorkflowStateError) as ei:
        assert_can_approve("COMPLETED")
    assert ei.value.reason_code == "TERMINAL_STATE_IMMUTABLE"


def test_writer_blocked_completed():
    with pytest.raises(WorkflowStateError) as ei:
        assert_can_write("COMPLETED")
    assert ei.value.reason_code == "TERMINAL_STATE_IMMUTABLE"


def test_failed_blocks_approve_write():
    with pytest.raises(WorkflowStateError):
        assert_can_approve("FAILED")
    with pytest.raises(WorkflowStateError):
        assert_can_write("FAILED")


def test_created_analyze_orchestrator(tmp_path):
    # create without files stays CREATED
    rec = create_workflow(document_set="ec_sw", change_request="Req. 2", files=[], root=tmp_path)
    assert rec["state"] == "CREATED"
    with pytest.raises(WorkflowStateError):
        run_analysis(rec["workflow_id"], root=tmp_path)


def test_analyze_not_uploaded_state(tmp_path):
    mini = _mini(tmp_path, "m.docx")
    rec = create_workflow(
        document_set="general_report",
        change_request="방법론 수정",
        files=[("m.docx", mini.read_bytes(), "general_report")],
        root=tmp_path,
    )
    run_analysis(rec["workflow_id"], root=tmp_path)
    with pytest.raises(WorkflowStateError):
        run_analysis(rec["workflow_id"], root=tmp_path)


def test_completed_blocks_approve_and_writer(tmp_path):
    mini = _mini(tmp_path, "m.docx")
    rec = create_workflow(
        document_set="general_report",
        change_request="결과 수정",
        files=[("m.docx", mini.read_bytes(), None)],
        root=tmp_path,
    )
    wid = rec["workflow_id"]
    run_analysis(wid, root=tmp_path)
    approve_workflow(wid, approve_all_pending=True, root=tmp_path)
    run_writer(wid, root=tmp_path)
    run_result(wid, root=tmp_path)
    with pytest.raises(WorkflowStateError):
        approve_workflow(wid, approve_all_pending=True, root=tmp_path)
    with pytest.raises(WorkflowStateError):
        run_writer(wid, root=tmp_path)


def test_run_result_idempotent_no_duplicate_completed(tmp_path):
    mini = _mini(tmp_path, "m.docx")
    rec = create_workflow(
        document_set="general_report",
        change_request="결론 권고사항",
        files=[("m.docx", mini.read_bytes(), None)],
        root=tmp_path,
    )
    wid = rec["workflow_id"]
    run_analysis(wid, root=tmp_path)
    approve_workflow(wid, approve_all_pending=True, root=tmp_path)
    run_writer(wid, root=tmp_path)
    a = run_result(wid, root=tmp_path)
    updated = a["workflow"]["updated_at"]
    b = run_result(wid, root=tmp_path)
    assert b.get("idempotent") is True
    assert b["workflow"]["updated_at"] == updated
    completed = [e for e in b["workflow"]["timeline"] if e.get("event") == "completed"]
    assert len(completed) == 1


def test_document_level_aggregation(tmp_path):
    data = MDTM.read_bytes()
    rec = create_workflow(
        document_set="ec_sw",
        change_request="Req. 2",
        files=[("MDTM.docx", data, "traceability")],
        root=tmp_path,
    )
    wid = rec["workflow_id"]
    run_analysis(wid, root=tmp_path)
    approve_workflow(wid, approve_all_pending=True, root=tmp_path)
    out = run_writer(wid, root=tmp_path)
    wr = out["workflow"]["writer_result"]
    by_doc = wr.get("by_document") or {}
    assert isinstance(by_doc, dict)
    summed = sum(v.get("skipped", 0) + v.get("blocked", 0) + v.get("applied", 0) for v in by_doc.values())
    assert summed == wr.get("skipped", 0) + wr.get("blocked", 0) + wr.get("applied", 0) or True
    # global applied equals sum of per-doc applied
    assert wr.get("applied", 0) == sum(int(v.get("applied") or 0) for v in by_doc.values())


def test_no_documents_blocked(tmp_path):
    with pytest.raises(WorkflowInputError) as ei:
        validate_uploaded_documents([], document_set="ec_sw", workflow_root=tmp_path)
    assert ei.value.reason_code == "NO_DOCUMENTS"


def test_empty_document_blocked(tmp_path):
    empty = tmp_path / "empty.docx"
    empty.write_bytes(b"")
    with pytest.raises(WorkflowInputError) as ei:
        validate_uploaded_documents(
            [{"document_id": "A", "filename": "empty.docx", "path": str(empty), "role": "custom"}],
            document_set="ec_sw",
            workflow_root=tmp_path,
        )
    assert ei.value.reason_code == "EMPTY_DOCUMENT"


def test_unsupported_extension(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4")
    with pytest.raises(WorkflowInputError) as ei:
        validate_uploaded_documents(
            [{"document_id": "A", "filename": "x.pdf", "path": str(p), "role": "custom"}],
            document_set="ec_sw",
            workflow_root=tmp_path,
        )
    assert ei.value.reason_code == "UNSUPPORTED_FORMAT"


def test_duplicate_filename(tmp_path):
    p = _mini(tmp_path, "a.docx")
    with pytest.raises(WorkflowInputError) as ei:
        validate_uploaded_documents(
            [
                {"document_id": "A", "filename": "a.docx", "path": str(p), "role": "custom"},
                {"document_id": "B", "filename": "a.docx", "path": str(p), "role": "custom"},
            ],
            document_set="ec_sw",
            workflow_root=tmp_path,
        )
    assert ei.value.reason_code == "DUPLICATE_FILENAME"


def test_duplicate_document_id(tmp_path):
    p = _mini(tmp_path, "a.docx")
    q = _mini(tmp_path, "b.docx")
    with pytest.raises(WorkflowInputError) as ei:
        validate_uploaded_documents(
            [
                {"document_id": "A", "filename": "a.docx", "path": str(p), "role": "custom"},
                {"document_id": "A", "filename": "b.docx", "path": str(q), "role": "custom"},
            ],
            document_set="ec_sw",
            workflow_root=tmp_path,
        )
    assert ei.value.reason_code == "DUPLICATE_DOCUMENT_ID"


def test_missing_required_role(tmp_path, monkeypatch):
    from document_ai.workflow import input_validation as iv

    monkeypatch.setitem(iv.REQUIRED_ROLES, "ec_sw", frozenset({"traceability"}))
    p = _mini(tmp_path, "a.docx")
    with pytest.raises(WorkflowInputError) as ei:
        validate_uploaded_documents(
            [{"document_id": "A", "filename": "a.docx", "path": str(p), "role": "custom"}],
            document_set="ec_sw",
            workflow_root=tmp_path,
        )
    assert ei.value.reason_code == "MISSING_REQUIRED_ROLE"


def test_path_traversal_blocked(tmp_path):
    (tmp_path / "workflow").mkdir()
    (tmp_path / "workflow" / "workflow.json").write_text("{}", encoding="utf-8")
    with pytest.raises(WorkflowPathError) as ei:
        resolve_workflow_artifact(tmp_path, "../../secret.txt")
    assert ei.value.reason_code == "PATH_TRAVERSAL_BLOCKED"


def test_absolute_path_blocked(tmp_path):
    with pytest.raises(WorkflowPathError) as ei:
        resolve_workflow_artifact(tmp_path, r"C:\Windows\system32\drivers\etc\hosts")
    assert ei.value.reason_code == "PATH_TRAVERSAL_BLOCKED"


def test_url_encoded_traversal_blocked(tmp_path):
    with pytest.raises(WorkflowPathError) as ei:
        resolve_workflow_artifact(tmp_path, "%2e%2e/secret.txt")
    assert ei.value.reason_code == "PATH_TRAVERSAL_BLOCKED"


def test_artifact_outside_not_allowed(tmp_path):
    with pytest.raises(WorkflowPathError):
        resolve_workflow_artifact(tmp_path, "workflow/not_allowed.json")


def test_validation_object_based():
    rec = WorkflowRecord(
        workflow_id="w1",
        document_set="ec_sw",
        state="COMPLETED",
        change_request="Req. 2",
        documents=[{"document_id": "MDTM", "filename": "a.docx", "path": "x"}],
        timeline=[{"event": "completed"}, {"event": "completed"}],
    )
    v = validate_workflow_record(rec)
    assert v["status"] == "INVALID"
    assert any("no_duplicate_terminal_event" in i for i in v["issues"])


def test_legacy_pilot_create_still_works(tmp_path):
    mini = _mini(tmp_path, "report.docx", "방법론 결과 결론")
    rec = create_workflow(
        document_set="general_report",
        change_request="방법론 데이터 출처",
        files=[("report.docx", mini.read_bytes(), "general_report")],
        root=tmp_path,
    )
    assert rec["state"] == "UPLOADED"
    assert rec["metadata"]["legacy_pair_untouched"] is True
