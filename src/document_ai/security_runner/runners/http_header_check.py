"""Read-only HTTP security header check."""

from __future__ import annotations

import time
import urllib.error
from typing import Any

from document_ai.security_runner.evidence import body_summary, mask_sensitive_headers, write_evidence_json
from document_ai.security_runner.models import RunnerContext, SecurityCheckResult, utc_now_iso
from document_ai.security_runner.policy import SecurityRunnerConfigError, normalize_url
from document_ai.security_runner.runners._http import HttpObservation, request_read_only

DEFAULT_HEADERS = {
    "strict-transport-security": {"required": True},
    "content-security-policy": {"required": True},
    "x-content-type-options": {"required": True, "contains": "nosniff"},
    "referrer-policy": {"required": False},
}


class HTTPHeaderCheck:
    check_id = "http_header_check"

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
            body = str(fixture.get("body") or "").encode("utf-8")
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
        requirements = dict(DEFAULT_HEADERS)
        requirements.update(expected.get("headers") or {})
        try:
            observation = self._observe(context)
            headers = {key.lower(): value for key, value in observation.headers.items()}
            failures: list[str] = []
            findings: list[str] = []
            for name, rule_value in requirements.items():
                rule = rule_value if isinstance(rule_value, dict) else {"required": bool(rule_value)}
                required = bool(rule.get("required"))
                value = headers.get(name.lower(), "")
                if not value:
                    if required:
                        failures.append(f"missing required header: {name}")
                    else:
                        findings.append(f"optional header missing: {name}")
                    continue
                contains = str(rule.get("contains") or "")
                if contains and contains.lower() not in value.lower():
                    if required:
                        failures.append(f"{name} does not contain {contains!r}")
                    else:
                        findings.append(f"optional {name} does not contain {contains!r}")

            x_frame = headers.get("x-frame-options", "")
            csp = headers.get("content-security-policy", "")
            frame_required = bool(expected.get("frame_protection_required", True))
            if not x_frame and "frame-ancestors" not in csp.lower():
                message = "missing X-Frame-Options or CSP frame-ancestors"
                (failures if frame_required else findings).append(message)

            expected_statuses = {
                int(value) for value in expected.get("status_codes", [200, 204, 301, 302])
            }
            if observation.status not in expected_statuses:
                failures.append(
                    f"HTTP status {observation.status} not in {sorted(expected_statuses)}"
                )
            status = "FAIL" if failures else "PASS"
            actual = "; ".join(failures) if failures else (
                f"HTTP {observation.status}; required security headers satisfied"
            )
            if findings:
                actual += "; " + "; ".join(findings)
            content_type = headers.get("content-type", "")
            evidence = write_evidence_json(
                context.evidence_dir,
                f"{self.security_test_id}_headers.json",
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
                    "findings": findings,
                    "elapsed_ms": observation.elapsed_ms,
                },
                output_parent=context.output_path.parent,
                description="Sanitized HTTP security header metadata",
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
                    "redirect_count": len(observation.redirect_chain),
                    "body_truncated": observation.body_truncated,
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
                f"{self.security_test_id}_headers.json",
                {
                    "check": self.check_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                output_parent=context.output_path.parent,
                description="HTTP header check error metadata",
            )
            return SecurityCheckResult(
                security_test_id=self.security_test_id,
                status="REVIEW_REQUIRED",
                actual_result=f"HTTP header result uncertain: {type(exc).__name__}: {exc}",
                evidence=[evidence],
                started_at=started_at,
                completed_at=utc_now_iso(),
                duration_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
                metadata={"runner": self.check_id, "transient_error": True},
            )
