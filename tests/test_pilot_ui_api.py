# -*- coding: utf-8 -*-
"""Pilot smoke tests for Pilot UI API (no full scenario run)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from document_ai.pilot_ui.app import create_app
from document_ai.pilot_ui import service


def test_health():
    client = TestClient(create_app())
    r = client.get("/api/pilot/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_index_html():
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "Document AI Pilot" in r.text


def test_create_run_meta_only(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "PILOT_ROOT", tmp_path)
    meta = service.create_run(
        scenario_name="t",
        change_request="hello change",
        mdsr_bytes=b"PK\x03\x04mdsr-fake",
        mdsr_filename="MDSR.docx",
        mddr_bytes=b"PK\x03\x04mddr-fake",
        mddr_filename="MDDR.docx",
    )
    assert meta["run_id"]
    root = tmp_path / meta["run_id"]
    assert (root / "input" / "change_request.txt").read_text(encoding="utf-8").startswith(
        "hello"
    )
    assert (root / "input" / "reference" / "MDSR.docx").exists()
    assert (root / "input" / "reference" / "MDDR.docx").exists()


def test_approve_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "PILOT_ROOT", tmp_path)
    meta = service.create_run(
        scenario_name="appr",
        change_request="x",
        mdsr_bytes=b"a",
        mdsr_filename="MDSR.docx",
        mddr_bytes=b"b",
        mddr_filename="MDDR.docx",
    )
    run_id = meta["run_id"]
    approval = service.save_approval(run_id, decision="APPROVED", approved_by="t")
    assert approval["decision"] == "APPROVED"
    runs = service.list_runs()
    assert any(r["run_id"] == run_id for r in runs)
