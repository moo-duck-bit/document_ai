"""Tests for quality scoring."""

from __future__ import annotations

from document_ai.quality.scorer import score_analysis, score_status


def test_score_status_thresholds():
    assert score_status(90) == "PASS"
    assert score_status(75) == "WARNING"
    assert score_status(50) == "FAIL"


def test_score_analysis_clean_document():
    analysis = {
        "findings": [],
        "documents": {
            "mdsr": {
                "structure_review": {
                    "issue_count": 0,
                    "residual_count": 0,
                    "requirements_expected": 10,
                    "issues": [],
                    "residual": [],
                }
            }
        },
        "product_name": "IMS",
    }
    scores = score_analysis(analysis)
    assert scores.overall >= 85
    assert scores.structure >= 90
    assert scores.residual_text == 100.0


def test_score_analysis_penalizes_findings():
    analysis = {
        "findings": [
            {"category": "placeholder", "severity": "fail", "auto_fixable": True},
            {"category": "mindrium", "severity": "fail", "auto_fixable": True},
            {"category": "domain_mismatch", "severity": "warning", "auto_fixable": True},
        ],
        "documents": {
            "mdsr": {
                "structure_review": {
                    "issue_count": 2,
                    "residual_count": 1,
                    "requirements_expected": 5,
                    "issues": ["Req. 2: no description/purpose filled", "traceability IA-01: missing linked reqs"],
                    "residual": ["paragraph: Mindrium"],
                }
            }
        },
        "product_name": "IMS",
    }
    scores = score_analysis(analysis)
    assert scores.overall < 85
    assert scores.residual_text < 90
    assert scores.terminology < 100
