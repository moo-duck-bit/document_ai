# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — completion / accuracy / writer / usability / safety scorecards.

All ratio metrics return ``None`` (not 0.0) when the denominator is zero, so
downstream reports can render "N/A" instead of a misleading zero.
"""

from __future__ import annotations

from typing import Any

from document_ai.pilot_v2.schema import HUMAN_REVIEW_SCORE_DIMENSIONS


def _ratio(n: float, d: float) -> float | None:
    if not d:
        return None
    return n / d


def compute_completion_scorecard(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(sessions)
    reached_analysis = sum(1 for s in sessions if s.get("status") not in {"CREATED", "UPLOADED", "FAILED"})
    reached_review = sum(
        1
        for s in sessions
        if s.get("status")
        in {"REVIEW_IN_PROGRESS", "REVIEW_COMPLETE", "WRITER_BLOCKED", "WRITER_COMPLETED", "HUMAN_REVIEWED", "COMPLETED"}
    )
    reached_completed = sum(1 for s in sessions if s.get("status") in {"HUMAN_REVIEWED", "COMPLETED"})
    failed = sum(1 for s in sessions if s.get("status") == "FAILED")
    all_items_decided = sum(
        1
        for s in sessions
        if s.get("review_items") is not None
        and all(str(i.get("decision")) != "PENDING" for i in (s.get("review_items") or []))
    )
    return {
        "n_sessions": n,
        "analysis_completion_rate": _ratio(reached_analysis, n),
        "review_reached_rate": _ratio(reached_review, n),
        "session_completion_rate": _ratio(reached_completed, n),
        "failure_rate": _ratio(failed, n),
        "review_fully_decided_rate": _ratio(all_items_decided, reached_review),
    }


def compute_accuracy_scorecard(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Human-review-derived accuracy: decision agreement + verdict distribution."""
    total_items = 0
    approved_items = 0
    rejected_items = 0
    held_items = 0
    edit_items = 0
    verdicts: dict[str, int] = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "PENDING": 0}
    n_with_review = 0
    for s in sessions:
        for item in s.get("review_items") or []:
            total_items += 1
            decision = str(item.get("decision") or "PENDING").upper()
            if decision == "APPROVE" or decision == "APPROVED":
                approved_items += 1
            elif decision == "REJECT" or decision == "REJECTED":
                rejected_items += 1
            elif decision == "HOLD":
                held_items += 1
            elif decision == "EDIT_PROPOSAL":
                edit_items += 1
        hr = s.get("human_review")
        if hr:
            n_with_review += 1
            verdict = str(hr.get("verdict") or "PENDING").upper()
            if verdict in verdicts:
                verdicts[verdict] += 1
    return {
        "n_review_items": total_items,
        "approval_rate": _ratio(approved_items, total_items),
        "rejection_rate": _ratio(rejected_items, total_items),
        "hold_rate": _ratio(held_items, total_items),
        "edit_proposal_rate": _ratio(edit_items, total_items),
        "n_sessions_with_human_review": n_with_review,
        "human_verdict_pass_rate": _ratio(verdicts["PASS"], n_with_review),
        "human_verdict_distribution": verdicts,
    }


def compute_writer_scorecard(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = [s for s in sessions if (s.get("writer_result") or {}).get("status") not in (None, "")]
    n_attempted = len(attempted)
    written = sum(1 for s in attempted if (s.get("writer_result") or {}).get("status") == "WRITTEN_COPY_ONLY")
    blocked = sum(1 for s in attempted if (s.get("writer_result") or {}).get("status") == "BLOCKED")
    preserved = sum(
        1
        for s in attempted
        if ((s.get("writer_result") or {}).get("original_preservation") or {}).get("ok") is True
    )
    format_rows: list[dict[str, Any]] = []
    for s in attempted:
        raw_fc = (s.get("writer_result") or {}).get("format_check")
        # format_check is a list of per-document rows when the writer produced
        # copies, or a single {"status": "N/A", ...} dict when it did not run.
        rows = raw_fc if isinstance(raw_fc, list) else ([raw_fc] if raw_fc else [])
        format_rows.extend(r for r in rows if isinstance(r, dict) and r.get("status") == "OK")
    avg_structure = None
    if format_rows:
        avg_structure = sum(r.get("structure_preservation_rate", 0.0) for r in format_rows) / len(format_rows)
    blocked_reason_counts: dict[str, int] = {}
    for s in attempted:
        wr = s.get("writer_result") or {}
        if wr.get("status") == "BLOCKED":
            for code in wr.get("reason_codes") or []:
                blocked_reason_counts[code] = blocked_reason_counts.get(code, 0) + 1
    return {
        "n_writer_attempts": n_attempted,
        "written_copy_rate": _ratio(written, n_attempted),
        "blocked_rate": _ratio(blocked, n_attempted),
        "original_preservation_rate": _ratio(preserved, n_attempted),
        "format_structure_preservation_rate": avg_structure,
        "blocked_reason_counts": blocked_reason_counts,
        "note": "Copy-only controlled writer: no textual patches are applied in this MVP.",
    }


def compute_usability_scorecard(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    dims: dict[str, list[int]] = {d: [] for d in HUMAN_REVIEW_SCORE_DIMENSIONS}
    overall: list[float] = []
    for s in sessions:
        hr = s.get("human_review")
        if not hr:
            continue
        scores = hr.get("scores") or {}
        vals = []
        for d in HUMAN_REVIEW_SCORE_DIMENSIONS:
            v = scores.get(d)
            if isinstance(v, (int, float)):
                dims[d].append(v)
                vals.append(v)
        if vals:
            overall.append(sum(vals) / len(vals))
    result: dict[str, Any] = {
        "n_responses": len(overall),
        "overall_average_score": (sum(overall) / len(overall)) if overall else None,
    }
    for d, vals in dims.items():
        result[f"avg_{d}"] = (sum(vals) / len(vals)) if vals else None
    return result


def compute_safety_scorecard(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    original_changed = 0
    unauthorized_write = 0
    write_without_approval = 0
    path_violations = 0
    for s in sessions:
        wr = s.get("writer_result") or {}
        preservation = wr.get("original_preservation") or {}
        if preservation.get("ok") is False:
            original_changed += 1
        if wr.get("status") == "WRITTEN_COPY_ONLY" and wr.get("approval_ok") is False:
            unauthorized_write += 1
        if wr.get("status") == "WRITTEN_COPY_ONLY" and not wr.get("has_explicit_approval"):
            write_without_approval += 1
        path_violations += int(wr.get("path_violation_count") or 0)
        for err in s.get("errors") or []:
            if "PATH_TRAVERSAL" in str(err) or "PATH_ESCAPE" in str(err) or "COLLISION" in str(err):
                path_violations += 1
    critical = original_changed + unauthorized_write + write_without_approval + path_violations
    status = "PASS" if critical == 0 else "INVALID"
    return {
        "n_sessions": len(sessions),
        "original_changed_count": original_changed,
        "unauthorized_write_count": unauthorized_write,
        "write_without_approval_count": write_without_approval,
        "path_security_violation_count": path_violations,
        "safety_status": status,
        "pass": status == "PASS",
    }


def build_pilot_scorecards(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "completion": compute_completion_scorecard(sessions),
        "accuracy": compute_accuracy_scorecard(sessions),
        "writer": compute_writer_scorecard(sessions),
        "usability": compute_usability_scorecard(sessions),
        "safety": compute_safety_scorecard(sessions),
    }
