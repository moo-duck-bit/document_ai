"""Read-only automated security runner tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.form_fill.security_execution import (
    import_security_results,
    validate_execution_payload,
)
from document_ai.form_fill.security_tests import ensure_security_tests_payload
from document_ai.security_runner.evidence import mask_sensitive_headers
from document_ai.security_runner.executor import dry_run_security_tests, run_security_tests
from document_ai.security_runner.policy import (
    SecurityRunnerConfigError,
    validate_runner_config,
)


def _case(tmp_path: Path, name: str = "runner_case") -> Path:
    case_dir = tmp_path / name
    case_dir.mkdir()
    intake = {
        "case_id": name,
        "product_name": "Runner Test",
        "domain": "test",
        "facts": {"product_name": "Runner Test"},
    }
    (case_dir / "input.json").write_text(json.dumps(intake), encoding="utf-8")
    (case_dir / "requirements.json").write_text(
        json.dumps(
            {
                "traceability": [
                    {"requirement": "SI-01", "linked_reqs": "Req. 1"},
                    {"requirement": "SI-02", "linked_reqs": "Req. 2"},
                    {"requirement": "SI-03", "linked_reqs": "Req. 3"},
                    {"requirement": "SI-04", "linked_reqs": "Req. 4"},
                ]
            }
        ),
        encoding="utf-8",
    )
    ensure_security_tests_payload(case_dir, intake=intake)
    return case_dir


def _config(
    case_id: str,
    *,
    sid: str = "SI-01",
    runner: str = "tls_check",
    fixture: dict | None = None,
    expected: dict | None = None,
    method: str | None = None,
) -> dict:
    check = {
        "security_test_id": sid,
        "runner": runner,
        "enabled": True,
        "expected": expected or {},
        "fixture": fixture or {},
    }
    if method:
        check["method"] = method
    return {
        "case_id": case_id,
        "environment": "fixture",
        "synthetic": True,
        "target": {
            "base_url": "https://fixture.example.com",
            "host": "fixture.example.com",
            "port": 443,
        },
        "policy": {
            "allowed_hosts": ["fixture.example.com"],
            "allowed_urls": ["https://fixture.example.com"],
            "allowed_ports": [443],
            "allow_private_network": False,
        },
        "timeout_seconds": 1,
        "retry_count": 0,
        "max_redirects": 2,
        "max_body_bytes": 128,
        "checks": [check],
    }


def _write_config(tmp_path: Path, config: dict, name: str = "config.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _run(
    tmp_path: Path,
    config: dict,
    *,
    case_dir: Path | None = None,
    output_name: str = "execution.json",
) -> tuple[dict, dict, Path]:
    case_dir = case_dir or _case(tmp_path)
    config_path = _write_config(tmp_path, config)
    output = tmp_path / output_name
    summary = run_security_tests(
        case_dir,
        config_path,
        output_path=output,
        synthetic=True,
        no_network=True,
        execution_id="exec-test-runner-001",
    )
    return summary, json.loads(output.read_text(encoding="utf-8")), output


def test_runner_config_schema_exists_and_is_json():
    schema = json.loads(
        Path("schemas/security_runner_config.schema.json").read_text(encoding="utf-8")
    )
    assert schema["title"] == "ReadOnlySecurityRunnerConfig"
    assert "checks" in schema["properties"]


def test_unknown_runner_rejected(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(case_dir.name, runner="shell_command")
    errors = validate_runner_config(
        config,
        case_id=case_dir.name,
        known_security_test_ids={"SI-01"},
    )
    assert any("unknown runner" in error for error in errors)


def test_unknown_security_test_id_rejected(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(case_dir.name, sid="ZZ-99")
    errors = validate_runner_config(
        config,
        case_id=case_dir.name,
        known_security_test_ids={"SI-01"},
    )
    assert any("unknown security_test_id" in error for error in errors)


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_non_read_only_http_methods_blocked(tmp_path: Path, method: str):
    case_dir = _case(tmp_path)
    config = _config(
        case_dir.name,
        runner="api_health_check",
        method=method,
    )
    errors = validate_runner_config(
        config,
        case_id=case_dir.name,
        known_security_test_ids={"SI-01"},
    )
    assert any("method blocked" in error for error in errors)


def test_tls_version_pass_and_fail(tmp_path: Path):
    case_dir = _case(tmp_path)
    passed = _config(
        case_dir.name,
        fixture={
            "negotiated_tls_version": "TLSv1.3",
            "certificate_not_after": "2030-01-01T00:00:00Z",
            "hostname_matches": True,
        },
        expected={"minimum_tls_version": "TLSv1.2"},
    )
    _, payload, _ = _run(tmp_path, passed, case_dir=case_dir, output_name="pass.json")
    assert payload["results"][0]["status"] == "PASS"

    failed = _config(
        case_dir.name,
        fixture={
            "negotiated_tls_version": "TLSv1.0",
            "certificate_not_after": "2030-01-01T00:00:00Z",
            "hostname_matches": True,
        },
        expected={"minimum_tls_version": "TLSv1.2"},
    )
    _, payload, _ = _run(tmp_path, failed, case_dir=case_dir, output_name="fail.json")
    assert payload["results"][0]["status"] == "FAIL"


def test_certificate_expiry_policy_fails(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(
        case_dir.name,
        fixture={
            "negotiated_tls_version": "TLSv1.3",
            "certificate_not_after": "2020-01-01T00:00:00Z",
            "hostname_matches": True,
        },
        expected={
            "minimum_tls_version": "TLSv1.2",
            "minimum_certificate_days_remaining": 30,
        },
    )
    _, payload, _ = _run(tmp_path, config, case_dir=case_dir)
    assert payload["results"][0]["status"] == "FAIL"
    assert "expires" in payload["results"][0]["actual_result"]


def test_missing_required_header_fails_optional_missing_does_not(tmp_path: Path):
    case_dir = _case(tmp_path)
    missing_required = _config(
        case_dir.name,
        runner="http_header_check",
        method="HEAD",
        expected={
            "headers": {
                "strict-transport-security": {"required": True},
                "content-security-policy": {"required": False},
            },
            "frame_protection_required": False,
        },
        fixture={
            "status": 200,
            "headers": {"X-Content-Type-Options": "nosniff"},
        },
    )
    _, payload, _ = _run(
        tmp_path, missing_required, case_dir=case_dir, output_name="required.json"
    )
    assert payload["results"][0]["status"] == "FAIL"

    optional_only = _config(
        case_dir.name,
        runner="http_header_check",
        method="HEAD",
        expected={
            "headers": {
                "strict-transport-security": {"required": False},
                "content-security-policy": {"required": False},
                "x-content-type-options": {"required": False},
                "referrer-policy": {"required": False},
            },
            "frame_protection_required": False,
            "status_codes": [200],
        },
        fixture={"status": 200, "headers": {}},
    )
    _, payload, _ = _run(
        tmp_path, optional_only, case_dir=case_dir, output_name="optional.json"
    )
    assert payload["results"][0]["status"] == "PASS"


def test_api_unexpected_status_and_body_limit(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(
        case_dir.name,
        runner="api_health_check",
        method="GET",
        expected={"status_code": 200, "content_type": "application/json"},
        fixture={
            "status": 503,
            "headers": {"Content-Type": "application/json"},
            "body": "x" * 500,
        },
    )
    _, payload, output = _run(tmp_path, config, case_dir=case_dir)
    result = payload["results"][0]
    assert result["status"] == "FAIL"
    assert result["runner_metadata"]["body_truncated"] is True
    evidence = json.loads((output.parent / result["evidence"][0]["path"]).read_text())
    assert evidence["response"]["body_stored"] is False
    assert evidence["response"]["truncated"] is True


def test_timeout_is_review_required_with_limited_retry(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(
        case_dir.name,
        runner="api_health_check",
        method="GET",
        fixture={"error": "timeout fixture"},
    )
    config["retry_count"] = 1
    _, payload, _ = _run(tmp_path, config, case_dir=case_dir)
    result = payload["results"][0]
    assert result["status"] == "REVIEW_REQUIRED"
    assert len(result["runner_metadata"]["attempts"]) == 2


def test_redirect_limit_is_review_required(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(
        case_dir.name,
        runner="http_header_check",
        method="HEAD",
        fixture={
            "status": 200,
            "headers": {},
            "redirect_chain": [{"status": 302}] * 3,
        },
    )
    config["max_redirects"] = 2
    _, payload, _ = _run(tmp_path, config, case_dir=case_dir)
    assert payload["results"][0]["status"] == "REVIEW_REQUIRED"
    assert "redirect limit" in payload["results"][0]["actual_result"]


def test_sensitive_headers_masked():
    masked = mask_sensitive_headers(
        {
            "Authorization": "Bearer abc.def",
            "Cookie": "session=secret",
            "Set-Cookie": "session=secret",
            "X-Trace": "token=abc",
        }
    )
    assert masked["Authorization"] == "[REDACTED]"
    assert masked["Cookie"] == "[REDACTED]"
    assert masked["Set-Cookie"] == "[REDACTED]"
    assert "abc" not in masked["X-Trace"]


def test_evidence_hash_and_execution_schema_compatible(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(
        case_dir.name,
        fixture={
            "negotiated_tls_version": "TLSv1.3",
            "certificate_not_after": "2030-01-01T00:00:00Z",
            "hostname_matches": True,
        },
    )
    _, payload, output = _run(tmp_path, config, case_dir=case_dir)
    assert validate_execution_payload(payload) == []
    evidence = payload["results"][0]["evidence"][0]
    evidence_path = output.parent / evidence["path"]
    assert evidence_path.exists()
    assert len(evidence["sha256"]) == 64


def test_private_network_requires_explicit_policy(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(case_dir.name)
    config["target"]["host"] = "127.0.0.1"
    config["policy"]["allowed_hosts"] = ["127.0.0.1"]
    errors = validate_runner_config(
        config,
        case_id=case_dir.name,
        known_security_test_ids={"SI-01"},
    )
    assert any("private/local target blocked" in error for error in errors)
    config["policy"]["allow_private_network"] = True
    errors = validate_runner_config(
        config,
        case_id=case_dir.name,
        known_security_test_ids={"SI-01"},
    )
    assert errors == []


def test_port_list_scan_rejected(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(case_dir.name, runner="port_connectivity_check")
    config["checks"][0]["ports"] = [22, 80]
    errors = validate_runner_config(
        config,
        case_id=case_dir.name,
        known_security_test_ids={"SI-01"},
    )
    assert any("scan is forbidden" in error for error in errors)


def test_dry_run_never_uses_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    case_dir = _case(tmp_path)
    config = _config(case_dir.name)
    config_path = _write_config(tmp_path, config)

    def fail_network(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("network must not be used during dry-run")

    monkeypatch.setattr("socket.getaddrinfo", fail_network)
    monkeypatch.setattr("socket.create_connection", fail_network)
    output = tmp_path / "dry.json"
    result = dry_run_security_tests(
        case_dir,
        config_path,
        output_path=output,
        synthetic=False,
    )
    assert result["network_requests_performed"] == 0
    assert not output.exists()


def test_synthetic_flag_metrics_and_import_e2e(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(
        case_dir.name,
        fixture={
            "negotiated_tls_version": "TLSv1.3",
            "certificate_not_after": "2030-01-01T00:00:00Z",
            "hostname_matches": True,
        },
    )
    summary, payload, output = _run(tmp_path, config, case_dir=case_dir)
    assert payload["synthetic"] is True
    assert summary["no_network"] is True
    assert summary["metrics"]["configured_check_count"] == 1
    imported = import_security_results(case_dir, output)
    assert imported["results_imported"] == 1
    overlay = json.loads(
        (case_dir / "security_test_results.json").read_text(encoding="utf-8")
    )
    history = overlay["results_by_test"]["SI-01-T01"]["history"]
    assert history[0]["synthetic"] is True


def test_disabled_check_is_not_executed(tmp_path: Path):
    case_dir = _case(tmp_path)
    config = _config(case_dir.name)
    config["checks"][0]["enabled"] = False
    _, payload, _ = _run(tmp_path, config, case_dir=case_dir)
    assert payload["results"][0]["status"] == "NOT_EXECUTED"
    assert payload["runner_metrics"]["not_executed_count"] == 1
