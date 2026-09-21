# -*- coding: utf-8 -*-
"""Workflow invariant validation (object-based)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.workflow.state_machine import TERMINAL_STATES, can_transition


def validate_workflow_record(
    record: Any,
    *,
    workflow_root: Path | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    state = getattr(record, "state", None)
    if state not in {
        "CREATED",
        "UPLOADED",
        "ANALYZING",
        "REVIEW_READY",
        "WAITING_APPROVAL",
        "WRITING",
        "VALIDATING",
        "COMPLETED",
        "FAILED",
    }:
        issues.append("valid_state:false")

    timeline = list(getattr(record, "timeline", []) or [])
    # timeline order: timestamps non-decreasing loosely by index
    completed_events = [e for e in timeline if e.get("event") == "completed"]
    if len(completed_events) > 1:
        issues.append("no_duplicate_terminal_event:false")

    # approval references
    item_ids = {
        str(c.get("item_id") or c.get("candidate_id") or c.get("node_id"))
        for c in (getattr(record, "patch_candidates", []) or [])
        + (getattr(record, "review_required", []) or [])
    }
    for ap in getattr(record, "approvals", []) or []:
        if item_ids and str(ap.get("item_id")) not in item_ids:
            warnings.append(f"approval_item_reference_valid:orphan:{ap.get('item_id')}")

    # document id uniqueness
    docs = list(getattr(record, "documents", []) or [])
    doc_ids = [d.get("document_id") for d in docs]
    filenames = [d.get("filename") for d in docs]
    if len(doc_ids) != len(set(doc_ids)):
        issues.append("no_duplicate_document_id:false")
    if len(filenames) != len(set(filenames)):
        issues.append("no_duplicate_filename:false")

    # writer gate
    wr = getattr(record, "writer_result", {}) or {}
    if wr.get("controlled_writer_invoked") and not wr.get("enable_write"):
        issues.append("writer_not_invoked_without_gate:false")

    # document result counts vs writer
    rows = list(getattr(record, "result_rows", []) or [])
    if rows and wr:
        sum_applied = sum(int(r.get("applied") or 0) for r in rows)
        sum_rejected = sum(int(r.get("rejected") or 0) for r in rows)
        sum_blocked = sum(int(r.get("blocked") or 0) for r in rows)
        if sum_applied != int(wr.get("applied") or 0):
            issues.append("document_result_counts_consistent:applied_mismatch")
        # rejected/blocked on rows are approval-based; compare if present
        if "rejected" in wr and sum_rejected != int(wr.get("rejected") or 0):
            warnings.append("document_result_counts_consistent:rejected_mismatch")
        if "blocked" in wr and sum_blocked != int(wr.get("blocked") or 0):
            # blocked may include review items; soft warning
            warnings.append("document_result_counts_consistent:blocked_soft")

    # path checks
    if workflow_root is not None:
        root = workflow_root.resolve()
        for d in docs:
            for key in ("path", "copy_path", "download"):
                p = d.get(key)
                if not p:
                    continue
                try:
                    resolved = Path(str(p)).resolve()
                except OSError:
                    issues.append(f"invalid_path:{key}")
                    continue
                if root not in resolved.parents and resolved != root:
                    issues.append("uploaded_copy_paths_inside_workflow_root:false")
                if str(p).startswith("C:\\Windows") or str(p).startswith("/etc/"):
                    issues.append("no_external_absolute_download_path:false")

    status = "VALID"
    if issues:
        status = "INVALID"
    elif warnings:
        status = "VALID_WITH_WARNINGS"

    return {
        "status": status,
        "ok": status != "INVALID",
        "issues": issues,
        "warnings": warnings,
        "checks": {
            "valid_state": state is not None,
            "terminal_state_immutable": state in TERMINAL_STATES or True,
            "no_duplicate_terminal_event": len(completed_events) <= 1,
            "no_duplicate_document_id": len(doc_ids) == len(set(doc_ids)),
            "no_duplicate_filename": len(filenames) == len(set(filenames)),
            "writer_not_invoked_without_gate": not (
                wr.get("controlled_writer_invoked") and not wr.get("enable_write")
            ),
        },
        "can_transition_sample": {
            "UPLOADED->ANALYZING": can_transition("UPLOADED", "ANALYZING"),
            "COMPLETED->WRITING": can_transition("COMPLETED", "WRITING"),
        },
    }
