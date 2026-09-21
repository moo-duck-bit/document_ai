"""Tests for quality report generation."""

from __future__ import annotations

from document_ai.quality.report import render_quality_report


def test_render_quality_report_sections():
    result = {
        "case": "data/cases/inventory_mgmt",
        "product_name": "Inventory Management System",
        "domain": "inventory_b2b",
        "status": "WARNING",
        "scores": {
            "structure": 92.0,
            "terminology": 72.0,
            "completeness": 88.0,
            "consistency": 95.0,
            "traceability": 90.0,
            "residual_text": 78.0,
            "overall": 82.0,
        },
        "findings": [
            {
                "category": "domain_mismatch",
                "severity": "warning",
                "location": "paragraph[12]",
                "message": "Domain mismatch",
                "auto_fixable": True,
                "excerpt": "쇼핑몰",
            },
            {
                "category": "figure_table",
                "severity": "warning",
                "location": "paragraph[40]",
                "message": "Figure placeholder",
                "auto_fixable": False,
                "excerpt": "Figure 1",
            },
        ],
        "documents": {"mdsr": {}, "mddr": {}},
        "comparison": {
            "aggregate": {
                "field_similarity": 0.5,
                "paragraph_similarity": 0.6,
                "requirement_coverage": 0.95,
                "traceability_coverage": 0.9,
            },
            "comparisons": {
                "mdsr": {
                    "field_similarity": 0.5,
                    "paragraph_similarity": 0.6,
                    "requirement_coverage": 0.95,
                    "traceability_coverage": 0.9,
                }
            },
        },
    }
    text = render_quality_report(result)
    assert "# Document Quality Report" in text
    assert "**Overall:** WARNING" in text
    assert "### FAIL" in text
    assert "### WARNING" in text
    assert "Auto-fixable Items" in text
    assert "Human Review Required" in text
    assert "Gold Comparison" in text
    assert "domain_mismatch" in text
