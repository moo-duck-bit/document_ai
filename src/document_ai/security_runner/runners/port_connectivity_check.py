"""Single-port TCP connectivity check without banner grabbing."""

from __future__ import annotations

import socket
import time
from typing import Any

from document_ai.security_runner.evidence import write_evidence_json
from document_ai.security_runner.models import RunnerContext, SecurityCheckResult, utc_now_iso
from document_ai.security_runner.policy import validate_host_port


class PortConnectivityCheck:
    check_id = "port_connectivity_check"

    def __init__(self, security_test_id: str) -> None:
        self.security_test_id = security_test_id

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        if isinstance(config.get("ports"), list) and len(config["ports"]) != 1:
            return ["port range/list scan is forbidden"]
        return []

    def run(self, context: RunnerContext) -> SecurityCheckResult:
        started_at = utc_now_iso()
        started = time.monotonic()
        config = context.check_config
        host = str(config.get("host") or context.target.get("host") or "")
        port = int(config.get("port") or context.target.get("port") or 0)
        try:
            if context.no_network:
                fixture = config.get("fixture") or {}
                if fixture.get("error"):
                    raise TimeoutError(str(fixture["error"]))
                connected = bool(fixture.get("connected", True))
                elapsed_ms = int(fixture.get("elapsed_ms") or 1)
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
                with socket.create_connection((host, port), timeout=context.timeout):
                    # No send()/recv(): banner grabbing is prohibited.
                    connected = True
                elapsed_ms = int((time.monotonic() - started) * 1000)
            status = "PASS" if connected else "REVIEW_REQUIRED"
            actual = (
                f"TCP connection to allowlisted {host}:{port} succeeded; no data sent or read"
                if connected
                else f"TCP connection state for {host}:{port} is uncertain"
            )
            evidence = write_evidence_json(
                context.evidence_dir,
                f"{self.security_test_id}_port.json",
                {
                    "check": self.check_id,
                    "host": host,
                    "port": port,
                    "connected": connected,
                    "elapsed_ms": elapsed_ms,
                    "banner_grabbed": False,
                    "bytes_sent": 0,
                    "bytes_received": 0,
                },
                output_parent=context.output_path.parent,
                description="Single-port TCP connectivity metadata",
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
                    "transient_error": not connected,
                    "banner_grabbed": False,
                },
            )
        except (TimeoutError, socket.timeout, socket.gaierror, OSError) as exc:
            evidence = write_evidence_json(
                context.evidence_dir,
                f"{self.security_test_id}_port.json",
                {
                    "check": self.check_id,
                    "host": host,
                    "port": port,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "banner_grabbed": False,
                    "bytes_sent": 0,
                    "bytes_received": 0,
                },
                output_parent=context.output_path.parent,
                description="Port connectivity error metadata",
            )
            return SecurityCheckResult(
                security_test_id=self.security_test_id,
                status="REVIEW_REQUIRED",
                actual_result=f"TCP connectivity uncertain: {type(exc).__name__}: {exc}",
                evidence=[evidence],
                started_at=started_at,
                completed_at=utc_now_iso(),
                duration_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
                metadata={"runner": self.check_id, "transient_error": True},
            )
