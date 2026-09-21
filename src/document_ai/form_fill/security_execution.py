"""Import, merge, and apply external security test execution results."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.form_fill.security_tests import normalize_security_id
from document_ai.learn.extract_security_tests import load_security_tests, save_security_tests
from document_ai.paths import PROJECT_ROOT

EXECUTION_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "security_test_execution.schema.json"
VALID_STATUSES = frozenset({"PASS", "FAIL", "NOT_EXECUTED", "NOT_APPLICABLE", "REVIEW_REQUIRED"})
VALID_REVIEW_STATUSES = frozenset(
    {
        "imported",
        "review_pending",
        "reviewer_verified",
        "rejected",
        "superseded",
        "test_fixture_verified",
    }
)
EXECUTED_STATUSES = frozenset({"PASS", "FAIL"})
NON_OVERWRITE_STATUSES = frozenset({"NOT_EXECUTED", "NOT_APPLICABLE"})


class SecurityExecutionImportError(ValueError):
    """Raised when execution import validation fails."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_execution_status(value: str) -> str:
    raw = (value or "").strip().upper().replace(" ", "_")
    aliases = {
        "PASSED": "PASS",
        "FAILED": "FAIL",
        "NOTEXECUTED": "NOT_EXECUTED",
        "NOTAPPLICABLE": "NOT_APPLICABLE",
        "REVIEWREQUIRED": "REVIEW_REQUIRED",
        "만족": "PASS",
    }
    status = aliases.get(raw, raw)
    if status not in VALID_STATUSES:
        raise SecurityExecutionImportError(f"unsupported status: {value!r}")
    return status


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_execution_payload(payload: dict[str, Any]) -> list[str]:
    """Lightweight schema validation without external jsonschema dependency."""
    errors: list[str] = []
    for key in ("case_id", "execution_id", "executed_at", "executor", "results"):
        if key not in payload:
            errors.append(f"missing required field: {key}")
    if errors:
        return errors

    if not isinstance(payload.get("results"), list) or not payload["results"]:
        errors.append("results must be a non-empty array")

    executor = payload.get("executor")
    if not isinstance(executor, dict):
        errors.append("executor must be an object")
    else:
        if not executor.get("type"):
            errors.append("executor.type is required")
        elif executor["type"] not in {"human", "script", "external_tool"}:
            errors.append(f"invalid executor.type: {executor['type']}")
        if not str(executor.get("name") or "").strip():
            errors.append("executor.name is required")

    exec_id = str(payload.get("execution_id") or "")
    if not re.match(r"^exec-[A-Za-z0-9._-]+$", exec_id):
        errors.append(f"invalid execution_id format: {exec_id}")

    seen_ids: set[str] = set()
    for idx, row in enumerate(payload.get("results") or []):
        if not isinstance(row, dict):
            errors.append(f"results[{idx}] must be an object")
            continue
        sid = str(row.get("security_test_id") or "").strip()
        if not sid:
            errors.append(f"results[{idx}].security_test_id is required")
            continue
        if sid in seen_ids:
            errors.append(f"duplicate security_test_id in execution file: {sid}")
        seen_ids.add(sid)
        try:
            normalize_execution_status(str(row.get("status") or ""))
        except SecurityExecutionImportError as exc:
            errors.append(f"results[{idx}].status: {exc}")

        evidence = row.get("evidence")
        if evidence is not None and not isinstance(evidence, list):
            errors.append(f"results[{idx}].evidence must be an array")

    return errors


def match_plan_test(security_test_id: str, plan_tests: list[dict[str, Any]]) -> dict[str, Any] | None:
    token = (security_test_id or "").strip()
    normalized = normalize_security_id(token)
    for test in plan_tests:
        if str(test.get("security_test_id") or "") == token:
            return test
        if normalize_security_id(str(test.get("security_test_id") or "")) == normalized:
            return test
        if normalize_security_id(str(test.get("req_id") or "")) == normalized:
            return test
    return None


def _resolve_path(path_text: str, *, base_dirs: list[Path]) -> Path | None:
    raw = (path_text or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_file():
        return candidate.resolve()
    for base in base_dirs:
        resolved = (base / raw).resolve()
        if resolved.is_file():
            return resolved
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_evidence_path(path: Path, *, base_dirs: list[Path]) -> str:
    candidates = [PROJECT_ROOT, *base_dirs]
    for base in candidates:
        try:
            return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
        except ValueError:
            continue
    return path.name


def enrich_evidence(
    evidence_items: list[Any],
    *,
    base_dirs: list[Path],
) -> tuple[list[dict[str, Any]], list[str]]:
    enriched: list[dict[str, Any]] = []
    warnings: list[str] = []
    for idx, item in enumerate(evidence_items or []):
        if isinstance(item, str):
            item = {"type": "text", "content": item}
        if not isinstance(item, dict):
            warnings.append(f"evidence[{idx}] ignored: not an object")
            continue
        ev_type = str(item.get("type") or "text")
        entry = dict(item)
        entry["type"] = ev_type
        path_text = str(item.get("path") or "").strip()
        if path_text:
            resolved = _resolve_path(path_text, base_dirs=base_dirs)
            if resolved:
                entry["path"] = _relative_evidence_path(resolved, base_dirs=base_dirs)
                entry["resolved_path"] = str(resolved)
                entry.setdefault("sha256", _sha256_file(resolved))
            else:
                warnings.append(f"missing evidence file: {path_text}")
                entry["path"] = path_text.replace("\\", "/")
        elif item.get("content"):
            content = str(item.get("content") or "")
            if len(content) > 240:
                entry["content"] = content[:240] + "…"
            entry.setdefault("description", str(item.get("description") or "inline text evidence"))
        enriched.append(entry)
    return enriched, warnings


def has_meaningful_evidence(evidence: list[dict[str, Any]] | None) -> bool:
    if not evidence:
        return False
    for item in evidence:
        resolved = item.get("resolved_path") or item.get("path")
        if resolved and Path(str(resolved)).exists():
            return True
        if item.get("path") and item.get("sha256"):
            return True
        if str(item.get("content") or "").strip():
            return True
        if str(item.get("url") or "").strip():
            return True
    return False


def format_evidence_summary(evidence: Any) -> str:
    if isinstance(evidence, str):
        return evidence
    if not isinstance(evidence, list):
        return str(evidence or "")
    parts: list[str] = []
    for item in evidence:
        if not isinstance(item, dict):
            parts.append(str(item))
            continue
        label = item.get("type") or "evidence"
        path = item.get("path") or item.get("url") or item.get("description") or ""
        if isinstance(path, str) and len(path) > 80:
            path = "…" + path[-60:].replace("\\", "/")
        sha = item.get("sha256")
        summary = f"[{label}] {path}".strip()
        if sha:
            summary += f" (sha256={sha[:12]}...)"
        parts.append(summary)
    return "; ".join(p for p in parts if p)


def _plan_test_key(test: dict[str, Any]) -> str:
    return str(test.get("security_test_id") or test.get("req_id") or "")


def load_security_test_results(case_dir: Path) -> dict[str, Any] | None:
    path = case_dir / "security_test_results.json"
    if not path.exists():
        return None
    return _load_json(path)


def save_security_test_results(case_dir: Path, payload: dict[str, Any]) -> Path:
    out = case_dir / "security_test_results.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _empty_overlay(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "model_version": "security-test-results-v1",
        "accepted_execution_id": None,
        "executions": [],
        "results_by_test": {},
        "warnings": [],
        "import_log": [],
    }


def _parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _should_accept_result(
    current: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> bool:
    status = candidate.get("status")
    if status in NON_OVERWRITE_STATUSES:
        return False
    if status == "REVIEW_REQUIRED":
        return False
    if status == "PASS" and not candidate.get("has_evidence"):
        return False
    if current is None:
        return status in EXECUTED_STATUSES
    if current.get("review_status") == "reviewer_verified":
        if candidate.get("review_status") != "reviewer_verified":
            return _parse_ts(candidate.get("executed_at")) > _parse_ts(current.get("executed_at"))
    return _parse_ts(candidate.get("executed_at")) >= _parse_ts(current.get("executed_at"))


def merge_execution_result(
    overlay: dict[str, Any],
    *,
    execution_meta: dict[str, Any],
    plan_test: dict[str, Any],
    result_row: dict[str, Any],
    warnings: list[str],
) -> None:
    test_key = _plan_test_key(plan_test)
    bucket = overlay.setdefault("results_by_test", {}).setdefault(
        test_key,
        {"security_test_id": test_key, "req_id": plan_test.get("req_id"), "history": [], "accepted": None},
    )
    status = normalize_execution_status(str(result_row.get("status") or ""))
    evidence, evidence_warnings = enrich_evidence(
        list(result_row.get("evidence") or []),
        base_dirs=list(execution_meta.get("evidence_base_dirs") or []),
    )
    warnings.extend(evidence_warnings)

    history_entry = {
        "execution_id": execution_meta["execution_id"],
        "executed_at": result_row.get("executed_at") or execution_meta.get("executed_at"),
        "status": status,
        "actual_result": str(result_row.get("actual_result") or "").strip(),
        "evidence": evidence,
        "executor_note": str(result_row.get("executor_note") or "").strip(),
        "executor": execution_meta.get("executor"),
        "environment": execution_meta.get("environment"),
        "synthetic": bool(execution_meta.get("synthetic")),
        "review_status": "imported",
        "has_evidence": has_meaningful_evidence(evidence),
        "source_file": execution_meta.get("source_file"),
        "imported_at": execution_meta.get("imported_at"),
    }
    if status == "PASS" and not history_entry["has_evidence"]:
        warnings.append(f"{test_key}: PASS without evidence -> review required")
        history_entry["review_status"] = "imported"
    if status == "REVIEW_REQUIRED":
        history_entry["review_status"] = "imported"

    bucket["history"].append(history_entry)

    current = bucket.get("accepted")
    if status in NON_OVERWRITE_STATUSES:
        return
    if _should_accept_result(current, history_entry):
        accepted = copy.deepcopy(history_entry)
        bucket["accepted"] = accepted
        overlay["accepted_execution_id"] = execution_meta["execution_id"]


def import_security_results(
    case_dir: Path,
    results_path: Path,
    *,
    accept: bool = True,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    results_path = results_path.resolve()
    payload = _load_json(results_path)

    errors = validate_execution_payload(payload)
    if errors:
        raise SecurityExecutionImportError("; ".join(errors))

    input_path = case_dir / "input.json"
    case_id = json.loads(input_path.read_text(encoding="utf-8")).get("case_id", case_dir.name) if input_path.exists() else case_dir.name
    if payload.get("case_id") != case_id:
        raise SecurityExecutionImportError(
            f"case_id mismatch: file={payload.get('case_id')!r} case={case_id!r}"
        )

    plan_path = case_dir / "security_tests.json"
    if not plan_path.exists():
        raise SecurityExecutionImportError(f"missing plan file: {plan_path}")
    plan_payload = load_security_tests(plan_path)
    plan_tests = list(plan_payload.get("tests") or [])

    execution_id = str(payload["execution_id"])
    executions_dir = case_dir / "executions"
    executions_dir.mkdir(parents=True, exist_ok=True)
    archived = executions_dir / f"{execution_id}.json"
    archived.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    overlay = load_security_test_results(case_dir) or _empty_overlay(case_id)
    if any(row.get("execution_id") == execution_id for row in overlay.get("executions") or []):
        raise SecurityExecutionImportError(f"execution_id already imported: {execution_id}")

    evidence_base_dirs = [
        results_path.parent,
        case_dir,
        case_dir / "executions",
        PROJECT_ROOT / "data" / "executions" / case_id,
        PROJECT_ROOT / "data" / "executions" / case_id / "evidence",
    ]
    execution_meta = {
        "execution_id": execution_id,
        "executed_at": payload.get("executed_at"),
        "executor": payload.get("executor"),
        "environment": payload.get("environment"),
        "synthetic": bool(payload.get("synthetic")),
        "source_file": (
            str(archived.relative_to(case_dir))
            if str(archived).startswith(str(case_dir))
            else str(archived)
        ),
        "imported_at": _utc_now_iso(),
        "evidence_base_dirs": evidence_base_dirs,
    }
    overlay.setdefault("executions", []).append(
        {
            "execution_id": execution_id,
            "executed_at": payload.get("executed_at"),
            "executor": payload.get("executor"),
            "environment": payload.get("environment"),
            "synthetic": bool(payload.get("synthetic")),
            "source_file": execution_meta["source_file"],
            "imported_at": execution_meta["imported_at"],
            "result_count": len(payload.get("results") or []),
        }
    )

    warnings: list[str] = []
    imported = 0
    for row in payload.get("results") or []:
        plan_test = match_plan_test(str(row.get("security_test_id") or ""), plan_tests)
        if not plan_test:
            raise SecurityExecutionImportError(
                f"unknown security_test_id: {row.get('security_test_id')!r}"
            )
        merge_execution_result(
            overlay,
            execution_meta=execution_meta,
            plan_test=plan_test,
            result_row=row,
            warnings=warnings,
        )
        imported += 1

    if accept:
        overlay["accepted_execution_id"] = execution_id

    overlay.setdefault("warnings", []).extend(warnings)
    overlay.setdefault("import_log", []).append(
        {
            "execution_id": execution_id,
            "imported_at": execution_meta["imported_at"],
            "source": str(results_path),
            "results_imported": imported,
            "warnings": len(warnings),
        }
    )
    save_security_test_results(case_dir, overlay)

    return {
        "case_id": case_id,
        "execution_id": execution_id,
        "archived_execution": str(archived),
        "results_imported": imported,
        "warnings": warnings,
        "accepted_execution_id": overlay.get("accepted_execution_id"),
        "overlay_path": str(case_dir / "security_test_results.json"),
    }


def apply_accepted_execution(plan_test: dict[str, Any], overlay_entry: dict[str, Any] | None) -> dict[str, Any]:
    """Merge plan fields with accepted execution without mutating the plan source."""
    effective = copy.deepcopy(plan_test)
    accepted = (overlay_entry or {}).get("accepted")
    if not accepted:
        return effective

    status = accepted.get("status")
    if status in NON_OVERWRITE_STATUSES:
        return effective

    effective["actual_result"] = accepted.get("actual_result") or effective.get("actual_result")
    effective["satisfaction"] = status
    effective["execution_status"] = "executed" if status in EXECUTED_STATUSES else str(status or "").lower()
    effective["evidence"] = format_evidence_summary(accepted.get("evidence"))
    effective["executed_at"] = accepted.get("executed_at")
    effective["executor"] = accepted.get("executor")
    effective["execution_id"] = accepted.get("execution_id")
    effective["review_status"] = accepted.get("review_status")
    effective["execution_synthetic"] = accepted.get("synthetic")
    provenance = dict(effective.get("provenance") or {})
    provenance.update(
        {
            "execution_source": accepted.get("source_file"),
            "execution_truth": "imported external result" if not accepted.get("synthetic") else "synthetic sample result",
            "review_status": accepted.get("review_status"),
        }
    )
    effective["provenance"] = provenance
    return effective


def build_effective_security_payload(case_dir: Path) -> dict[str, Any]:
    """Build XXCS payload using selected/reviewed results when available."""
    from document_ai.form_fill.security_execution_review import build_report_security_payload

    return build_report_security_payload(case_dir, mode="auto")


def compute_execution_metrics(
    plan_tests: list[dict[str, Any]],
    overlay: dict[str, Any] | None,
) -> dict[str, Any]:
    overlay = overlay or {}
    results_by_test = overlay.get("results_by_test") or {}
    total = len(plan_tests) or 1
    executed = 0
    with_evidence = 0
    executed_complete = 0
    pass_with_evidence = 0
    fail_with_evidence = 0
    pass_total = 0
    fail_total = 0
    unresolved_review = 0
    stale = 0
    accepted_execution_id = overlay.get("accepted_execution_id")

    for test in plan_tests:
        key = _plan_test_key(test)
        entry = results_by_test.get(key) or {}
        accepted = entry.get("accepted")
        if accepted and accepted.get("status") in EXECUTED_STATUSES:
            executed += 1
            if accepted.get("has_evidence"):
                with_evidence += 1
            if str(accepted.get("actual_result") or "").strip():
                executed_complete += 1
            if accepted.get("status") == "PASS":
                pass_total += 1
                if accepted.get("has_evidence"):
                    pass_with_evidence += 1
            if accepted.get("status") == "FAIL":
                fail_total += 1
                if accepted.get("has_evidence"):
                    fail_with_evidence += 1
        for hist in entry.get("history") or []:
            if hist.get("status") == "REVIEW_REQUIRED" and hist.get("review_status") != "reviewer_verified":
                unresolved_review += 1
            if accepted_execution_id and hist.get("execution_id") != accepted_execution_id:
                if hist.get("status") in EXECUTED_STATUSES and hist.get("review_status") != "superseded":
                    stale += 1

    synthetic_executed = 0
    real_executed = 0
    for test in plan_tests:
        key = _plan_test_key(test)
        accepted = (results_by_test.get(key) or {}).get("accepted")
        if accepted and accepted.get("status") in EXECUTED_STATUSES:
            if accepted.get("synthetic"):
                synthetic_executed += 1
            else:
                real_executed += 1

    return {
        "execution_coverage": round(executed / total, 3),
        "evidence_coverage": round(with_evidence / total, 3),
        "executed_result_completeness": round(executed_complete / total, 3),
        "pass_with_evidence_ratio": round(pass_with_evidence / pass_total, 3) if pass_total else 1.0,
        "fail_with_evidence_ratio": round(fail_with_evidence / fail_total, 3) if fail_total else 1.0,
        "unresolved_review_required_count": unresolved_review,
        "stale_execution_count": stale,
        "execution_readiness": round((executed + with_evidence) / (2 * total), 3),
        "plan_test_count": len(plan_tests),
        "executed_test_count": executed,
        # Real-only coverage excludes synthetic fixtures from paper metrics
        "real_execution_coverage": round(real_executed / total, 3),
        "synthetic_execution_count": synthetic_executed,
        "real_execution_count": real_executed,
    }


def plan_field_completeness(test: dict[str, Any]) -> float:
    fields = ("test_method", "test_procedure", "expected_result")
    present = sum(1 for field in fields if str(test.get(field) or "").strip())
    return present / len(fields)


def execution_field_completeness(test: dict[str, Any], accepted: dict[str, Any] | None) -> float:
    if not accepted or accepted.get("status") not in EXECUTED_STATUSES:
        if str(test.get("satisfaction") or "") in {"NOT_EXECUTED", "NOT_APPLICABLE"}:
            return 1.0
        return 0.0
    fields = ("actual_result", "status")
    present = sum(1 for field in fields if str(accepted.get(field) or "").strip())
    evidence_ok = 1.0 if accepted.get("has_evidence") else 0.0
    return (present / len(fields) + evidence_ok) / 2
