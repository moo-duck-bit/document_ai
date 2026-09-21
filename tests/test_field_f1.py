"""Tests for flat golden_fields.jsonl Field F1 evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.eval.field_f1 import (
    bootstrap_golden_fields_jsonl_from_case,
    compute_field_f1,
    extract_field_value,
    load_golden_fields_jsonl,
    score_field_row,
)


def _write_case(tmp_path: Path) -> Path:
    case = tmp_path / "demo_case"
    case.mkdir()
    (case / "input.json").write_text(
        json.dumps(
            {
                "case_id": "demo_case",
                "facts": {
                    "product_name": "Demo Product",
                    "product_code": "DEMO",
                    "author_org": "Demo Org",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (case / "mdsr_content.json").write_text(
        json.dumps(
            {
                "cover_product_line": "Demo Org",
                "document_title": "EC-SW-MDSR Demo Product spec",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (case / "requirements.json").write_text(
        json.dumps(
            {
                "requirements": [
                    {"req_id": "Req. 1", "description": "First requirement text."},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return case


def test_extract_field_value_paths(tmp_path: Path):
    case = _write_case(tmp_path)
    assert extract_field_value(case, "input.facts.product_code") == "DEMO"
    assert extract_field_value(case, "mdsr.cover_product_line") == "Demo Org"
    assert extract_field_value(case, "requirements.Req. 1.description") == "First requirement text."


def test_score_field_row_exact_and_fuzzy(tmp_path: Path):
    case = _write_case(tmp_path)
    exact = score_field_row(
        case,
        {
            "case_id": "demo_case",
            "field_id": "input.facts.product_code",
            "expected_value": "DEMO",
            "exact_match": True,
        },
    )
    assert exact["matched"] is True

    fuzzy = score_field_row(
        case,
        {
            "case_id": "demo_case",
            "field_id": "mdsr.document_title",
            "expected_value": "Demo Product",
            "exact_match": False,
        },
    )
    assert fuzzy["matched"] is True


def test_bootstrap_and_compute_field_f1(tmp_path: Path):
    case = _write_case(tmp_path)
    golden = tmp_path / "golden_fields.jsonl"
    rows = bootstrap_golden_fields_jsonl_from_case(
        case,
        out_path=golden,
        include_requirements=True,
    )
    assert len(rows) >= 4
    loaded = load_golden_fields_jsonl(golden)
    assert loaded[0]["case_id"] == "demo_case"

    result = compute_field_f1(case_dir=case, golden_path=golden)
    assert result["field_count"] == len(rows)
    assert result["field_f1"] == 1.0
    assert result["matched_count"] == result["field_count"]
