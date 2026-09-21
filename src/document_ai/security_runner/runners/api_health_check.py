"""Read-only API health check using GET or HEAD."""

from __future__ import annotations

import json
import time
import urllib.error
from typing import Any

from document_ai.security_runner.evidence import body_summary, mask_sensitive_headers, write_evidence_json
from document_ai.security_runner.models import RunnerContext, SecurityCheckResult, utc_now_iso
from document_ai.security_runner.policy import SecurityRunnerConfigError, normalize_url
from document_ai.security_runner.runners._http import HttpObservation, request_read_only


def _has_json_key(payload: Any, dotted_key: str) -> bool:
    current = payload
    for token in dotted_key.split("."):
        if not isinstance(current, dict) or token not in current:
            return False
        current = current[token]
    return True


class APIHealthCheck:
    check_id = "api_health_check"

    def __init__(self, security_test_id: str) -> None:
        self.security_test_id = security_test_id

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        method = str(config.get("method") or "GET").upper()
        return [] if method in {"GET", "HEAD"} else [f"HTTP method blocked: {method}"]

    def _observe(self, context: RunnerContext) -> HttpObservation:
        config = context.check_config
        url = normalize_url(
            str(config.get("base_url") or context.target.get("base_url") or ""),
            str(config.get("endpoint") or ""),
        )
        if context.no_network:
            fixture = config.get("fixture") or {}
            if fixture.get("error"):
                raise TimeoutError(str(fixture["error"]))
            raw_body = fixture.get("body", "")
            if isinstance(raw_body, (dict, list)):
                raw_body = json.dumps(raw_body)
            body = str(raw_body).encode("utf-8")
            redirect_chain = list(fixture.get("redirect_chain") or [])
            if len(redirect_chain) > context.max_redirects:
                raise SecurityRunnerConfigError(
                    f"redirect limit exceeded ({context.max_redirects})"
                )
            return HttpObservation(
                url=url,
                status=int(fixture.get("status") or 200),
                headers=mask_sensitive_headers(dict(fixture.get("headers") or {})),
                body=body[: context.max_body_bytes],
                body_truncated=len(body) > context.max_body_bytes,
                redirect_chain=redirect_chain,
                elapsed_ms=int(fixture.get("elapsed_ms") or 1),
            )
        return request_read_only(
            url,
            method=str(config.get("method") or "GET"),
            timeout=context.timeout,
            max_body_bytes=context.max_body_bytes,
            max_redirects=context.max_redirects,
            policy=context.policy,
            ssl_verify=bool(config.get("ssl_verify", True)),
        )

    def run(self, context: RunnerContext) -> SecurityCheckResult:
        started_at = utc_now_iso()
        started = time.monotonic()
        config = context.check_config
        expected = config.get("expected") or {}
        try:
            observation = self._observe(context)
            headers = {key.lower(): value for key, value in observation.headers.items()}
            failures: list[str] = []
            uncertain: list[str] = []
            expected_statuses = {
                int(value)
                for value in expected.get(
                    "status_codes",
                    [expected.get("status_code", 200)],
                )
            }
            if observation.status not in expected_statuses:
                failures.append(
                    f"HTTP status {observation.status} not in {sorted(expected_statuses)}"
                )
            max_response_ms = expected.get("maximum_response_time_ms")
            if max_response_ms is not None and observation.elapsed_ms > int(max_response_ms):
                failures.append(
                    f"response time {observation.elapsed_ms}ms exceeds {int(max_response_ms)}ms"
                )
            content_type = headers.get("content-type", "")
            expected_content_type = str(expected.get("content_type") or "")
            if expected_content_type and expected_content_type.lower() not in content_type.lower():
                failures.append(
                    f"content-type {content_type!r} does not include {expected_content_type!r}"
                )
            required_keys = [str(item) for item in expected.get("json_keys") or []]
            if required_keys:
                try:
                    decoded = json.loads(observation.body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    uncertain.append("response is not parseable JSON for required key checks")
                else:
                    missing = [key for key in required_keys if not _has_json_key(decoded, key)]
                    if missing:
                        failures.append("missing JSON keys: " + ", ".join(missing))

            if observation.body_truncated and required_keys:
                uncertain.append(
                    "response body exceeded configured limit; JSON key result may be incomplete"
                )
            status = "FAIL" if failures else ("REVIEW_REQUIRED" if uncertain else "PASS")
            actual = "; ".join(failures or uncertain) if failures or uncertain else (
                f"API health endpoint returned HTTP {observation.status} in "
                f"{observation.elapsed_ms}ms"
            )
            evidence = write_evidence_json(
                context.evidence_dir,
                f"{self.security_test_id}_api_health.json",
                {
                    "check": self.check_id,
                    "url": observation.url,
                    "method": str(config.get("method") or "GET").upper(),
                    "status": observation.status,
                    "headers": observation.headers,
                    "redirect_chain": observation.redirect_chain,
                    "response": body_summary(
                        observation.body,
                        content_type=content_type,
                        truncated=observation.body_truncated,
                    ),
                    "expected": expected,
                    "failures": failures,
                    "uncertain": uncertain,
                    "elapsed_ms": observation.elapsed_ms,
                },
                output_parent=context.output_path.parent,
                description="Sanitized API health metadata and body hash",
            )
            return SecurityCheckResult(
                security_test_id=self.security_test_id,
                status=status,
                actual_result=actual,
                evidence=[evidence],
                started_at=started_at,
                completed_at=utc_now_iso(),
                duration_ms=int((time.monotonic() - started) * 1000),
                metadata={
                    "runner": self.check_id,
                    "body_truncated": observation.body_truncated,
                    "body_bytes_observed": len(observation.body),
                    "transient_error": False,
                },
            )
        except (
            TimeoutError,
            urllib.error.URLError,
            OSError,
            SecurityRunnerConfigError,
        ) as exc:
            evidence = write_evidence_json(
                context.evidence_dir,
                f"{self.security_test_id}_api_health.json",
                {
                    "check": self.check_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                output_parent=context.output_path.parent,
                description="API health check error metadata",
            )
            return SecurityCheckResult(
                security_test_id=self.security_test_id,
                status="REVIEW_REQUIRED",
                actual_result=f"API health result uncertain: {type(exc).__name__}: {exc}",
                evidence=[evidence],
                started_at=started_at,
                completed_at=utc_now_iso(),
                duration_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
                metadata={"runner": self.check_id, "transient_error": True},
            )
