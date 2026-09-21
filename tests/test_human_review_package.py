"""Tests for holdout human-review package and summary (evaluation-only)."""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document

from document_ai.eval.human_review_package import (
    prepare_review_package,
    review_result_template,
    summarize_human_evaluation,
)


def _stub_case(tmp_path: Path) -> Path:
    case = tmp_path / "cases" / "hospital_reservation"
    case.mkdir(parents=True)
    (case / "input.json").write_text(
        json.dumps({"case_id": "hospital_reservation", "domain": "hospital_reservation"}),
        encoding="utf-8",
    )
    for name in ("output_mdsr.docx", "output_mddr.docx"):
        doc = Document()
        doc.add_paragraph("Req. 1\nSample body for review package.")
        doc.save(str(case / name))
    (case / "human_review_checklist.md").write_text("# checklist\n", encoding="utf-8")
    return case


def test_prepare_review_package_files(tmp_path: Path):
    case = _stub_case(tmp_path)
    gold_fields = tmp_path / "gold" / "fields"
    gold_fields.mkdir(parents=True)
    (gold_fields / "hospital_reservation.gold_fields.json").write_text(
        json.dumps({"case_id": "hospital_reservation", "requirement_ids": ["Req. 1"]}),
        encoding="utf-8",
    )

    manifest = prepare_review_package(
        "hospital_reservation",
        case_dir=case,
        review_root=tmp_path / "review",
        gold_root=tmp_path / "gold",
    )
    review_dir = Path(manifest["review_dir"])
    expected = [
        "generated_mdsr.docx",
        "generated_mddr.docx",
        "human_review_checklist.md",
        "gold_fields_review.json",
        "reviewer_instructions.md",
        "review_result.template.json",
    ]
    for name in expected:
        assert (review_dir / name).exists(), name

    template = json.loads((review_dir / "review_result.template.json").read_text(encoding="utf-8"))
    for key in review_result_template():
        assert key in template
    assert "holdout freeze" in (review_dir / "reviewer_instructions.md").read_text(encoding="utf-8").lower()


def test_human_evaluation_summary_from_review_result(tmp_path: Path):
    review_dir = tmp_path / "review" / "hospital_reservation"
    review_dir.mkdir(parents=True)
    payload = review_result_template()
    payload.update(
        {
            "case_id": "hospital_reservation",
            "reviewer_id": "R1",
            "reviewed_at": "2026-07-14",
            "mdsr_status": "accept",
            "mddr_status": "accept_with_nits",
            "terminology_score": 4,
            "requirement_correctness_score": 5,
            "design_correctness_score": 4,
            "traceability_score": 4,
            "regulatory_appropriateness_score": 5,
            "issues": [{"kind": "placeholder", "detail": "XX-XX-XXXX"}],
            "required_changes": [],
            "approval_decision": "approve",
            "reviewer_comment": "OK for holdout gold",
        }
    )
    (review_dir / "review_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = summarize_human_evaluation(review_dir)
    assert summary["mean_score"] == 4.4
    assert summary["approve_count"] == 1
    assert summary["major_issue_count"] == 1
    assert summary["required_change_count"] == 0
    assert summary["recommended_gate"] == "promote_to_human_approved"
    assert summary["agreement"]["n_reviewers"] == 1
    assert (review_dir / "human_evaluation_summary.md").exists()
    assert "Mean score" in (review_dir / "human_evaluation_summary.md").read_text(encoding="utf-8")
