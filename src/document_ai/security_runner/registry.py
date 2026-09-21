"""Registry for built-in read-only security checks."""

from __future__ import annotations

from typing import Any

from document_ai.security_runner.models import SecurityCheck
from document_ai.security_runner.runners.api_health_check import APIHealthCheck
from document_ai.security_runner.runners.http_header_check import HTTPHeaderCheck
from document_ai.security_runner.runners.port_connectivity_check import PortConnectivityCheck
from document_ai.security_runner.runners.tls_check import TLSCheck

CHECK_TYPES: dict[str, type[Any]] = {
    "tls_check": TLSCheck,
    "http_header_check": HTTPHeaderCheck,
    "api_health_check": APIHealthCheck,
    "port_connectivity_check": PortConnectivityCheck,
}


def create_check(runner_name: str, security_test_id: str) -> SecurityCheck:
    check_type = CHECK_TYPES.get(runner_name)
    if check_type is None:
        raise ValueError(f"unknown runner: {runner_name}")
    return check_type(security_test_id)


def registered_runners() -> list[str]:
    return sorted(CHECK_TYPES)
