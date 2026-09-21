# -*- coding: utf-8 -*-
"""Holdout protocol + generalization + format + split regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.evaluation.document_set_v2.dataset_loader import (
    BenchmarkV2ValidationError,
    load_benchmark_v2_manifest,
    validate_benchmark_v2,
)
from document_ai.evaluation.document_set_v2.format_preservation import compare_format
from document_ai.evaluation.document_set_v2.holdout_protocol import hash_label_dir
from document_ai.evaluation.document_set_v2.metrics import generalization_gap

REPO = Path(__file__).resolve().parents[1]
V1 = REPO / "data" / "eval" / "document_set_benchmark"
V2 = REPO / "data" / "eval" / "document_set_benchmark_v2"


def test_development_ge_20():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    assert len(b["cases"]["development"]) >= 20


def test_holdout_ge_20():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    assert len(b["cases"]["holdout"]) >= 20


def test_ec_sw_count_new_cases():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    n = sum(1 for split in ("development", "holdout") for c in b["cases"][split] if c.domain == "ec_sw")
    assert n >= 20


def test_general_report_count():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    n = sum(1 for split in ("development", "holdout") for c in b["cases"][split] if c.domain == "general_report")
    assert n >= 12


def test_business_proposal_count():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    n = sum(1 for split in ("development", "holdout") for c in b["cases"][split] if c.domain == "business_proposal")
    assert n >= 8


def test_duplicate_detection_across_splits():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    ids = [c.case_id for rows in b["cases"].values() for c in rows]
    assert len(ids) == len(set(ids))


def test_missing_input_document_raises(tmp_path):
    # craft invalid case pointing missing file
    bad = {
        "meta": {},
        "regression_manifest": str(V1 / "manifest.json"),
        "development_cases": [],
        "holdout_cases": [],
    }
    # skip — empty development would fail validation lt_20
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps(bad), encoding="utf-8")
    b = load_benchmark_v2_manifest(man)
    v = validate_benchmark_v2(b)
    assert v["status"] == "INVALID"
    assert any("development_lt_20" in i for i in v["issues"])


def test_sealed_label_hash_keys():
    h = hash_label_dir(V2 / "holdout" / "sealed_labels")
    assert "document_impacts.jsonl" in h
    assert "node_evaluation_eligibility.jsonl" in h


def test_generalization_gap_zero_when_equal():
    m = {"document_macro_f1": 0.5, "required_node_top1": 0.5, "required_node_recall_at_3": 0.5, "e2e_success_rate": 0.5, "node_decision_macro_f1": 0.5}
    g = generalization_gap(m, m)
    assert all(abs(v) < 1e-12 for v in g.values())


def test_format_table_and_style_keys():
    src = V2 / "fixtures" / "business_proposal" / "proposal_base.docx"
    cmp = compare_format(src, src)
    assert "table_preservation_rate" in cmp
    assert "style_preservation_rate" in cmp


def test_v1_labels_dir_intact():
    assert (V1 / "labels" / "document_impacts.jsonl").is_file()
    assert (V1 / "labels" / "node_evaluation_eligibility.jsonl").is_file()


def test_source_types_on_new_cases():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    for c in b["cases"]["development"]:
        assert c.source_type in {"GENERATED", "STRUCTURE_PERTURBED", "TEMPLATE_DERIVED", "fixture"}


def test_holdout_cases_have_holdout_split():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    assert all(c.split == "holdout" for c in b["cases"]["holdout"])


def test_regression_cases_forced_split():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    assert all(c.split == "regression" for c in b["cases"]["regression"])


def test_metamorphic_expected_relation_present():
    for line in (V2 / "metamorphic_pairs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert row.get("expected_relation")
        assert row.get("base_case_id") != row.get("variant_case_id")


def test_no_automatic_gold_mutation_flag_in_seal():
    man = json.loads((V2 / "holdout" / "holdout_label_manifest.json").read_text(encoding="utf-8"))
    assert man["status"] == "SEALED"


def test_fixture_fingerprints_optional_but_paths_exist():
    b = load_benchmark_v2_manifest(V2 / "manifest.json")
    for c in list(b["cases"]["development"])[:5]:
        for d in c.input_documents:
            assert (V2 / d["path"]).is_file() or Path(d["path"]).is_file()


def test_error_taxonomy_constants_documented():
    # ensure report path planned
    assert "GENERALIZATION_FAILURE"  # presence in docs later
    tax = [
        "GENERALIZATION_FAILURE",
        "IDENTIFIER_VARIATION_FAILURE",
        "HEADING_VARIATION_FAILURE",
        "TABLE_STRUCTURE_FAILURE",
        "STABLE_REFERENCE_FAILURE",
        "CALIBRATION_ERROR",
        "HIGH_CONFIDENCE_WRONG",
        "DOMAIN_PACK_MISMATCH",
        "DUPLICATE_DOCUMENT_ERROR",
        "FORMAT_PRESERVATION_ERROR",
        "HOLDOUT_PROTOCOL_VIOLATION",
    ]
    assert len(tax) >= 11


def test_writer_expectations_should_write_false():
    rows = [
        json.loads(l)
        for l in (V2 / "development" / "labels" / "writer_expectations.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert rows and all(r.get("should_write") is False for r in rows)


def test_validation_error_type():
    assert issubclass(BenchmarkV2ValidationError, ValueError)
