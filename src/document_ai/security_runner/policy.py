"""Configuration validation and network safety policy."""

from __future__ import annotations

import ipaddress
import json
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

ALLOWED_HTTP_METHODS = frozenset({"GET", "HEAD"})
KNOWN_RUNNERS = frozenset(
    {"tls_check", "http_header_check", "api_health_check", "port_connectivity_check"}
)
SENSITIVE_CONFIG_TOKENS = (
    "password",
    "passwd",
    "token",
    "secret",
    "private_key",
    "authorization",
    "api_key",
)


class SecurityRunnerConfigError(ValueError):
    """Raised when runner configuration violates schema or safety policy."""


def load_runner_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains_secret_key(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            lowered = str(key).lower()
            if any(token in lowered for token in SENSITIVE_CONFIG_TOKENS):
                found.append(dotted)
            found.extend(_contains_secret_key(item, dotted))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found.extend(_contains_secret_key(item, f"{prefix}[{idx}]"))
    return found


def normalize_url(base_url: str, endpoint: str = "") -> str:
    base = str(base_url or "").strip()
    if not base:
        return ""
    if endpoint:
        return urljoin(base.rstrip("/") + "/", str(endpoint).lstrip("/"))
    return base


def _parse_host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SecurityRunnerConfigError(f"URL scheme must be http or https: {url!r}")
    if parsed.username or parsed.password:
        raise SecurityRunnerConfigError("credentials in URL are forbidden")
    if not parsed.hostname:
        raise SecurityRunnerConfigError(f"URL hostname is required: {url!r}")
    if parsed.fragment:
        raise SecurityRunnerConfigError("URL fragments are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname, port


def is_private_or_local_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return value.lower().rstrip(".") in {"localhost", "localhost.localdomain"}
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def validate_resolved_addresses(host: str, *, allow_private_network: bool) -> list[str]:
    """Resolve a configured host at execution time and enforce private-network policy."""
    if is_private_or_local_address(host) and not allow_private_network:
        raise SecurityRunnerConfigError(f"private/local target blocked: {host}")
    try:
        addresses = sorted(
            {
                item[4][0]
                for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
                if item[4]
            }
        )
    except socket.gaierror as exc:
        raise SecurityRunnerConfigError(f"target DNS resolution failed: {host}: {exc}") from exc
    if not addresses:
        raise SecurityRunnerConfigError(f"target resolved to no addresses: {host}")
    if not allow_private_network:
        blocked = [address for address in addresses if is_private_or_local_address(address)]
        if blocked:
            raise SecurityRunnerConfigError(
                f"target resolves to private/local address: {host} -> {', '.join(blocked)}"
            )
    return addresses


def validate_url_target(
    url: str,
    *,
    allowed_urls: list[str],
    allowed_hosts: list[str],
    allow_private_network: bool,
    resolve_dns: bool,
) -> tuple[str, int]:
    host, port = _parse_host_port(url)
    normalized = url.rstrip("/")
    normalized_allowlist = {str(item).rstrip("/") for item in allowed_urls}
    hosts = {str(item).lower().rstrip(".") for item in allowed_hosts}
    if normalized not in normalized_allowlist and host.lower().rstrip(".") not in hosts:
        raise SecurityRunnerConfigError(f"URL/host is not allowlisted: {url}")
    if is_private_or_local_address(host) and not allow_private_network:
        raise SecurityRunnerConfigError(f"private/local target blocked: {host}")
    if resolve_dns:
        validate_resolved_addresses(host, allow_private_network=allow_private_network)
    return host, port


def validate_host_port(
    host: str,
    port: int,
    *,
    allowed_hosts: list[str],
    allowed_ports: list[int],
    allow_private_network: bool,
    resolve_dns: bool,
) -> None:
    normalized_host = str(host).lower().rstrip(".")
    if normalized_host not in {str(item).lower().rstrip(".") for item in allowed_hosts}:
        raise SecurityRunnerConfigError(f"host is not allowlisted: {host}")
    if int(port) not in {int(item) for item in allowed_ports}:
        raise SecurityRunnerConfigError(f"port is not allowlisted: {port}")
    if not 1 <= int(port) <= 65535:
        raise SecurityRunnerConfigError(f"invalid port: {port}")
    if is_private_or_local_address(host) and not allow_private_network:
        raise SecurityRunnerConfigError(f"private/local target blocked: {host}")
    if resolve_dns:
        validate_resolved_addresses(host, allow_private_network=allow_private_network)


def validate_redirect_target(
    from_url: str,
    to_url: str,
    *,
    policy: dict[str, Any],
    resolve_dns: bool = True,
) -> None:
    if not to_url:
        raise SecurityRunnerConfigError("empty redirect target")
    validate_url_target(
        to_url,
        allowed_urls=list(policy.get("allowed_urls") or []),
        allowed_hosts=list(policy.get("allowed_hosts") or []),
        allow_private_network=bool(policy.get("allow_private_network")),
        resolve_dns=resolve_dns,
    )
    source = urlparse(from_url)
    target = urlparse(to_url)
    if source.scheme == "https" and target.scheme == "http" and not policy.get(
        "allow_https_downgrade"
    ):
        raise SecurityRunnerConfigError("HTTPS-to-HTTP redirect is blocked")


def validate_runner_config(
    config: dict[str, Any],
    *,
    case_id: str,
    known_security_test_ids: set[str],
    selected_check: str | None = None,
    resolve_dns: bool = False,
) -> list[str]:
    errors: list[str] = []
    if config.get("case_id") != case_id:
        errors.append(
            f"case_id mismatch: config={config.get('case_id')!r} case={case_id!r}"
        )
    if not isinstance(config.get("target"), dict):
        errors.append("target must be an object")
    checks = config.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty array")
        return errors

    secret_keys = _contains_secret_key(config)
    if secret_keys:
        errors.append("secret-like config keys are forbidden: " + ", ".join(secret_keys))

    policy = config.get("policy") or {}
    allowed_hosts = list(policy.get("allowed_hosts") or [])
    allowed_urls = list(policy.get("allowed_urls") or [])
    allowed_ports = list(policy.get("allowed_ports") or [])
    if not allowed_hosts:
        errors.append("policy.allowed_hosts must be non-empty")

    seen: set[str] = set()
    for idx, check in enumerate(checks):
        if not isinstance(check, dict):
            errors.append(f"checks[{idx}] must be an object")
            continue
        sid = str(check.get("security_test_id") or "").strip()
        runner = str(check.get("runner") or "").strip()
        if not sid:
            errors.append(f"checks[{idx}].security_test_id is required")
        if sid in seen:
            errors.append(f"duplicate security_test_id: {sid}")
        seen.add(sid)
        if runner not in KNOWN_RUNNERS:
            errors.append(f"unknown runner: {runner!r}")
        if selected_check and selected_check not in {sid, str(check.get("check_id") or "")}:
            continue
        if sid and sid not in known_security_test_ids:
            errors.append(f"unknown security_test_id: {sid}")
        method = str(check.get("method") or "GET").upper()
        if runner in {"http_header_check", "api_health_check"} and method not in ALLOWED_HTTP_METHODS:
            errors.append(f"{sid}: HTTP method blocked: {method}")
        if runner == "port_connectivity_check" and isinstance(check.get("ports"), list):
            if len(check["ports"]) != 1:
                errors.append(f"{sid}: port range/list scan is forbidden")

        target = config.get("target") or {}
        host = str(check.get("host") or target.get("host") or "")
        port = int(check.get("port") or target.get("port") or 0)
        base_url = str(check.get("base_url") or target.get("base_url") or "")
        endpoint = str(check.get("endpoint") or "")
        try:
            if runner in {"http_header_check", "api_health_check"}:
                url = normalize_url(base_url, endpoint)
                validate_url_target(
                    url,
                    allowed_urls=allowed_urls,
                    allowed_hosts=allowed_hosts,
                    allow_private_network=bool(policy.get("allow_private_network")),
                    resolve_dns=resolve_dns,
                )
            elif runner in {"tls_check", "port_connectivity_check"}:
                validate_host_port(
                    host,
                    port,
                    allowed_hosts=allowed_hosts,
                    allowed_ports=allowed_ports,
                    allow_private_network=bool(policy.get("allow_private_network")),
                    resolve_dns=resolve_dns,
                )
        except (SecurityRunnerConfigError, TypeError, ValueError) as exc:
            errors.append(f"{sid or idx}: {exc}")
    return errors
