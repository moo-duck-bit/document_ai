"""Human review, approval, and report-selection for security test executions."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.form_fill.security_execution import (
    EXECUTED_STATUSES,
    SecurityExecutionImportError,
    _parse_ts,
    _plan_test_key,
    _sha256_file,
    format_evidence_summary,
    load_security_test_results,
    match_plan_test,
    save_security_test_results,
)
from document_ai.learn.extract_security_tests import load_security_tests
from document_ai.paths import PROJECT_ROOT

REVIEW_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "security_test_execution_review.schema.json"

REVIEW_STATUSES = frozenset(
    {
        "imported",
        "review_pending",
        "reviewer_verified",
        "rejected",
        "superseded",
        "test_fixture_verified",
    }
)
FINAL_REPORT_STATUSES = frozenset({"reviewer_verified"})
FIXTURE_STATUSES = frozenset({"test_fixture_verified"})
SELECTABLE_STATUSES = frozenset({"reviewer_verified", "test_fixture_verified"})


class SecurityReviewError(ValueError):
    """Raised when review validation or gold promotion fails."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_id(case_dir: Path) -> str:
    input_path = case_dir / "input.json"
    if input_path.exists():
        return str(_load_json(input_path).get("case_id") or case_dir.name)
    return case_dir.name


def _execution_archive_path(case_dir: Path, execution_id: str) -> Path:
    return case_dir / "executions" / f"{execution_id}.json"


def _review_record_path(case_dir: Path, execution_id: str) -> Path:
    return case_dir / "execution_reviews" / f"{execution_id}.review.json"


def load_execution_archive(case_dir: Path, execution_id: str) -> dict[str, Any]:
    path = _execution_archive_path(case_dir, execution_id)
    if not path.exists():
        raise SecurityReviewError(f"unknown execution_id: {execution_id}")
    return _load_json(path)


def validate_review_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("case_id", "execution_id", "reviewer", "reviewed_at", "overall_status", "test_reviews"):
        if key not in payload:
            errors.append(f"missing required field: {key}")
    if errors:
        return errors

    reviewer = payload.get("reviewer")
    if not isinstance(reviewer, dict) or not str(reviewer.get("name") or "").strip():
        errors.append("reviewer.name is required")

    status = str(payload.get("overall_status") or "")
    if status not in REVIEW_STATUSES:
        errors.append(f"invalid overall_status: {status}")

    reviews = payload.get("test_reviews")
    if not isinstance(reviews, list) or not reviews:
        errors.append("test_reviews must be a non-empty array")
        return errors

    seen: set[str] = set()
    for idx, row in enumerate(reviews):
        if not isinstance(row, dict):
            errors.append(f"test_reviews[{idx}] must be an object")
            continue
        sid = str(row.get("security_test_id") or "").strip()
        if not sid:
            errors.append(f"test_reviews[{idx}].security_test_id is required")
            continue
        if sid in seen:
            errors.append(f"duplicate security_test_id in review: {sid}")
        seen.add(sid)
        row_status = str(row.get("status") or "")
        if row_status not in REVIEW_STATUSES:
            errors.append(f"test_reviews[{idx}].status invalid: {row_status}")
    return errors


def _recheck_evidence_hashes(history_entry: dict[str, Any], *, base_dirs: list[Path]) -> list[str]:
    warnings: list[str] = []
    for item in history_entry.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        expected = str(item.get("sha256") or "").strip()
        path_text = str(item.get("resolved_path") or item.get("path") or "").strip()
        if not expected or not path_text:
            continue
        candidate = Path(path_text)
        if not candidate.is_file():
            for base in base_dirs:
                alt = (base / path_text).resolve()
                if alt.is_file():
                    candidate = alt
                    break
        if not candidate.is_file():
            warnings.append(f"missing evidence for hash check: {path_text}")
            continue
        actual = _sha256_file(candidate)
        if actual != expected:
            warnings.append(f"evidence hash mismatch: {path_text}")
    return warnings


def prepare_security_review_package(
    case_dir: Path,
    execution_id: str,
    *,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    case_id = _case_id(case_dir)
    execution = load_execution_archive(case_dir, execution_id)
    if execution.get("case_id") != case_id:
        raise SecurityReviewError(
            f"case_id mismatch: execution={execution.get('case_id')!r} case={case_id!r}"
        )

    overlay = load_security_test_results(case_dir) or {}
    plan = load_security_tests(case_dir / "security_tests.json") if (case_dir / "security_tests.json").exists() else {"tests": []}
    synthetic = bool(execution.get("synthetic"))

    package_dir = out_dir or (PROJECT_ROOT / "data" / "review" / case_id / execution_id)
    package_dir.mkdir(parents=True, exist_ok=True)

    evidence_manifest: list[dict[str, Any]] = []
    for row in execution.get("results") or []:
        for item in row.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            path_text = str(item.get("path") or "")
            entry = {
                "security_test_id": row.get("security_test_id"),
                "type": item.get("type"),
                "path": path_text,
                "description": item.get("description"),
                "sha256": item.get("sha256"),
            }
            resolved = Path(str(item.get("resolved_path") or ""))
            if not resolved.is_file():
                for base in (
                    PROJECT_ROOT,
                    case_dir,
                    PROJECT_ROOT / "data" / "executions" / case_id,
                    PROJECT_ROOT / "data" / "executions" / case_id / "evidence",
                ):
                    alt = (base / path_text).resolve()
                    if alt.is_file():
                        resolved = alt
                        break
            if resolved.is_file():
                entry["sha256"] = entry.get("sha256") or _sha256_file(resolved)
                entry["exists"] = True
                try:
                    entry["resolved_path"] = str(resolved.relative_to(PROJECT_ROOT)).replace("\\", "/")
                except ValueError:
                    entry["resolved_path"] = str(resolved).replace("\\", "/")
            else:
                entry["exists"] = False
            evidence_manifest.append(entry)

    template_reviews = []
    for row in execution.get("results") or []:
        sid = str(row.get("security_test_id") or "")
        plan_test = match_plan_test(sid, list(plan.get("tests") or []))
        default_status = "test_fixture_verified" if synthetic else "review_pending"
        template_reviews.append(
            {
                "security_test_id": sid,
                "plan_security_test_id": (plan_test or {}).get("security_test_id"),
                "execution_status": row.get("status"),
                "status": default_status,
                "result_status_confirmed": False,
                "evidence_confirmed": False,
                "evidence_hash_verified": False,
                "selected_for_report": False,
                "note": "SYNTHETIC fixture — not for real gold" if synthetic else "",
            }
        )

    review_template = {
        "case_id": case_id,
        "execution_id": execution_id,
        "reviewer": {"name": "", "role": ""},
        "reviewed_at": _utc_now_iso(),
        "overall_status": "test_fixture_verified" if synthetic else "review_pending",
        "synthetic_acknowledged": synthetic,
        "verification_scope": "fixture_only" if synthetic else "full_execution",
        "note": (
            "Synthetic demonstration package. Do not promote to human-approved execution gold."
            if synthetic
            else "Fill reviewer name and confirm each test before import."
        ),
        "test_reviews": template_reviews,
    }

    instructions = "\n".join(
        [
            f"# Security Execution Review Instructions — {case_id}",
            "",
            f"Execution: `{execution_id}`",
            f"Synthetic: **{synthetic}**",
            "",
            "## Reviewer checklist",
            "",
            "1. Confirm each security_test_id maps to the plan (`security_tests.json`).",
            "2. Confirm actual_result matches attached evidence.",
            "3. Confirm PASS/FAIL judgments are justified (do not invent results).",
            "4. Verify evidence paths and SHA-256 hashes in `evidence_manifest.json`.",
            "5. Ensure sensitive data is not copied into XXCS DOCX.",
            "6. Decide `selected_for_report` per test (final XXCS only).",
            "7. Acknowledge synthetic vs real execution.",
            "",
            "## Rules",
            "",
            "- Do **not** auto-approve imported results.",
            "- Synthetic executions cannot become human-approved execution gold.",
            "- Prefer `test_fixture_verified` + `selected_for_report=false` for synthetic demos.",
            "- Original execution JSON under `executions/` must not be edited.",
            "",
        ]
    )

    summary_lines = [
        f"# Execution Summary — {execution_id}",
        "",
        f"- case_id: `{case_id}`",
        f"- executed_at: {execution.get('executed_at')}",
        f"- executor: {(execution.get('executor') or {}).get('name')}",
        f"- synthetic: {synthetic}",
        f"- result_count: {len(execution.get('results') or [])}",
        "",
        "| Test ID | Status | Actual (truncated) | Evidence |",
        "|---------|--------|------------------|----------|",
    ]
    for row in execution.get("results") or []:
        actual = str(row.get("actual_result") or "")[:60].replace("|", "/")
        ev_count = len(row.get("evidence") or [])
        summary_lines.append(
            f"| {row.get('security_test_id')} | {row.get('status')} | {actual} | {ev_count} |"
        )

    checklist = "\n".join(
        [
            f"# Execution Review Checklist — {execution_id}",
            "",
            "- [ ] Test IDs match plan",
            "- [ ] Actual results match evidence",
            "- [ ] PASS/FAIL judgments justified",
            "- [ ] Evidence paths/hashes valid",
            "- [ ] No sensitive data exposure in DOCX",
            "- [ ] selected_for_report decisions recorded",
            "- [ ] Synthetic acknowledged (if applicable)",
            "",
        ]
    )

    package_manifest = {
        "case_id": case_id,
        "execution_id": execution_id,
        "synthetic": synthetic,
        "created_at": _utc_now_iso(),
        "files": [
            "reviewer_instructions.md",
            "execution_summary.md",
            "execution_review_checklist.md",
            "execution_review.template.json",
            "evidence_manifest.json",
            "package_manifest.json",
        ],
        "overlay_accepted_execution_id": overlay.get("accepted_execution_id"),
    }

    files = {
        "reviewer_instructions.md": instructions,
        "execution_summary.md": "\n".join(summary_lines) + "\n",
        "execution_review_checklist.md": checklist,
        "execution_review.template.json": json.dumps(review_template, ensure_ascii=False, indent=2) + "\n",
        "evidence_manifest.json": json.dumps(evidence_manifest, ensure_ascii=False, indent=2) + "\n",
        "package_manifest.json": json.dumps(package_manifest, ensure_ascii=False, indent=2) + "\n",
    }
    for name, content in files.items():
        (package_dir / name).write_text(content, encoding="utf-8")

    return {
        "case_id": case_id,
        "execution_id": execution_id,
        "synthetic": synthetic,
        "package_dir": str(package_dir),
        "files": list(files.keys()),
        "template_path": str(package_dir / "execution_review.template.json"),
    }


def _apply_review_to_overlay(
    overlay: dict[str, Any],
    *,
    execution: dict[str, Any],
    review: dict[str, Any],
    hash_warnings: list[str],
) -> dict[str, Any]:
    """Update overlay history review fields; never delete history."""
    synthetic = bool(execution.get("synthetic"))
    overall = str(review.get("overall_status") or "review_pending")
    if synthetic and overall == "reviewer_verified":
        raise SecurityReviewError(
            "synthetic execution cannot be overall_status=reviewer_verified; "
            "use test_fixture_verified instead"
        )

    review_by_id = {
        str(row.get("security_test_id") or ""): row for row in review.get("test_reviews") or []
    }
    results_by_test = overlay.setdefault("results_by_test", {})
    selected_rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []

    for test_key, bucket in results_by_test.items():
        for hist in bucket.get("history") or []:
            if hist.get("execution_id") != review.get("execution_id"):
                continue
            matched = None
            for sid, row in review_by_id.items():
                if sid == test_key or sid == hist.get("security_test_id"):
                    matched = row
                    break
                plan_like = {"security_test_id": test_key, "req_id": bucket.get("req_id")}
                if match_plan_test(sid, [plan_like]):
                    matched = row
                    break
            if matched is None:
                # try req_id short form
                for sid, row in review_by_id.items():
                    if sid == bucket.get("req_id") or test_key.startswith(f"{sid}-"):
                        matched = row
                        break
            if matched is None:
                continue

            status = str(matched.get("status") or "review_pending")
            if synthetic and status == "reviewer_verified":
                raise SecurityReviewError(
                    f"synthetic test {test_key} cannot be reviewer_verified; use test_fixture_verified"
                )
            selected = bool(matched.get("selected_for_report"))
            if synthetic and selected and status not in FIXTURE_STATUSES:
                raise SecurityReviewError(
                    f"synthetic test {test_key}: selected_for_report requires test_fixture_verified"
                )
            if selected and status == "rejected":
                raise SecurityReviewError(f"rejected test cannot be selected_for_report: {test_key}")

            hist["review_status"] = status
            hist["reviewer"] = review.get("reviewer")
            hist["reviewed_at"] = review.get("reviewed_at")
            hist["review_note"] = matched.get("note") or review.get("note") or ""
            hist["verification_scope"] = review.get("verification_scope")
            hist["selected_for_report"] = selected and status in SELECTABLE_STATUSES
            hist["result_status_confirmed"] = bool(matched.get("result_status_confirmed"))
            hist["evidence_confirmed"] = bool(matched.get("evidence_confirmed"))
            hist["evidence_hash_verified"] = bool(matched.get("evidence_hash_verified")) and not hash_warnings
            hist["real_execution"] = not synthetic
            hist["synthetic"] = synthetic

            if hist.get("selected_for_report"):
                selected_rows.append(
                    {
                        "security_test_id": test_key,
                        "req_id": bucket.get("req_id"),
                        "execution_id": hist.get("execution_id"),
                        "status": hist.get("status"),
                        "actual_result": hist.get("actual_result"),
                        "evidence": hist.get("evidence"),
                        "executed_at": hist.get("executed_at"),
                        "reviewed_at": hist.get("reviewed_at"),
                        "review_status": hist.get("review_status"),
                        "synthetic": synthetic,
                        "real_execution": not synthetic,
                        "selected_for_report": True,
                        "executor": hist.get("executor"),
                        "has_evidence": hist.get("has_evidence"),
                    }
                )

            # Update accepted pointer only for real reviewer_verified selections
            if status == "reviewer_verified" and not synthetic:
                bucket["accepted"] = copy.deepcopy(hist)
            elif status == "rejected" and (bucket.get("accepted") or {}).get("execution_id") == hist.get(
                "execution_id"
            ):
                # clear accepted if this was the accepted one and now rejected
                bucket["accepted"] = None
            elif status == "test_fixture_verified":
                # keep demo accepted for pipeline demos but mark fixture
                if hist.get("selected_for_report"):
                    bucket["accepted"] = copy.deepcopy(hist)
                elif (bucket.get("accepted") or {}).get("execution_id") == hist.get("execution_id"):
                    # demote auto-accepted synthetic from import unless explicitly selected
                    accepted = bucket.get("accepted") or {}
                    accepted["review_status"] = status
                    accepted["selected_for_report"] = False
                    accepted["real_execution"] = False
                    bucket["accepted"] = accepted

            audit.append(
                {
                    "security_test_id": test_key,
                    "execution_id": hist.get("execution_id"),
                    "review_status": status,
                    "selected_for_report": hist.get("selected_for_report"),
                }
            )

    overlay.setdefault("review_log", []).append(
        {
            "execution_id": review.get("execution_id"),
            "reviewed_at": review.get("reviewed_at"),
            "reviewer": review.get("reviewer"),
            "overall_status": overall,
            "synthetic": synthetic,
            "hash_warnings": hash_warnings,
            "audit": audit,
        }
    )
    return {"selected_rows": selected_rows, "audit": audit}


def select_results_for_report(
    overlay: dict[str, Any],
    *,
    allow_synthetic_demo: bool = False,
) -> dict[str, Any]:
    """
    Selection priority:
    1. selected_for_report=true
    2. reviewer_verified (real)
    3. synthetic=false
    4. latest reviewed_at
    5. latest executed_at
    """
    selected: dict[str, dict[str, Any]] = {}
    ambiguous: list[str] = []

    for test_key, bucket in (overlay.get("results_by_test") or {}).items():
        candidates: list[dict[str, Any]] = []
        for hist in bucket.get("history") or []:
            status = hist.get("review_status")
            synthetic = bool(hist.get("synthetic"))
            if hist.get("selected_for_report") and status in SELECTABLE_STATUSES:
                if synthetic and not allow_synthetic_demo:
                    continue
                if synthetic and status == "reviewer_verified":
                    continue
                candidates.append(hist)
            elif status in FINAL_REPORT_STATUSES and not synthetic:
                candidates.append({**hist, "selected_for_report": True})

        if not candidates:
            continue

        def sort_key(item: dict[str, Any]) -> tuple:
            return (
                1 if item.get("selected_for_report") else 0,
                1 if item.get("review_status") == "reviewer_verified" else 0,
                0 if item.get("synthetic") else 1,
                _parse_ts(item.get("reviewed_at")),
                _parse_ts(item.get("executed_at")),
            )

        candidates.sort(key=sort_key, reverse=True)
        top = candidates[0]
        # Ambiguity: two real verified with same reviewed_at
        if len(candidates) > 1:
            second = candidates[1]
            if (
                sort_key(top)[:4] == sort_key(second)[:4]
                and top.get("execution_id") != second.get("execution_id")
            ):
                ambiguous.append(test_key)
                continue
        selected[test_key] = copy.deepcopy(top)

    return {
        "selected_by_test": selected,
        "ambiguous_test_ids": ambiguous,
        "selected_count": len(selected),
    }


def save_selected_security_results(case_dir: Path, payload: dict[str, Any]) -> Path:
    out = case_dir / "selected_security_results.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_selected_security_results(case_dir: Path) -> dict[str, Any] | None:
    path = case_dir / "selected_security_results.json"
    if not path.exists():
        return None
    return _load_json(path)


def import_security_review(
    case_dir: Path,
    review_path: Path,
    *,
    allow_synthetic_demo_selection: bool = False,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    review_path = review_path.resolve()
    review = _load_json(review_path)

    errors = validate_review_payload(review)
    if errors:
        raise SecurityReviewError("; ".join(errors))

    case_id = _case_id(case_dir)
    if review.get("case_id") != case_id:
        raise SecurityReviewError(
            f"case_id mismatch: review={review.get('case_id')!r} case={case_id!r}"
        )

    execution_id = str(review["execution_id"])
    execution = load_execution_archive(case_dir, execution_id)
    synthetic = bool(execution.get("synthetic"))

    if synthetic and not review.get("synthetic_acknowledged"):
        raise SecurityReviewError("synthetic execution requires synthetic_acknowledged=true")

    if synthetic and review.get("overall_status") == "reviewer_verified":
        raise SecurityReviewError(
            "synthetic execution blocked from overall_status=reviewer_verified"
        )

    overlay = load_security_test_results(case_dir)
    if not overlay:
        raise SecurityReviewError("missing security_test_results.json overlay")

    # Locate history entries for this execution to recheck hashes
    hash_warnings: list[str] = []
    base_dirs = [
        PROJECT_ROOT,
        case_dir,
        PROJECT_ROOT / "data" / "executions" / case_id,
        PROJECT_ROOT / "data" / "executions" / case_id / "evidence",
    ]
    for bucket in (overlay.get("results_by_test") or {}).values():
        for hist in bucket.get("history") or []:
            if hist.get("execution_id") == execution_id:
                hash_warnings.extend(_recheck_evidence_hashes(hist, base_dirs=base_dirs))

    # Blocking hash failures when reviewer claims hash verified
    for row in review.get("test_reviews") or []:
        if row.get("evidence_hash_verified") and hash_warnings:
            raise SecurityReviewError(
                "evidence hash verification failed: " + "; ".join(hash_warnings[:3])
            )

    applied = _apply_review_to_overlay(
        overlay,
        execution=execution,
        review=review,
        hash_warnings=hash_warnings,
    )

    # Persist review record (do not mutate original execution archive)
    reviews_dir = case_dir / "execution_reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_record = {
        **review,
        "imported_at": _utc_now_iso(),
        "source_review_file": str(review_path),
        "synthetic": synthetic,
        "hash_warnings": hash_warnings,
        "audit": applied["audit"],
    }
    record_path = _review_record_path(case_dir, execution_id)
    record_path.write_text(json.dumps(review_record, ensure_ascii=False, indent=2), encoding="utf-8")

    selection = select_results_for_report(
        overlay,
        allow_synthetic_demo=allow_synthetic_demo_selection or synthetic,
    )
    # For synthetic: force selected_for_report false in final report selection unless demo flag
    selected_payload = {
        "case_id": case_id,
        "model_version": "selected-security-results-v1",
        "updated_at": _utc_now_iso(),
        "allow_synthetic_demo": bool(allow_synthetic_demo_selection),
        "ambiguous_test_ids": selection["ambiguous_test_ids"],
        "results_by_test": {},
        "synthetic_selected_count": 0,
        "real_selected_count": 0,
    }
    for test_key, row in selection["selected_by_test"].items():
        if row.get("synthetic") and not allow_synthetic_demo_selection:
            continue
        selected_payload["results_by_test"][test_key] = row
        if row.get("synthetic"):
            selected_payload["synthetic_selected_count"] += 1
        else:
            selected_payload["real_selected_count"] += 1

    save_selected_security_results(case_dir, selected_payload)
    save_security_test_results(case_dir, overlay)

    return {
        "case_id": case_id,
        "execution_id": execution_id,
        "review_record": str(record_path),
        "selected_path": str(case_dir / "selected_security_results.json"),
        "synthetic": synthetic,
        "hash_warnings": hash_warnings,
        "selected_count": len(selected_payload["results_by_test"]),
        "real_selected_count": selected_payload["real_selected_count"],
        "synthetic_selected_count": selected_payload["synthetic_selected_count"],
        "ambiguous_test_ids": selection["ambiguous_test_ids"],
        "audit_count": len(applied["audit"]),
    }


def promote_execution_gold(
    case_dir: Path,
    *,
    execution_id: str,
    reviewer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Promote human-approved real execution to data/gold/xxcs/execution/. Blocks synthetic."""
    case_dir = case_dir.resolve()
    case_id = _case_id(case_dir)
    execution = load_execution_archive(case_dir, execution_id)
    if execution.get("synthetic"):
        raise SecurityReviewError(
            "synthetic execution cannot be promoted to human-approved execution gold"
        )

    selected = load_selected_security_results(case_dir) or {}
    if selected.get("synthetic_selected_count", 0):
        raise SecurityReviewError("selected synthetic results block gold promotion")

    review_path = _review_record_path(case_dir, execution_id)
    if not review_path.exists():
        raise SecurityReviewError(f"missing review record: {review_path}")
    review = _load_json(review_path)
    if review.get("overall_status") not in FINAL_REPORT_STATUSES:
        raise SecurityReviewError(
            f"gold promotion requires overall_status=reviewer_verified, got {review.get('overall_status')}"
        )

    gen = case_dir / "output_xxcs.docx"
    if not gen.exists():
        raise SecurityReviewError(f"missing generated XXCS: {gen}")

    out_dir = PROJECT_ROOT / "data" / "gold" / "xxcs" / "execution"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{case_id}.docx"
    dest.write_bytes(gen.read_bytes())

    manifest_path = out_dir / "manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {"entries": []}
    entry = {
        "case_id": case_id,
        "gold_type": "execution",
        "execution_id": execution_id,
        "review_status": review.get("overall_status"),
        "reviewer": reviewer or review.get("reviewer"),
        "synthetic": False,
        "frozen_at": _utc_now_iso(),
        "path": str(dest.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }
    entries = [e for e in manifest.get("entries") or [] if e.get("case_id") != case_id]
    entries.append(entry)
    manifest["entries"] = entries
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def ensure_plan_gold_layout(case_id: str = "lab_ec_sw") -> dict[str, Any]:
    """Ensure plan gold directory exists and is documented separately from execution gold."""
    plan_dir = PROJECT_ROOT / "data" / "gold" / "xxcs" / "plan"
    exec_dir = PROJECT_ROOT / "data" / "gold" / "xxcs" / "execution"
    plan_dir.mkdir(parents=True, exist_ok=True)
    exec_dir.mkdir(parents=True, exist_ok=True)
    readme = PROJECT_ROOT / "data" / "gold" / "xxcs" / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# XXCS Gold Dataset",
                "",
                "## Layout",
                "",
                "- `plan/` — plan-based XXCS gold (method/procedure/expected; NOT_EXECUTED placeholders OK)",
                "- `execution/` — human-approved real execution gold only (`reviewer_verified`, synthetic=false)",
                "",
                "Do not mix plan and execution gold in the same comparison bucket.",
                "Synthetic fixtures must never be promoted to `execution/`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    plan_manifest = plan_dir / "manifest.json"
    if not plan_manifest.exists():
        plan_manifest.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "case_id": case_id,
                            "gold_type": "plan",
                            "synthetic": False,
                            "note": "Use independent plan gold / case gold_xxcs.docx for plan validation",
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return {"plan_dir": str(plan_dir), "execution_dir": str(exec_dir)}


def compute_review_metrics(
    plan_tests: list[dict[str, Any]],
    overlay: dict[str, Any] | None,
    selected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overlay = overlay or {}
    selected = selected or {}
    results_by_test = overlay.get("results_by_test") or {}
    selected_by = selected.get("results_by_test") or {}
    total = len(plan_tests) or 1

    verified = 0
    selected_count = 0
    verified_evidence = 0
    unresolved = 0
    synthetic_count = 0
    real_count = 0
    fixture_count = 0

    for test in plan_tests:
        key = _plan_test_key(test)
        bucket = results_by_test.get(key) or {}
        for hist in bucket.get("history") or []:
            if hist.get("synthetic"):
                synthetic_count += 1
            elif hist.get("status") in EXECUTED_STATUSES:
                real_count += 1
            rs = hist.get("review_status")
            if rs in {"imported", "review_pending"} or hist.get("status") == "REVIEW_REQUIRED":
                if rs not in FINAL_REPORT_STATUSES | FIXTURE_STATUSES | {"rejected", "superseded"}:
                    unresolved += 1
            if rs == "test_fixture_verified":
                fixture_count += 1

        sel = selected_by.get(key)
        accepted = bucket.get("accepted")
        candidate = sel or (
            accepted
            if accepted and accepted.get("review_status") in FINAL_REPORT_STATUSES
            else None
        )
        if candidate and candidate.get("review_status") in FINAL_REPORT_STATUSES and not candidate.get("synthetic"):
            verified += 1
            if candidate.get("has_evidence") or candidate.get("evidence_confirmed"):
                verified_evidence += 1
        if sel and sel.get("selected_for_report"):
            selected_count += 1

    readiness = compute_final_report_readiness(overlay, selected)

    return {
        "reviewer_verified_execution_coverage": round(verified / total, 3),
        "selected_result_coverage": round(selected_count / total, 3),
        "verified_evidence_coverage": round(verified_evidence / total, 3),
        "unresolved_review_count": unresolved,
        "synthetic_result_count": synthetic_count,
        "real_execution_count": real_count,
        "fixture_verified_count": fixture_count,
        "final_report_readiness": readiness["ready"],
        "final_report_readiness_score": readiness["score"],
        "final_report_blockers": readiness["blockers"],
    }


def compute_final_report_readiness(
    overlay: dict[str, Any] | None,
    selected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overlay = overlay or {}
    selected = selected or {}
    blockers: list[str] = []
    selected_by = selected.get("results_by_test") or {}

    if selected.get("synthetic_selected_count", 0) and not selected.get("allow_synthetic_demo"):
        blockers.append("synthetic results selected for final report")

    for key, row in selected_by.items():
        if row.get("synthetic") and not selected.get("allow_synthetic_demo"):
            blockers.append(f"synthetic selected: {key}")
        allowed = FINAL_REPORT_STATUSES | (
            FIXTURE_STATUSES if selected.get("allow_synthetic_demo") else frozenset()
        )
        if row.get("review_status") not in allowed:
            blockers.append(f"selected result not reviewer_verified: {key}")
        if row.get("status") in EXECUTED_STATUSES and not row.get("has_evidence"):
            blockers.append(f"PASS/FAIL without evidence: {key}")

    for bucket in (overlay.get("results_by_test") or {}).values():
        for hist in bucket.get("history") or []:
            if hist.get("status") == "REVIEW_REQUIRED" and hist.get("review_status") not in {
                "rejected",
                "superseded",
                "reviewer_verified",
                "test_fixture_verified",
            }:
                blockers.append(
                    f"unresolved REVIEW_REQUIRED: {bucket.get('security_test_id')}"
                )

    if not selected_by:
        # Plan-only: ready for plan report; final execution report not claimed
        ready = len([b for b in blockers if "REVIEW_REQUIRED" in b]) == 0
        # unresolved REVIEW_REQUIRED still blocks "final report" claim
        if any("REVIEW_REQUIRED" in b for b in blockers):
            ready = False
        else:
            ready = True  # no execution selection required for plan-only
        score = 1.0 if ready else max(0.0, 1.0 - 0.15 * len(blockers))
        return {
            "ready": ready,
            "score": round(score, 3),
            "blockers": blockers[:20],
            "selected_count": 0,
            "mode": "plan_only",
        }

    if selected.get("allow_synthetic_demo"):
        ready = len(blockers) == 0
    else:
        ready = len(blockers) == 0 and all(
            not r.get("synthetic") and r.get("review_status") in FINAL_REPORT_STATUSES
            for r in selected_by.values()
        )

    score = 1.0 if ready else max(0.0, 1.0 - 0.15 * len(blockers))
    return {
        "ready": ready,
        "score": round(score, 3),
        "blockers": blockers[:20],
        "selected_count": len(selected_by),
        "mode": "execution",
    }


def build_report_security_payload(
    case_dir: Path,
    *,
    mode: str = "auto",
) -> dict[str, Any]:
    """
    Build XXCS payload for render.

    mode:
      - plan: plan only
      - selected: only selected_for_report results
      - auto: selected if present else accepted overlay (with synthetic labels)
    """
    from document_ai.form_fill.security_execution import apply_accepted_execution

    case_dir = case_dir.resolve()
    plan_path = case_dir / "security_tests.json"
    if not plan_path.exists():
        return {"tests": []}
    plan_payload = load_security_tests(plan_path)
    overlay = load_security_test_results(case_dir) or {}
    selected = load_selected_security_results(case_dir) or {}
    selected_by = selected.get("results_by_test") or {}

    effective_tests: list[dict[str, Any]] = []
    for test in plan_payload.get("tests") or []:
        key = _plan_test_key(test)
        bucket = (overlay.get("results_by_test") or {}).get(key)
        if mode == "plan":
            effective_tests.append(copy.deepcopy(test))
            continue

        sel = selected_by.get(key) if mode in {"selected", "auto"} else None
        if sel:
            entry = {"accepted": sel, "history": (bucket or {}).get("history") or []}
            applied = apply_accepted_execution(test, entry)
            if sel.get("synthetic"):
                applied["satisfaction"] = f"SYNTHETIC_{sel.get('status')}"
                applied["reviewer_note"] = (
                    str(applied.get("reviewer_note") or "")
                    + " | Synthetic / Demonstration Result — not human-approved gold"
                ).strip(" |")
                applied["execution_synthetic"] = True
                provenance = dict(applied.get("provenance") or {})
                provenance["execution_truth"] = "synthetic demonstration result"
                provenance["real_execution"] = False
                applied["provenance"] = provenance
            else:
                provenance = dict(applied.get("provenance") or {})
                provenance["real_execution"] = True
                provenance["review_status"] = sel.get("review_status")
                applied["provenance"] = provenance
            effective_tests.append(applied)
            continue

        if mode == "selected":
            effective_tests.append(copy.deepcopy(test))
            continue

        # auto fallback: only real reviewer_verified accepted results enter XXCS.
        # Synthetic / unverified imports stay as plan placeholders unless explicitly selected.
        accepted = (bucket or {}).get("accepted") or {}
        if (
            accepted
            and not accepted.get("synthetic")
            and accepted.get("review_status") in FINAL_REPORT_STATUSES
        ):
            applied = apply_accepted_execution(test, bucket)
            provenance = dict(applied.get("provenance") or {})
            provenance["real_execution"] = True
            provenance["review_status"] = accepted.get("review_status")
            applied["provenance"] = provenance
            effective_tests.append(applied)
        else:
            effective_tests.append(copy.deepcopy(test))

    readiness = compute_final_report_readiness(overlay, selected)
    return {
        **plan_payload,
        "tests": effective_tests,
        "execution_overlay": {
            "accepted_execution_id": overlay.get("accepted_execution_id"),
            "execution_count": len(overlay.get("executions") or []),
            "selected_count": len(selected_by),
            "final_report_readiness": readiness["ready"],
        },
        "report_mode": mode,
    }


def security_review_summary(case_dir: Path) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    case_id = _case_id(case_dir)
    overlay = load_security_test_results(case_dir) or {}
    selected = load_selected_security_results(case_dir) or {}
    plan_tests = []
    if (case_dir / "security_tests.json").exists():
        plan_tests = load_security_tests(case_dir / "security_tests.json").get("tests") or []

    reviews_dir = case_dir / "execution_reviews"
    review_files = sorted(reviews_dir.glob("*.review.json")) if reviews_dir.exists() else []
    execution_summaries = []
    for path in review_files:
        data = _load_json(path)
        execution_summaries.append(
            {
                "execution_id": data.get("execution_id"),
                "overall_status": data.get("overall_status"),
                "reviewer": data.get("reviewer"),
                "reviewed_at": data.get("reviewed_at"),
                "synthetic": data.get("synthetic"),
                "test_review_count": len(data.get("test_reviews") or []),
                "selected_tests": [
                    r.get("security_test_id")
                    for r in data.get("test_reviews") or []
                    if r.get("selected_for_report")
                ],
            }
        )

    metrics = compute_review_metrics(plan_tests, overlay, selected)
    readiness = compute_final_report_readiness(overlay, selected)

    status_counts = {"PASS": 0, "FAIL": 0, "REVIEW_REQUIRED": 0, "NOT_EXECUTED": 0, "other": 0}
    for bucket in (overlay.get("results_by_test") or {}).values():
        for hist in bucket.get("history") or []:
            st = str(hist.get("status") or "other")
            if st in status_counts:
                status_counts[st] += 1
            else:
                status_counts["other"] += 1

    summary = {
        "case_id": case_id,
        "generated_at": _utc_now_iso(),
        "executions": overlay.get("executions") or [],
        "execution_reviews": execution_summaries,
        "selected_results": selected.get("results_by_test") or {},
        "status_counts": status_counts,
        "metrics": metrics,
        "final_report_readiness": readiness,
        "notes": [
            "Synthetic results are excluded from real execution metrics and gold promotion.",
            "Plan gold and execution gold remain separate.",
        ],
    }

    out_json = case_dir / "security_review_summary.json"
    out_md = case_dir / "security_review_summary.md"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Security Review Summary - {case_id}",
        "",
        f"**Generated:** {summary['generated_at']}",
        "",
        "## Final report readiness",
        "",
        f"- ready: **{readiness['ready']}**",
        f"- score: {readiness['score']}",
        f"- selected_count: {readiness['selected_count']}",
    ]
    if readiness["blockers"]:
        md_lines.append("- blockers:")
        for b in readiness["blockers"]:
            md_lines.append(f"  - {b}")
    md_lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|--------|------:|",
        ]
    )
    for key, value in metrics.items():
        if key == "final_report_blockers":
            continue
        md_lines.append(f"| {key} | {value} |")

    md_lines.extend(["", "## Execution reviews", ""])
    if not execution_summaries:
        md_lines.append("- (none)")
    for row in execution_summaries:
        md_lines.append(
            f"- `{row['execution_id']}` — {row['overall_status']} "
            f"(synthetic={row.get('synthetic')}, selected={row.get('selected_tests')})"
        )

    md_lines.extend(
        [
            "",
            "## Status counts (history)",
            "",
            f"- PASS: {status_counts['PASS']}",
            f"- FAIL: {status_counts['FAIL']}",
            f"- REVIEW_REQUIRED: {status_counts['REVIEW_REQUIRED']}",
            f"- NOT_EXECUTED: {status_counts['NOT_EXECUTED']}",
            "",
        ]
    )
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    summary["report_paths"] = {"json": str(out_json), "markdown": str(out_md)}
    return summary
