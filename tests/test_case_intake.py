"""Tests for natural-language case intake (case-intake CLI)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from document_ai.harness.intake_chat import (
    detect_missing_fields,
    parse_intake_text,
    save_intake_draft,
)

HOSPITAL_TEXT = (
    "병원 예약 시스템이고 환자 예약, 진료과 선택, 접수, 수납 기능이 있습니다."
)


def test_infer_hospital_reservation_domain():
    draft = parse_intake_text(HOSPITAL_TEXT, case_id="hospital_demo")
    assert draft.payload["domain"] == "hospital_reservation"
    assert draft.inferred.get("domain_source") in {"keyword", "explicit"}


def test_extract_product_name_and_code():
    draft = parse_intake_text(HOSPITAL_TEXT, case_id="hospital_demo")
    facts = draft.payload["facts"]
    assert facts["product_name"] == "Hospital Reservation System"
    assert facts["product_code"] == "HRS"


def test_detect_missing_fields_on_draft():
    draft = parse_intake_text(HOSPITAL_TEXT, case_id="hospital_demo", confirm=False)
    assert "author_org" in draft.missing_fields
    assert "confirmed" in draft.missing_fields
    assert detect_missing_fields(draft.payload) == draft.missing_fields


def test_confirmed_false_by_default(tmp_path: Path):
    draft = parse_intake_text(HOSPITAL_TEXT, case_id="draft_case")
    assert draft.payload["confirmed"] is False
    assert draft.payload["confirmed_at"] is None
    out = save_intake_draft(draft, tmp_path / "input.json")
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["confirmed"] is False
    assert (tmp_path / "intake_log.json").exists()


def test_confirm_sets_confirmed_true(tmp_path: Path):
    draft = parse_intake_text(
        HOSPITAL_TEXT,
        case_id="hospital_demo",
        author_org="Sample Medical IT Co., Ltd.",
        confirm=True,
    )
    assert draft.payload["confirmed"] is True
    assert draft.payload["confirmed_at"] is not None
    assert "confirmed" not in draft.missing_fields
    assert draft.missing_fields == []


def test_cli_case_intake_writes_draft(tmp_path: Path):
    case_dir = tmp_path / "new_case"
    case_dir.mkdir()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_ai.cli",
            "case-intake",
            "--case",
            str(case_dir),
            "--text",
            HOSPITAL_TEXT,
            "--author-org",
            "Demo Medical IT",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 2, proc.stderr
    payload = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    assert payload["domain"] == "hospital_reservation"
    assert payload["facts"]["author_org"] == "Demo Medical IT"
    assert payload["confirmed"] is False


def test_cli_case_intake_confirm(tmp_path: Path):
    case_dir = tmp_path / "confirmed_case"
    case_dir.mkdir()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_ai.cli",
            "case-intake",
            "--case",
            str(case_dir),
            "--text",
            HOSPITAL_TEXT,
            "--author-org",
            "Demo Medical IT",
            "--confirm",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    assert payload["confirmed"] is True
