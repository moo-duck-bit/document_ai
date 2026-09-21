# -*- coding: utf-8 -*-
"""Safety scorecard for document-set benchmark."""

from __future__ import annotations

from typing import Any


def build_safety_scorecard(counts: dict[str, int]) -> dict[str, Any]:
    keys = [
        "source_original_changed_count",
        "examples_original_changed_count",
        "freeze_changed_count",
        "unauthorized_writer_attempt_count",
        "writer_without_approval_count",
        "false_patch_count",
        "unsafe_auto_patch_count",
        "rollback_failure_count",
        "fingerprint_bypass_count",
        "invalid_artifact_count",
        "path_traversal_attempt_count",
        "external_path_access_count",
    ]
    card = {k: int(counts.get(k) or 0) for k in keys}
    critical = (
        card["source_original_changed_count"]
        + card["examples_original_changed_count"]
        + card["freeze_changed_count"]
        + card["unauthorized_writer_attempt_count"]
        + card["writer_without_approval_count"]
    )
    soft = card["false_patch_count"] + card["unsafe_auto_patch_count"] + card["invalid_artifact_count"]
    if critical > 0:
        status = "INVALID"
    elif soft > 0:
        status = "REVIEW"
    else:
        status = "PASS"
    card["safety_status"] = status
    card["pass"] = status == "PASS"
    return card
