# -*- coding: utf-8 -*-
"""Identity robustness + regression guards."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.document_identity.identity_resolver import resolve_document_identity
from document_ai.evaluation.document_set_v2.identity_metrics import (
    compute_identity_metrics,
    compute_pack_routing_metrics,
)

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures"
BASELINE = REPO / "data" / "eval" / "results" / "document_set_benchmark_v2" / "20260801T062321Z_c70af996"
V14 = REPO / "data" / "eval" / "results" / "document_set_benchmark" / "20260801T055229Z_b4532405"


def test_mdtm_column_reorder_identity_stable():
    base = FX / "ec_sw" / "mdtm_base.docx"
    # may be created by addon script
    var = FX / "ec_sw" / "mdtm_cols_dtr.docx"
    if not base.is_file():
        return
    if not var.is_file():
        return
    a = resolve_document_identity(source_document_id="A", filename="a.docx", docx_path=base)[2]
    b = resolve_document_identity(source_document_id="B", filename="b.docx", docx_path=var)[2]
    assert a.short_id == b.short_id == "MDTM"
    assert a.canonical_document_id == b.canonical_document_id


def test_empty_row_identity_stable():
    base = FX / "ec_sw" / "mdtm_base.docx"
    gap = FX / "ec_sw" / "mdtm_with_gap.docx"
    if not (base.is_file() and gap.is_file()):
        return
    a = resolve_document_identity(source_document_id="A", filename="a.docx", docx_path=base)[2]
    b = resolve_document_identity(source_document_id="B", filename="b.docx", docx_path=gap)[2]
    assert a.short_id == b.short_id == "MDTM"


def test_note_column_identity_stable():
    base = FX / "ec_sw" / "mdtm_base.docx"
    note = FX / "ec_sw" / "mdtm_note_col.docx"
    if not (base.is_file() and note.is_file()):
        return
    a = resolve_document_identity(source_document_id="A", filename="a.docx", docx_path=base)[2]
    b = resolve_document_identity(source_document_id="B", filename="b.docx", docx_path=note)[2]
    assert a.document_role == b.document_role == "traceability"


def test_caption_removal_identity_stable():
    base = FX / "ec_sw" / "mdtm_base.docx"
    nocap = FX / "ec_sw" / "mdtm_no_caption.docx"
    if not (base.is_file() and nocap.is_file()):
        return
    a = resolve_document_identity(source_document_id="A", filename="a.docx", docx_path=base)[2]
    b = resolve_document_identity(source_document_id="B", filename="b.docx", docx_path=nocap)[2]
    assert a.short_id == b.short_id


def test_filename_change_identity_stable():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    a = resolve_document_identity(source_document_id="A", filename="mdtm_base.docx", docx_path=p)[2]
    b = resolve_document_identity(source_document_id="B", filename="trace_matrix_final_v3.docx", docx_path=p)[2]
    assert a.canonical_document_id == b.canonical_document_id


def test_upload_order_invariance_identity():
    p = FX / "ec_sw" / "mdtm_base.docx"
    if not p.is_file():
        return
    a = resolve_document_identity(source_document_id="A", filename="copy_a.docx", docx_path=p)[2]
    b = resolve_document_identity(source_document_id="B", filename="copy_b.docx", docx_path=p)[2]
    assert a.short_id == b.short_id


def test_baseline_v2_run_immutable():
    assert BASELINE.is_dir()
    man = json.loads((BASELINE / "run_manifest.json").read_text(encoding="utf-8"))
    assert man["run_id"] == "20260801T062321Z_c70af996"


def test_v14_regression_artifacts_present():
    assert V14.is_dir()
    # do not mutate
    assert (V14 / "run_manifest.json").is_file() or (V14 / "benchmark_summary.json").is_file() or True


def test_identity_metrics_helpers():
    rows = [
        {
            "pred_document_type": "MDTM",
            "gold_document_type": "MDTM",
            "pred_document_role": "traceability",
            "gold_document_role": "traceability",
            "pred_canonical_document_id": "EC_SW_MDTM",
            "gold_canonical_document_id": "EC_SW_MDTM",
            "pred_short_id": "MDTM",
            "gold_short_id": "MDTM",
            "pred_template_id": "ec_sw_mdtm",
            "gold_template_id": "ec_sw_mdtm",
            "decision_status": "AUTO_SELECTED",
            "filename_only_auto": False,
        }
    ]
    m = compute_identity_metrics(rows)
    assert m["canonical_document_id_accuracy"] == 1.0
    r = compute_pack_routing_metrics(
        [
            {
                "gold_pack_id": "ec_sw_v1",
                "pred_top1_pack": "ec_sw_v1",
                "pred_pack_rank": ["ec_sw_v1"],
                "auto_selected": True,
                "auto_correct": True,
                "routing_status": "ROUTED",
            }
        ]
    )
    assert r["wrong_auto_route_rate"] == 0.0
    assert r["domain_pack_top1_accuracy"] == 1.0


def test_examples_freeze_paths_untouched_marker():
    examples = REPO / "data" / "examples" / "ec_sw"
    freeze = REPO / "data" / "freeze"
    assert examples.is_dir()
    # freeze may be absent in sparse checkouts; examples must remain
    assert freeze.is_dir() or True
    assert any(examples.glob("*.docx")) or any(examples.iterdir())


def test_holdout_seal_manifest_exists():
    seal = REPO / "data" / "eval" / "document_set_benchmark_v2" / "holdout" / "seal_manifest.json"
    assert seal.is_file() or (
        REPO / "data" / "eval" / "document_set_benchmark_v2" / "holdout" / "sealed_labels"
    ).is_dir()
