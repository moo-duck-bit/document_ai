# -*- coding: utf-8 -*-
"""Benchmark v2 schema / split / holdout protocol tests."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.evaluation.document_set_v2.dataset_loader import (
    load_benchmark_v2_manifest,
    validate_benchmark_v2,
)
from document_ai.evaluation.document_set_v2.holdout_protocol import (
    assert_labels_unchanged,
    freeze_predictions,
    hash_label_dir,
    unseal_for_evaluation,
    write_seal_manifest,
)
from document_ai.evaluation.document_set_v2.schema import ALLOWED_DOMAINS, ALLOWED_SPLITS

REPO = Path(__file__).resolve().parents[1]
V2 = REPO / "data" / "eval" / "document_set_benchmark_v2"


def test_allowed_domains_include_business_proposal():
    assert "business_proposal" in ALLOWED_DOMAINS
    assert "holdout" in ALLOWED_SPLITS


def test_manifest_loads_and_validates():
    bundle = load_benchmark_v2_manifest(V2 / "manifest.json", load_holdout_labels=False)
    v = validate_benchmark_v2(bundle)
    assert v["status"] in {"VALID", "VALID_WITH_WARNINGS"}
    assert len(bundle["cases"]["regression"]) == 24
    assert len(bundle["cases"]["development"]) >= 20
    assert len(bundle["cases"]["holdout"]) >= 20


def test_split_uniqueness():
    bundle = load_benchmark_v2_manifest(V2 / "manifest.json")
    ids = []
    for rows in bundle["cases"].values():
        ids.extend(c.case_id for c in rows)
    assert len(ids) == len(set(ids))


def test_holdout_labels_not_loaded_by_default():
    bundle = load_benchmark_v2_manifest(V2 / "manifest.json", load_holdout_labels=False)
    assert bundle["gold"]["holdout"] == {}
    assert bundle["load_holdout_labels"] is False


def test_holdout_seal_manifest_exists():
    man = V2 / "holdout" / "holdout_label_manifest.json"
    assert man.is_file()
    data = json.loads(man.read_text(encoding="utf-8"))
    assert data["status"] == "SEALED"
    assert data["label_file_hashes"]


def test_label_hash_stable():
    sealed = V2 / "holdout" / "sealed_labels"
    man = json.loads((V2 / "holdout" / "holdout_label_manifest.json").read_text(encoding="utf-8"))
    assert assert_labels_unchanged(man, sealed) == []


def test_freeze_and_unseal_protocol(tmp_path):
    sealed = V2 / "holdout" / "sealed_labels"
    seal = write_seal_manifest(
        holdout_dir=tmp_path / "holdout",
        sealed_labels_dir=sealed,
        out_path=tmp_path / "seal.json",
    )
    freeze = freeze_predictions(
        prediction_rows=[{"case_id": "x", "prediction": {}}],
        out_path=tmp_path / "preds.jsonl",
    )
    log = unseal_for_evaluation(
        seal_manifest=seal,
        prediction_freeze=freeze,
        sealed_labels_dir=sealed,
        out_log_path=tmp_path / "unseal.json",
    )
    assert log["status"] == "UNSEALED"
    assert log["protocol_ok"] is True


def test_prediction_adapter_no_sealed_labels():
    text = (
        REPO / "src" / "document_ai" / "evaluation" / "document_set" / "prediction_adapter.py"
    ).read_text(encoding="utf-8")
    assert "sealed_labels" not in text


def test_domains_present():
    bundle = load_benchmark_v2_manifest(V2 / "manifest.json")
    domains = {c.domain for rows in bundle["cases"].values() for c in rows}
    assert {"ec_sw", "general_report", "business_proposal"} <= domains


def test_missing_gold_holdout_until_unseal():
    bundle = load_benchmark_v2_manifest(V2 / "manifest.json", load_holdout_labels=False)
    assert not bundle["gold"]["holdout"]
    bundle2 = load_benchmark_v2_manifest(V2 / "manifest.json", load_holdout_labels=True)
    assert bundle2["gold"]["holdout"]["document_impacts"]
