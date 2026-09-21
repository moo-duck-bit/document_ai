"""Trial constants, status, and error taxonomy."""

from __future__ import annotations

from typing import Any

TRIAL_STATUSES = (
    "prepared",
    "generated",
    "review_pending",
    "reviewed",
    "completed",
)

TRIAL_TYPES = ("new_document_generation", "change_update")

ERROR_TYPES = (
    "FACT_ERROR",
    "MISSING_CONTENT",
    "UNSUPPORTED_ASSUMPTION",
    "TRACEABILITY_ERROR",
    "FORMAT_ERROR",
    "TERMINOLOGY_ERROR",
    "STYLE_EDIT",
    "REDUNDANT_CONTENT",
    "INCONSISTENT_CONTENT",
    "WRONG_SECTION",
    "NO_CHANGE_REQUIRED",
)

SEVERITIES = ("critical", "major", "minor", "style")

DOCUMENT_TYPES = ("MDSR", "MDDR", "XXCS")

DATASET_ROLES = (
    "reference",
    "development",
    "validation",
    "holdout",
    "real_world_trial",
)

BASELINE_SYSTEM_VERSION = "v0.5-document-harness"
BASELINE_COMMIT = "d73fc18"

HUMAN_RATING_FIELDS = (
    "content_accuracy",
    "completeness",
    "format_compliance",
    "traceability",
    "language_quality",
    "practical_usability",
)

TRIAL_SUBDIRS = (
    "input",
    "reference",
    "generated",
    "human_revised",
    "diff",
    "review",
    "metrics",
    "reports",
    "presentation",
    "workdir",
)

FORBIDDEN_INPUT_PATH_MARKERS = (
    "data/gold",
    "data\\gold",
    "/gold/",
    "\\gold\\",
    "human_revised",
    "holdout_gold",
    "gold_mdsr",
    "gold_mddr",
    "review_result.json",
)

SENSITIVE_NAME_MARKERS = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
    "private_key",
    "주민",
    "passport",
)


def empty_document_review(document_type: str) -> dict[str, Any]:
    return {
        "document_type": document_type,
        "usable_without_change": False,
        "internal_review_ready": False,
        "external_delivery_ready": False,
        "major_issue_count": 0,
        "minor_issue_count": 0,
        "unchanged_section_count": 0,
        "modified_section_count": 0,
        "deleted_section_count": 0,
        "added_section_count": 0,
        "rating": {field: 0 for field in HUMAN_RATING_FIELDS},
        "notes": "",
    }


def human_revision_template(trial_id: str, document_types: list[str]) -> dict[str, Any]:
    return {
        "trial_id": trial_id,
        "reviewer": {"name": "", "role": ""},
        "review_started_at": "",
        "review_completed_at": "",
        "manual_baseline_minutes": None,
        "manual_baseline_source": "unknown",
        "harness_generation_minutes": None,
        "human_revision_minutes": None,
        "document_reviews": [empty_document_review(dt) for dt in document_types],
    }


def empty_error_annotation(
    *,
    document_type: str = "",
    error_type: str = "MISSING_CONTENT",
    verified: bool = False,
) -> dict[str, Any]:
    return {
        "document_type": document_type,
        "location": "",
        "error_type": error_type,
        "severity": "minor",
        "generated_text": "",
        "revised_text": "",
        "source_reference": "",
        "note": "",
        "verified": verified,
        "source": "human" if verified else "auto_candidate",
    }
