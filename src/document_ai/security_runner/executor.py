"""Orchestrate read-only checks and emit the existing execution schema."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.form_fill.security_execution import (
    SecurityExecutionImportError,
    validate_execution_payload,
)
from document_ai.learn.extract_security_tests import load_security_tests
from document_ai.security_runner.evidence import write_manifest
from document_ai.security_runner.models import RunnerContext, SecurityCheckResult, utc_now_iso
from document_ai.security_runner.policy import (
    SecurityRunnerConfigError,
    load_runner_config,
    validate_runner_config,
)
from document_ai.security_runner.registry import create_check

RUNNER_NAME = "document-ai-security-runner"
RUNNER_VERSION = "0.1.0"


def _default_execution_id(*, synthetic: bool) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    kind = "synthetic" if synthetic else "readonly"
    return f"exec-{stamp}-{kind}"


def _case_id(case_dir: Path) -> str:
    input_path = case_dir / "input.json"
    if input_path.exists():
        return str(json.loads(input_path.read_text(encoding="utf-8")).get("case_id") or case_dir.name)
    return case_dir.name


def _known_test_ids(case_dir: Path) -> set[str]:
    plan_path = case_dir / "security_tests.json"
    if not plan_path.exists():
        raise SecurityRunnerConfigError(f"missing security plan: {plan_path}")
    known: set[str] = set()
    for row in load_security_tests(plan_path).get("tests") or []:
        for key in ("security_test_id", "req_id"):
            value = str(row.get(key) or "").strip()
            if value:
                known.add(value)
    return known


def _evidence_filename(check: dict[str, Any]) -> str:
    suffixes = {
        "tls_check": "tls",
        "http_header_check": "headers",
        "api_health_check": "api_health",
        "port_connectivity_check": "port",
    }
    sid = str(check.get("security_test_id") or "unknown")
    return f"{sid}_{suffixes.get(str(check.get('runner')), 'check')}.json"


def dry_run_security_tests(
    case_dir: Path,
    config_path: Path,
    *,
    output_path: Path,
    selected_check: str | None = None,
    timeout: float | None = None,
    execution_id: str | None = None,
    synthetic: bool = False,
    no_network: bool = False,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    config = load_runner_config(config_path.resolve())
    case_id = _case_id(case_dir)
    known_ids = _known_test_ids(case_dir)
    errors = validate_runner_config(
        config,
        case_id=case_id,
        known_security_test_ids=known_ids,
        selected_check=selected_check,
        resolve_dns=False,
    )
    checks = [
        row
        for row in config.get("checks") or []
        if not selected_check
        or selected_check in {
            str(row.get("security_test_id") or ""),
            str(row.get("check_id") or ""),
        }
    ]
    if selected_check and not checks:
        errors.append(f"selected check not found: {selected_check}")
    for row in checks:
        if row.get("enabled", True):
            try:
                errors.extend(
                    f"{row.get('security_test_id')}: {message}"
                    for message in create_check(
                        str(row.get("runner") or ""),
                        str(row.get("security_test_id") or ""),
                    ).validate_config(row)
                )
            except ValueError as exc:
                errors.append(str(exc))
    if errors:
        raise SecurityRunnerConfigError("; ".join(errors))

    is_synthetic = bool(synthetic or config.get("synthetic"))
    effective_no_network = bool(no_network or is_synthetic)
    eid = execution_id or _default_execution_id(synthetic=is_synthetic)
    evidence_dir = output_path.parent / output_path.stem
    target = config.get("target") or {}
    return {
        "mode": "dry_run",
        "case_id": case_id,
        "execution_id": eid,
        "synthetic": is_synthetic,
        "no_network": effective_no_network,
        "network_requests_performed": 0,
        "timeout": float(timeout or config.get("timeout_seconds") or 5.0),
        "target": {
            "base_url": target.get("base_url"),
            "host": target.get("host"),
            "port": target.get("port"),
        },
        "checks": [
            {
                "security_test_id": row.get("security_test_id"),
                "runner": row.get("runner"),
                "enabled": bool(row.get("enabled", True)),
                "method": row.get("method"),
                "evidence_path": str(evidence_dir / _evidence_filename(row)),
            }
            for row in checks
        ],
        "output": str(output_path),
        "policy": config.get("policy") or {},
    }


def _disabled_result(check: dict[str, Any]) -> SecurityCheckResult:
    now = utc_now_iso()
    return SecurityCheckResult(
        security_test_id=str(check.get("security_test_id") or ""),
        status="NOT_EXECUTED",
        actual_result="Check disabled by explicit runner configuration.",
        started_at=now,
        completed_at=now,
        metadata={"runner": check.get("runner"), "disabled": True},
    )


def run_security_tests(
    case_dir: Path,
    config_path: Path,
    *,
    output_path: Path,
    selected_check: str | None = None,
    timeout: float | None = None,
    execution_id: str | None = None,
    synthetic: bool = False,
    no_network: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return dry_run_security_tests(
            case_dir,
            config_path,
            output_path=output_path,
            selected_check=selected_check,
            timeout=timeout,
            execution_id=execution_id,
            synthetic=synthetic,
            no_network=no_network,
        )

    case_dir = case_dir.resolve()
    config_path = config_path.resolve()
    output_path = output_path.resolve()
    config = load_runner_config(config_path)
    case_id = _case_id(case_dir)
    known_ids = _known_test_ids(case_dir)
    errors = validate_runner_config(
        config,
        case_id=case_id,
        known_security_test_ids=known_ids,
        selected_check=selected_check,
        resolve_dns=False,
    )
    if errors:
        raise SecurityRunnerConfigError("; ".join(errors))

    checks = [
        row
        for row in config.get("checks") or []
        if not selected_check
        or selected_check in {
            str(row.get("security_test_id") or ""),
            str(row.get("check_id") or ""),
        }
    ]
    if selected_check and not checks:
        raise SecurityRunnerConfigError(f"selected check not found: {selected_check}")

    is_synthetic = bool(synthetic or config.get("synthetic"))
    # Synthetic mode is fixture-only by design and never performs network I/O.
    effective_no_network = bool(no_network or is_synthetic)
    eid = execution_id or _default_execution_id(synthetic=is_synthetic)
    if not eid.startswith("exec-"):
        raise SecurityRunnerConfigError("execution_id must start with 'exec-'")

    policy = config.get("policy") or {}
    timeout_seconds = float(timeout or config.get("timeout_seconds") or 5.0)
    retry_count = max(0, min(int(config.get("retry_count") or 0), 1))
    max_body_bytes = max(0, min(int(config.get("max_body_bytes") or 65536), 1_048_576))
    max_redirects = max(0, min(int(config.get("max_redirects") or 3), 5))
    min_interval_ms = max(
        0, min(int(config.get("min_request_interval_ms") or 100), 10_000)
    )
    evidence_dir = output_path.parent / output_path.stem
    output_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    results: list[SecurityCheckResult] = []
    last_request_at = 0.0
    for check_config in checks:
        if not bool(check_config.get("enabled", True)):
            results.append(_disabled_result(check_config))
            continue
        check = create_check(
            str(check_config.get("runner") or ""),
            str(check_config.get("security_test_id") or ""),
        )
        check_errors = check.validate_config(check_config)
        if check_errors:
            raise SecurityRunnerConfigError(
                f"{check_config.get('security_test_id')}: " + "; ".join(check_errors)
            )

        attempts: list[dict[str, Any]] = []
        result: SecurityCheckResult | None = None
        for attempt_index in range(retry_count + 1):
            now = time.monotonic()
            wait_seconds = min_interval_ms / 1000 - (now - last_request_at)
            if wait_seconds > 0 and not effective_no_network:
                time.sleep(wait_seconds)
            context = RunnerContext(
                case_id=case_id,
                execution_id=eid,
                output_path=output_path,
                evidence_dir=evidence_dir,
                target=dict(config.get("target") or {}),
                policy=dict(policy),
                timeout=timeout_seconds,
                synthetic=is_synthetic,
                no_network=effective_no_network,
                max_body_bytes=max_body_bytes,
                max_redirects=max_redirects,
                retry_count=retry_count,
                min_request_interval_ms=min_interval_ms,
                check_config=dict(check_config),
                attempts=attempts,
            )
            result = check.run(context)
            last_request_at = time.monotonic()
            attempts.append(
                {
                    "attempt": attempt_index + 1,
                    "status": result.status,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                }
            )
            # Never retry explicit PASS/FAIL. Only transient REVIEW_REQUIRED.
            if result.status != "REVIEW_REQUIRED" or not result.metadata.get(
                "transient_error"
            ):
                break
        if result is None:
            raise RuntimeError("security check produced no result")
        result.metadata["attempts"] = attempts
        results.append(result)

    duration_ms = int((time.monotonic() - started) * 1000)
    metrics = {
        "configured_check_count": len(checks),
        "executed_check_count": sum(
            1 for result in results if result.status != "NOT_EXECUTED"
        ),
        "pass_count": sum(1 for result in results if result.status == "PASS"),
        "fail_count": sum(1 for result in results if result.status == "FAIL"),
        "review_required_count": sum(
            1 for result in results if result.status == "REVIEW_REQUIRED"
        ),
        "not_executed_count": sum(
            1 for result in results if result.status == "NOT_EXECUTED"
        ),
        "not_applicable_count": sum(
            1 for result in results if result.status == "NOT_APPLICABLE"
        ),
        "evidence_generated_count": sum(len(result.evidence) for result in results),
        "execution_duration_ms": duration_ms,
        "runner_error_count": sum(1 for result in results if result.error),
    }
    all_evidence = [record for result in results for record in result.evidence]
    write_manifest(
        evidence_dir,
        execution_id=eid,
        records=all_evidence,
        metrics=metrics,
    )

    target = config.get("target") or {}
    execution = {
        "case_id": case_id,
        "execution_id": eid,
        "executed_at": utc_now_iso(),
        "synthetic": is_synthetic,
        "executor": {
            "type": "script",
            "name": RUNNER_NAME,
            "version": RUNNER_VERSION,
        },
        "environment": {
            "target": str(config.get("environment") or ""),
            "base_url": str(target.get("base_url") or ""),
            "host": str(target.get("host") or ""),
            "notes": (
                "Synthetic fixture execution; no network requests performed."
                if effective_no_network
                else "Read-only network checks only."
            ),
        },
        "results": [result.to_execution_dict() for result in results],
        "runner_metrics": metrics,
        "runner_policy": {
            "read_only": True,
            "no_shell": True,
            "no_subprocess": True,
            "no_network": effective_no_network,
            "allow_private_network": bool(policy.get("allow_private_network")),
            "max_redirects": max_redirects,
            "max_body_bytes": max_body_bytes,
            "retry_count": retry_count,
        },
    }
    schema_errors = validate_execution_payload(execution)
    if schema_errors:
        raise SecurityExecutionImportError(
            "runner output is not execution-schema compatible: "
            + "; ".join(schema_errors)
        )
    output_path.write_text(
        json.dumps(execution, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "case_id": case_id,
        "execution_id": eid,
        "synthetic": is_synthetic,
        "no_network": effective_no_network,
        "output": str(output_path),
        "evidence_dir": str(evidence_dir),
        "metrics": metrics,
        "results": [result.to_execution_dict() for result in results],
        "auto_imported": False,
    }
