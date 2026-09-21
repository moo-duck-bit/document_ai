# -*- coding: utf-8 -*-
"""Benchmark schema / dataset loader tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.evaluation.document_set.dataset_loader import (
    DatasetValidationError,
    load_benchmark_manifest,
)
from document_ai.evaluation.document_set.schema import STATUS_MAP, BenchmarkCase
from document_ai.evaluation.document_set.validation import validate_benchmark_bundle

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data" / "eval" / "document_set_benchmark" / "manifest.json"


def test_manifest_load():
    bundle = load_benchmark_manifest(MANIFEST)
    assert len(bundle["cases"]) >= 20


def test_domains_present():
    bundle = load_benchmark_manifest(MANIFEST)
    domains = {c.domain for c in bundle["cases"]}
    assert "ec_sw" in domains
    assert "general_report" in domains


def test_ec_sw_case_count():
    bundle = load_benchmark_manifest(MANIFEST)
    assert sum(1 for c in bundle["cases"] if c.domain == "ec_sw") >= 12


def test_general_report_case_count():
    bundle = load_benchmark_manifest(MANIFEST)
    assert sum(1 for c in bundle["cases"] if c.domain == "general_report") >= 8


def test_unique_case_ids():
    bundle = load_benchmark_manifest(MANIFEST)
    ids = [c.case_id for c in bundle["cases"]]
    assert len(ids) == len(set(ids))


def test_referenced_files_exist():
    bundle = load_benchmark_manifest(MANIFEST)
    base = Path(bundle["base_dir"])
    for c in bundle["cases"]:
        for d in c.input_documents:
            assert (base / d["path"]).is_file()


def test_document_gold_complete():
    bundle = load_benchmark_manifest(MANIFEST)
    gold_cases = {r["case_id"] for r in bundle["gold"]["document_impacts"]}
    for c in bundle["cases"]:
        assert c.case_id in gold_cases


def test_writer_gold_complete():
    bundle = load_benchmark_manifest(MANIFEST)
    gold_cases = {r["case_id"] for r in bundle["gold"]["writer_expectations"]}
    for c in bundle["cases"]:
        assert c.case_id in gold_cases


def test_invalid_domain_rejected(tmp_path):
    base = tmp_path / "bench"
    (base / "cases").mkdir(parents=True)
    (base / "labels").mkdir()
    (base / "fixtures").mkdir()
    doc = base / "fixtures" / "a.txt"
    doc.write_text("x", encoding="utf-8")
    case = {
        "case_id": "bad",
        "domain": "unknown",
        "document_set_id": "ec_sw",
        "change_request": "x",
        "input_documents": [{"path": "fixtures/a.txt", "filename": "a.txt"}],
    }
    (base / "cases" / "bad.json").write_text(json.dumps(case), encoding="utf-8")
    (base / "labels" / "document_impacts.jsonl").write_text(
        json.dumps({"case_id": "bad", "document_id": "A", "gold_status": "UNRELATED"}) + "\n",
        encoding="utf-8",
    )
    for name in ("node_impacts", "patch_expectations", "writer_expectations"):
        (base / "labels" / f"{name}.jsonl").write_text("", encoding="utf-8")
    man = {"meta": {}, "cases": ["cases/bad.json"]}
    mpath = base / "manifest.json"
    mpath.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load_benchmark_manifest(mpath)


def test_duplicate_case_detection(tmp_path):
    base = tmp_path / "bench"
    (base / "cases").mkdir(parents=True)
    (base / "labels").mkdir()
    (base / "fixtures").mkdir()
    doc = base / "fixtures" / "a.txt"
    doc.write_text("x", encoding="utf-8")
    case = {
        "case_id": "dup",
        "domain": "ec_sw",
        "document_set_id": "ec_sw",
        "change_request": "x",
        "input_documents": [{"path": "fixtures/a.txt", "filename": "a.txt"}],
    }
    (base / "cases" / "a.json").write_text(json.dumps(case), encoding="utf-8")
    (base / "cases" / "b.json").write_text(json.dumps(case), encoding="utf-8")
    (base / "labels" / "document_impacts.jsonl").write_text(
        json.dumps({"case_id": "dup", "document_id": "A", "gold_status": "UNRELATED"}) + "\n",
        encoding="utf-8",
    )
    for name in ("node_impacts", "patch_expectations", "writer_expectations"):
        (base / "labels" / f"{name}.jsonl").write_text("", encoding="utf-8")
    mpath = base / "manifest.json"
    mpath.write_text(json.dumps({"cases": ["cases/a.json", "cases/b.json"]}), encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load_benchmark_manifest(mpath)


def test_missing_document_detection(tmp_path):
    base = tmp_path / "bench"
    (base / "cases").mkdir(parents=True)
    (base / "labels").mkdir()
    case = {
        "case_id": "miss",
        "domain": "ec_sw",
        "document_set_id": "ec_sw",
        "change_request": "x",
        "input_documents": [{"path": "fixtures/missing.docx", "filename": "missing.docx"}],
    }
    (base / "cases" / "miss.json").write_text(json.dumps(case), encoding="utf-8")
    (base / "labels" / "document_impacts.jsonl").write_text(
        json.dumps({"case_id": "miss", "document_id": "A", "gold_status": "UNRELATED"}) + "\n",
        encoding="utf-8",
    )
    for name in ("node_impacts", "patch_expectations", "writer_expectations"):
        (base / "labels" / f"{name}.jsonl").write_text("", encoding="utf-8")
    mpath = base / "manifest.json"
    mpath.write_text(json.dumps({"cases": ["cases/miss.json"]}), encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load_benchmark_manifest(mpath)


def test_status_map_identity():
    assert STATUS_MAP["PATCH_CANDIDATE"] == "PATCH_CANDIDATE"
    assert STATUS_MAP["REVIEW_REQUIRED"] == "REVIEW_REQUIRED"


def test_benchmark_case_to_dict():
    c = BenchmarkCase(
        case_id="x",
        domain="ec_sw",
        document_set_id="ec_sw",
        change_request="Req. 1",
        input_documents=[],
    )
    assert c.to_dict()["case_id"] == "x"


def test_validate_bundle_ok():
    bundle = load_benchmark_manifest(MANIFEST)
    v = validate_benchmark_bundle(bundle)
    assert v["status"] in {"VALID", "VALID_WITH_WARNINGS"}
