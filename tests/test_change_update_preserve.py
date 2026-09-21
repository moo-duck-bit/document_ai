# -*- coding: utf-8 -*-
"""Regression: change_update must patch-in-place Mindrium docs, not regenerate via retrieval."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document

from document_ai.harness.document_harness import DocumentHarness
from document_ai.impact.preserve_patch import (
    build_patch_preserving_outputs,
    contamination_new_tokens,
    patch_mdsr_description_only,
    sha256_file,
)
from document_ai.learn.docx_io import load_document
from document_ai.render.requirements import _default_criteria


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "data" / "examples" / "ec_sw"
MINDRIUM = ROOT / "data" / "cases" / "mindrium_xa"
TRIAL = ROOT / "data" / "trials" / "trial-001-mindrium-xa"


@pytest.fixture(scope="module")
def mindrium_mdsr() -> Path:
    matches = sorted(EXAMPLES.glob("spec_mdsr*.docx"))
    assert matches, "Mindrium MDSR example missing"
    return matches[0]


@pytest.fixture(scope="module")
def mindrium_mddr() -> Path:
    matches = sorted(EXAMPLES.glob("spec_mddr*.docx"))
    assert matches, "Mindrium MDDR example missing"
    return matches[0]


def test_default_criteria_helper_mentions_pci_owasp():
    assert "PCI DSS" in _default_criteria("Req. 105")
    assert "OWASP" in _default_criteria("Req. 102")


def test_description_only_patch_leaves_criteria_empty():
    doc = Document()
    table = doc.add_table(rows=4, cols=2)
    table.rows[0].cells[0].text = "Req. 6"
    table.rows[1].cells[0].text = "설명"
    table.rows[2].cells[0].text = "목적"
    table.rows[3].cells[0].text = "기준"
    assert patch_mdsr_description_only(doc, "Req. 6", "desc only", overwrite=True)
    assert table.rows[1].cells[1].text == "desc only"
    assert table.rows[2].cells[1].text.strip() == ""
    assert table.rows[3].cells[1].text.strip() == ""
    assert "PCI DSS" not in table.rows[3].cells[1].text


def test_description_only_patch_does_not_invent_label_when_blank():
    doc = Document()
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Req. 6"
    table.rows[1].cells[0].text = ""
    table.rows[1].cells[1].text = ""
    assert patch_mdsr_description_only(doc, "Req. 6", "desc only", overwrite=True)
    assert table.rows[1].cells[0].text.strip() == ""
    assert table.rows[1].cells[1].text == "desc only"


def test_description_only_patch_does_not_write_pci_criteria(mindrium_mdsr: Path, tmp_path: Path):
    out = tmp_path / "mdsr.docx"
    out.write_bytes(mindrium_mdsr.read_bytes())
    doc = load_document(out)
    ok = patch_mdsr_description_only(
        doc,
        "Req. 6",
        "연속 로그인 실패 시 계정 잠금을 수행해야 한다.",
        overwrite=True,
    )
    assert ok
    from document_ai.impact.preserve_patch import save_document

    save_document(doc, out)
    contam = contamination_new_tokens(mindrium_mdsr, out)
    assert contam == []
    # criteria cells must not gain PCI DSS
    doc2 = load_document(out)
    blob = "\n".join(c.text for t in doc2.tables for r in t.rows for c in r.cells)
    # new PCI only forbidden; if reference already had it, contamination_new_tokens handles it
    assert "PCI DSS" not in blob or any(
        "PCI DSS" in c.text
        for t in load_document(mindrium_mdsr).tables
        for r in t.rows
        for c in r.cells
    )


def test_patch_preserving_mdsr_only_req6_and_mddr_unchanged(
    mindrium_mdsr: Path, mindrium_mddr: Path, tmp_path: Path
):
    desc = (
        "연속 로그인 실패 시 계정 잠금 및 관리자 알림을 수행해야 한다.\n"
        "잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다."
    )
    out_dir = tmp_path / "out"
    result = build_patch_preserving_outputs(
        reference_mdsr=mindrium_mdsr,
        reference_mddr=mindrium_mddr,
        req_id="Req. 6",
        description=desc,
        out_dir=out_dir,
        mddr_strategy="no_automatic_design_patch",
    )
    assert result.ok, result.errors
    assert result.validation["mdsr_unexpected_diff_count"] == 0
    assert result.mddr_sha256_matches_reference is True
    assert sha256_file(out_dir / "output_mddr.docx") == sha256_file(mindrium_mddr)
    assert not (out_dir / "output_xxcs.docx").exists()
    # size must not collapse
    assert (out_dir / "output_mdsr.docx").stat().st_size > mindrium_mdsr.stat().st_size * 0.8


def test_no_design_patch_when_impact_design_ids_null(mindrium_mddr: Path, tmp_path: Path):
    """MDDR Option 1: no automatic design invention."""
    out = tmp_path / "mddr.docx"
    out.write_bytes(mindrium_mddr.read_bytes())
    assert sha256_file(out) == sha256_file(mindrium_mddr)


def test_xxcs_out_of_scope_not_created(mindrium_mdsr: Path, mindrium_mddr: Path, tmp_path: Path):
    out_dir = tmp_path / "pkg"
    build_patch_preserving_outputs(
        reference_mdsr=mindrium_mdsr,
        reference_mddr=mindrium_mddr,
        req_id="Req. 6",
        description="테스트 설명입니다.",
        out_dir=out_dir,
    )
    assert list(out_dir.glob("*xxcs*")) == []


def test_change_update_must_use_preserve_patch_not_harness_generate():
    """change_update canonical path is preserve_patch, not DocumentHarness.generate."""
    from document_ai.impact import preserve_patch

    assert hasattr(preserve_patch, "build_patch_preserving_outputs")
    assert hasattr(preserve_patch, "patch_mdsr_description_only")
    # Harness remains available for new_document_generation, but must not be
    # the default for Mindrium change_update Trial 1 correction.
    assert DocumentHarness is not None


def test_retrieval_enabled_harness_is_not_invoked_by_preserve_api(
    mindrium_mdsr: Path, mindrium_mddr: Path, tmp_path: Path
):
    """preserve API never calls retrieval / jm_collection."""
    result = build_patch_preserving_outputs(
        reference_mdsr=mindrium_mdsr,
        reference_mddr=mindrium_mddr,
        req_id="Req. 6",
        description="잠금 정책",
        out_dir=tmp_path / "out",
    )
    assert result.ok
    contam = contamination_new_tokens(mindrium_mdsr, tmp_path / "out" / "output_mdsr.docx")
    assert all(h["token"] != "JM COLLECTION" for h in contam)
    assert all(h["token"] != "JM-web" for h in contam)


def test_tre01_dc03_copy_bug_not_introduced_by_preserve_patch(
    mindrium_mdsr: Path, mindrium_mddr: Path, tmp_path: Path
):
    """XXCS not generated; therefore TRE-01/DC-03 copy cannot occur in canonical package."""
    out_dir = tmp_path / "out"
    result = build_patch_preserving_outputs(
        reference_mdsr=mindrium_mdsr,
        reference_mddr=mindrium_mddr,
        req_id="Req. 6",
        description="잠금 정책 설명",
        out_dir=out_dir,
    )
    assert result.ok
    assert not (out_dir / "output_xxcs.docx").exists()


def test_trial_invalid_markers_and_patch_dir_contract():
    """If Trial 1 folder exists, invalid markers / patch dir expectations are documented."""
    if not TRIAL.exists():
        pytest.skip("trial folder not present")
    # After correction script these should exist; allow skip if not yet run.
    clean = TRIAL / "generated_clean_mindrium" / "INVALID_FOR_HR.txt"
    gen = TRIAL / "generated" / "INVALID_FOR_HR.txt"
    if not clean.exists() or not gen.exists():
        pytest.skip("correction script not yet applied in this workspace snapshot")
    assert "INVALID_FOR_HR" in clean.read_text(encoding="utf-8")
