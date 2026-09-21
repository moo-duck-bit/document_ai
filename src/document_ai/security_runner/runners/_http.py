"""Bounded, allowlisted HTTP transport for read-only checks."""

from __future__ import annotations

import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from document_ai.security_runner.evidence import mask_sensitive_headers
from document_ai.security_runner.policy import (
    ALLOWED_HTTP_METHODS,
    SecurityRunnerConfigError,
    validate_redirect_target,
    validate_url_target,
)


@dataclass(slots=True)
class HttpObservation:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    body_truncated: bool
    redirect_chain: list[dict[str, Any]]
    elapsed_ms: int


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def request_read_only(
    url: str,
    *,
    method: str,
    timeout: float,
    max_body_bytes: int,
    max_redirects: int,
    policy: dict[str, Any],
    ssl_verify: bool,
) -> HttpObservation:
    method = method.upper()
    if method not in ALLOWED_HTTP_METHODS:
        raise SecurityRunnerConfigError(f"HTTP method blocked: {method}")

    current = url
    redirect_chain: list[dict[str, Any]] = []
    started = time.monotonic()
    ssl_context = ssl.create_default_context()
    if not ssl_verify:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(
        _NoRedirectHandler(),
        urllib.request.HTTPSHandler(context=ssl_context),
    )

    for redirect_index in range(max_redirects + 1):
        validate_url_target(
            current,
            allowed_urls=list(policy.get("allowed_urls") or []),
            allowed_hosts=list(policy.get("allowed_hosts") or []),
            allow_private_network=bool(policy.get("allow_private_network")),
            resolve_dns=True,
        )
        request = urllib.request.Request(
            current,
            method=method,
            headers={
                "User-Agent": "document-ai-security-runner/0.1",
                "Accept": "application/json,text/plain,*/*;q=0.1",
            },
        )
        try:
            response = opener.open(request, timeout=timeout)
            status = int(response.status)
            headers = dict(response.headers.items())
            body = b"" if method == "HEAD" else response.read(max_body_bytes + 1)
            truncated = len(body) > max_body_bytes
            if truncated:
                body = body[:max_body_bytes]
            return HttpObservation(
                url=current,
                status=status,
                headers=mask_sensitive_headers(headers),
                body=body,
                body_truncated=truncated,
                redirect_chain=redirect_chain,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            headers = dict(exc.headers.items()) if exc.headers else {}
            location = headers.get("Location") or headers.get("location")
            if 300 <= status < 400 and location:
                if redirect_index >= max_redirects:
                    raise SecurityRunnerConfigError(
                        f"redirect limit exceeded ({max_redirects})"
                    ) from exc
                destination = urljoin(current, location)
                validate_redirect_target(
                    current,
                    destination,
                    policy=policy,
                    resolve_dns=True,
                )
                redirect_chain.append(
                    {
                        "from": current,
                        "to": destination,
                        "status": status,
                    }
                )
                current = destination
                continue
            body = b"" if method == "HEAD" else exc.read(max_body_bytes + 1)
            truncated = len(body) > max_body_bytes
            if truncated:
                body = body[:max_body_bytes]
            return HttpObservation(
                url=current,
                status=status,
                headers=mask_sensitive_headers(headers),
                body=body,
                body_truncated=truncated,
                redirect_chain=redirect_chain,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
    raise SecurityRunnerConfigError(f"redirect limit exceeded ({max_redirects})")
