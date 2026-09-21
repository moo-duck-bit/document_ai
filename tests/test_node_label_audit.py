# -*- coding: utf-8 -*-
"""Node label audit — proposals only, no automatic gold mutation."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.evaluation.document_set.node_label_audit import (
    audit_node_labels,
    write_audit_artifacts,
)

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "data" / "eval" / "document_set_benchmark"


def test_audit_covers_all_24_cases():
    audit = audit_node_labels(bench_dir=BENCH)
    assert audit["summary"]["total_cases"] == 24
    assert audit["summary"]["automatic_gold_mutation"] == 0


def test_audit_modes_present():
    audit = audit_node_labels(bench_dir=BENCH)
    modes = audit["summary"]["by_mode"]
    assert modes.get("REQUIRED", 0) >= 1
    assert modes.get("OPTIONAL", 0) >= 1
    assert modes.get("NOT_APPLICABLE", 0) >= 1
    assert modes.get("AMBIGUOUS", 0) >= 1
    assert modes.get("UNLABELED", 0) == 0


def test_missing_gold_detection(tmp_path):
    # copy minimal: reuse eligibility but empty node gold via isolated dir
    # use real bench — REQUIRED without gold would be flagged if present
    audit = audit_node_labels(bench_dir=BENCH)
    for row in audit["rows"]:
        if row["node_evaluation_mode"] == "REQUIRED":
            assert row["gold_node_count"] >= 1 or row["label_issue"] == "NODE_GOLD_MISSING"


def test_unnecessary_gold_detection():
    audit = audit_node_labels(bench_dir=BENCH)
    # NOT_APPLICABLE with gold → NODE_GOLD_NOT_REQUIRED
    for row in audit["rows"]:
        if row["node_evaluation_mode"] == "NOT_APPLICABLE" and row["gold_node_count"] > 0:
            assert row["label_issue"] == "NODE_GOLD_NOT_REQUIRED"


def test_proposed_change_generation_no_auto_apply(tmp_path):
    audit = audit_node_labels(bench_dir=BENCH, prediction_by_case={"ec_sw_semantic_only": [{"node_id": "fake"}]})
    paths = write_audit_artifacts(audit, out_dir=tmp_path, also_write_proposed_to_bench=False)
    proposed = json.loads(Path(paths["proposed_label_changes.json"]).read_text(encoding="utf-8"))
    assert proposed["automatic_gold_mutation"] is False
    for ch in proposed["changes"]:
        assert ch.get("auto_applied") is False


def test_prediction_does_not_mutate_gold():
    before = (BENCH / "labels" / "node_impacts.jsonl").read_bytes()
    audit_node_labels(
        bench_dir=BENCH,
        prediction_by_case={
            "ec_sw_semantic_only": [{"node_id": "invented_from_pred", "score": 9}],
            "gr_schedule_table": [{"node_id": "invented2", "score": 9}],
        },
    )
    after = (BENCH / "labels" / "node_impacts.jsonl").read_bytes()
    assert before == after


def test_invalid_alternative_flagged_for_ambiguous_empty():
    issues = []
    from document_ai.evaluation.document_set.node_evaluation import validate_eligibility_row

    issues = validate_eligibility_row(
        {"node_evaluation_mode": "AMBIGUOUS", "acceptable_node_ids": [], "acceptable_node_groups": []}
    )
    assert issues


def test_label_complete_majority():
    audit = audit_node_labels(bench_dir=BENCH)
    complete = sum(1 for r in audit["rows"] if r["label_issue"] == "LABEL_COMPLETE")
    assert complete >= 20
