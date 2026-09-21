# -*- coding: utf-8 -*-
"""PR-25: Controlled writer validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.controlled_writer.copy_workspace import file_sha256
from document_ai.controlled_writer.schema import (
    DiffResult,
    RollbackPoint,
    WriterPlan,
    WriterResult,
)


def validate_controlled_writer(
    *,
    plans: list[WriterPlan],
    results: list[WriterResult],
    diffs: list[DiffResult],
    rollbacks: list[RollbackPoint],
    summary: dict[str, Any] | None = None,
    source_fingerprints: dict[str, str] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    source_fingerprints = source_fingerprints or {}

    plan_ids = [p.writer_plan_id for p in plans]
    if len(plan_ids) != len(set(plan_ids)):
        issues.append("duplicate_writer_plan_id")
    result_ids = [r.writer_result_id for r in results]
    if len(result_ids) != len(set(result_ids)):
        issues.append("duplicate_writer_result_id")

    for r in results:
        if r.actual_original_changed:
            issues.append(f"original_changed:{r.writer_result_id}")
        if not r.original_unchanged and r.result_status == "APPLIED":
            issues.append(f"original_not_verified:{r.writer_result_id}")
        # Source path must still match recorded fingerprint if provided
        src = Path(r.source_path)
        if r.source_path in source_fingerprints and src.exists():
            if file_sha256(src) != source_fingerprints[r.source_path]:
                issues.append(f"source_fingerprint_drift:{r.writer_result_id}")

    for d in diffs:
        if d.operation_count < 0:
            issues.append(f"diff_negative_ops:{d.diff_id}")
        if d.before_text == d.after_text and d.operation_count != 0:
            warnings.append(f"diff_count_inconsistent:{d.diff_id}")

    applied = [r for r in results if r.result_status == "APPLIED"]
    for r in applied:
        if not r.copy_modified and r.operation in ("UPDATE", "REPLACE", "ADD", "DELETE", "LINK"):
            # ADD empty could be edge; still warn
            warnings.append(f"applied_but_copy_unmodified:{r.writer_result_id}")
        if r.diff_id and not any(d.diff_id == r.diff_id for d in diffs):
            issues.append(f"missing_diff:{r.writer_result_id}")

    if summary:
        if summary.get("original_changed_count", 0) != 0:
            issues.append("summary_original_changed_nonzero")
        if summary.get("patch_success_count") != sum(
            1 for r in results if r.result_status == "APPLIED"
        ):
            issues.append("summary_success_mismatch")
        if summary.get("failure_count") != sum(
            1
            for r in results
            if r.result_status in ("FAILED", "ROLLED_BACK")
        ):
            issues.append("summary_failure_mismatch")

    originals_ok = all(r.original_unchanged for r in results) and not any(
        r.actual_original_changed for r in results
    )
    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "controlled_writer_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": {
            "unique_plan_ids": "duplicate_writer_plan_id" not in issues,
            "unique_result_ids": "duplicate_writer_result_id" not in issues,
            "originals_unchanged": originals_ok,
            "original_changed_count_zero": originals_ok,
            "diff_consistency": not any(i.startswith("missing_diff") for i in issues),
            "summary_consistent": not any(i.startswith("summary_") for i in issues),
        },
        "original_fingerprint_checks": len(source_fingerprints),
        "patch_success_count": sum(1 for r in results if r.result_status == "APPLIED"),
        "failure_count": sum(
            1 for r in results if r.result_status in ("FAILED", "ROLLED_BACK")
        ),
        "note": "PR-25 controlled writer validation. Originals must never change.",
    }
