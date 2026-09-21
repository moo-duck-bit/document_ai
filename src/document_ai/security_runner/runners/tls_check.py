"""Read-only TLS negotiation and certificate policy check."""

from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any

from document_ai.security_runner.evidence import write_evidence_json
from document_ai.security_runner.models import RunnerContext, SecurityCheckResult, utc_now_iso
from document_ai.security_runner.policy import validate_host_port

TLS_ORDER = {
    "SSLv3": 0,
    "TLSv1": 1,
    "TLSv1.0": 1,
    "TLSv1.1": 2,
    "TLSv1.2": 3,
    "TLSv1.3": 4,
}


def _parse_cert_expiry(value: str) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        timestamp = ssl.cert_time_to_seconds(value)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, OverflowError):
        return None


class TLSCheck:
    check_id = "tls_check"

    def __init__(self, security_test_id: str) -> None:
        self.security_test_id = security_test_id

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        expected = config.get("expected") or {}
        minimum = str(expected.get("minimum_tls_version") or "")
        if minimum and minimum not in TLS_ORDER:
            return [f"unsupported minimum_tls_version: {minimum}"]
        return []

    def run(self, context: RunnerContext) -> SecurityCheckResult:
        started_at = utc_now_iso()
        started = time.monotonic()
        config = context.check_config
        host = str(config.get("host") or context.target.get("host") or "")
        port = int(config.get("port") or context.target.get("port") or 443)
        expected = config.get("expected") or {}
        ssl_verify = bool(config.get("ssl_verify", True))
        warning = "" if ssl_verify else "SSL verification explicitly disabled; "
        observation: dict[str, Any]
        try:
            if context.no_network:
                fixture = config.get("fixture") or {}
                error = str(fixture.get("error") or "")
                if error:
                    raise TimeoutError(error)
                observation = {
                    "host": host,
                    "port": port,
                    "connected": bool(fixture.get("connected", True)),
                    "negotiated_tls_version": fixture.get(
                        "negotiated_tls_version", "TLSv1.3"
                    ),
                    "certificate_not_after": fixture.get(
                        "certificate_not_after", "2030-01-01T00:00:00Z"
                    ),
                    "hostname_matches": bool(fixture.get("hostname_matches", True)),
                    "certificate_subject": fixture.get("certificate_subject", "CN=fixture"),
                    "certificate_issuer": fixture.get("certificate_issuer", "CN=fixture-ca"),
                    "transport": "mock",
                }
            else:
                validate_host_port(
                    host,
                    port,
                    allowed_hosts=list(context.policy.get("allowed_hosts") or []),
                    allowed_ports=list(context.policy.get("allowed_ports") or []),
                    allow_private_network=bool(
                        context.policy.get("allow_private_network")
                    ),
                    resolve_dns=True,
                )
                ssl_context = ssl.create_default_context()
                if not ssl_verify:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                with socket.create_connection((host, port), timeout=context.timeout) as raw:
                    with ssl_context.wrap_socket(
                        raw,
                        server_hostname=host if ssl_verify else None,
                    ) as wrapped:
                        cert = wrapped.getpeercert() or {}
                        observation = {
                            "host": host,
                            "port": port,
                            "connected": True,
                            "negotiated_tls_version": wrapped.version(),
                            "certificate_not_after": cert.get("notAfter", ""),
                            "hostname_matches": ssl_verify,
                            "certificate_subject": cert.get("subject", []),
                            "certificate_issuer": cert.get("issuer", []),
                            "transport": "network",
                        }

            negotiated = str(observation.get("negotiated_tls_version") or "")
            minimum = str(expected.get("minimum_tls_version") or "TLSv1.2")
            expiry = _parse_cert_expiry(str(observation.get("certificate_not_after") or ""))
            days_remaining = (
                int((expiry - datetime.now(timezone.utc)).total_seconds() // 86400)
                if expiry
                else None
            )
            observation["certificate_days_remaining"] = days_remaining
            minimum_days = int(expected.get("minimum_certificate_days_remaining") or 0)
            failures: list[str] = []
            uncertain: list[str] = []
            if not observation.get("connected"):
                uncertain.append("TLS connection was not established")
            if negotiated not in TLS_ORDER:
                uncertain.append("negotiated TLS version unavailable")
            elif TLS_ORDER[negotiated] < TLS_ORDER.get(minimum, 99):
                failures.append(f"{negotiated} is below required {minimum}")
            if not observation.get("hostname_matches"):
                failures.append("certificate hostname does not match")
            if expiry is None:
                uncertain.append("certificate expiry unavailable")
            elif days_remaining is not None and days_remaining < minimum_days:
                failures.append(
                    f"certificate expires in {days_remaining} days; required >= {minimum_days}"
                )

            status = "FAIL" if failures else ("REVIEW_REQUIRED" if uncertain else "PASS")
            actual = warning + "; ".join(failures or uncertain) if failures or uncertain else (
                f"TLS connection succeeded with {negotiated}; certificate valid for "
                f"{days_remaining} days"
            )
            evidence = write_evidence_json(
                context.evidence_dir,
                f"{self.security_test_id}_tls.json",
                {
                    "check": self.check_id,
                    "expected": expected,
                    "observation": observation,
                    "failures": failures,
                    "uncertain": uncertain,
                    "ssl_verification_enabled": ssl_verify,
                },
                output_parent=context.output_path.parent,
                description="TLS negotiation and certificate metadata",
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
                    "transient_error": False,
                    "ssl_verification_enabled": ssl_verify,
                },
            )
        except (TimeoutError, socket.timeout, socket.gaierror, OSError, ssl.SSLError) as exc:
            evidence = write_evidence_json(
                context.evidence_dir,
                f"{self.security_test_id}_tls.json",
                {
                    "check": self.check_id,
                    "host": host,
                    "port": port,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                output_parent=context.output_path.parent,
                description="TLS check error metadata",
            )
            return SecurityCheckResult(
                security_test_id=self.security_test_id,
                status="REVIEW_REQUIRED",
                actual_result=f"TLS result uncertain: {type(exc).__name__}: {exc}",
                evidence=[evidence],
                started_at=started_at,
                completed_at=utc_now_iso(),
                duration_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
                metadata={"runner": self.check_id, "transient_error": True},
            )
