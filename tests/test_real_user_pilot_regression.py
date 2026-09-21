# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — hard regression guard.

These assertions encode the non-negotiable safety invariants from the
Product Validation Cycle 1 spec. They must hold regardless of future
refactors of pilot_v2 or its wiring into cli.py / pilot_ui/app.py.

Explicitly NOT covered here (by design): re-running the full frozen
benchmark holdout suite. That suite is validated separately and must never
be regenerated or re-scored as a side effect of pilot work.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_V2_SRC = REPO_ROOT / "src" / "document_ai" / "pilot_v2"

FORBIDDEN_PATH_FRAGMENTS = (
    "Desktop",
    "examples",
    "Freeze",
    "freeze",
    "document_set_benchmark_v2/fixtures",
    "document_set_benchmark/fixtures",
)


def _iter_pilot_v2_source_files():
    return sorted(PILOT_V2_SRC.rglob("*.py"))


def _code_only_lines(text: str) -> str:
    """Strip module/function docstrings and '#' comments so the forbidden-path
    scan only inspects executable code (prose explaining what NOT to do, in a
    docstring, is fine and expected — an actual path literal in code is not).
    """
    # Drop triple-quoted docstring blocks (non-greedy, handles both quote styles).
    without_docstrings = re.sub(r'"""[\s\S]*?"""', "", text)
    without_docstrings = re.sub(r"'''[\s\S]*?'''", "", without_docstrings)
    code_lines = []
    for line in without_docstrings.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        code_lines.append(line)
    return "\n".join(code_lines)


# --- static source scan: no writes to Desktop/examples/Freeze paths ------------------


def test_pilot_v2_source_files_exist():
    files = _iter_pilot_v2_source_files()
    assert len(files) >= 10, "expected the full pilot_v2 package to be present"


@pytest.mark.parametrize("path", _iter_pilot_v2_source_files(), ids=lambda p: p.name)
def test_no_desktop_examples_or_freeze_literals_in_pilot_v2_source(path: Path):
    code = _code_only_lines(path.read_text(encoding="utf-8"))
    for fragment in FORBIDDEN_PATH_FRAGMENTS:
        assert fragment not in code, f"{path.name} references forbidden path fragment {fragment!r} in executable code"


def test_pilot_v2_never_imports_examples_or_desktop_modules():
    pattern = re.compile(r"^\s*(from|import)\s+.*\b(examples|desktop)\b", re.IGNORECASE | re.MULTILINE)
    for path in _iter_pilot_v2_source_files():
        code = _code_only_lines(path.read_text(encoding="utf-8"))
        assert not pattern.search(code), f"{path.name} appears to import an examples/desktop module"


def test_scenarios_module_only_writes_under_pilot_owned_scenarios_dir():
    code = _code_only_lines((PILOT_V2_SRC / "scenarios.py").read_text(encoding="utf-8"))
    # The module must declare its own pilot-owned fixtures root and must not
    # reference the frozen benchmark's fixtures directory in executable code.
    assert 'PILOT_ROOT = REPO / "data" / "pilot"' in code
    assert "document_set_benchmark" not in code


# --- writer without approval is always blocked ---------------------------------------


def test_writer_without_approval_is_blocked(tmp_path):
    from document_ai.pilot_v2 import orchestrator as pv2
    from document_ai.pilot_v2 import scenarios

    scenario = scenarios.get_scenario("pilot_bp_no_impact")
    fixture_path = scenarios.ensure_fixture(scenario)
    session = pv2.create_session(
        document_set=scenario.document_set,
        change_request=scenario.change_request,
        scenario_id=scenario.scenario_id,
        root=tmp_path,
    )
    sid = session["session_id"]
    pv2.upload_documents(sid, [(fixture_path.name, fixture_path.read_bytes(), scenario.fixture_role)], root=tmp_path)
    pv2.resolve_identity(sid, routing_mode="explicit", root=tmp_path)
    pv2.analyze(sid, root=tmp_path)

    # No decisions applied at all -> nothing is APPROVE'd.
    result = pv2.run_writer_if_allowed(
        sid, enable_write=True, env={"CONTROLLED_WRITER_ENABLED": "true"}, root=tmp_path
    )
    wr = result["writer_result"]
    assert wr["status"] == "BLOCKED"
    assert wr["copies_written"] == []
    assert "NOT_APPROVED" in wr["reason_codes"]


def test_writer_blocked_even_with_approval_if_env_var_unset(tmp_path):
    from document_ai.pilot_v2 import orchestrator as pv2
    from document_ai.pilot_v2 import scenarios

    scenario = scenarios.get_scenario("pilot_gr_conclusion")
    fixture_path = scenarios.ensure_fixture(scenario)
    session = pv2.create_session(
        document_set=scenario.document_set,
        change_request=scenario.change_request,
        scenario_id=scenario.scenario_id,
        root=tmp_path,
    )
    sid = session["session_id"]
    pv2.upload_documents(sid, [(fixture_path.name, fixture_path.read_bytes(), scenario.fixture_role)], root=tmp_path)
    pv2.resolve_identity(sid, routing_mode="explicit", root=tmp_path)
    session = pv2.analyze(sid, root=tmp_path)
    items = session.get("review_items") or []
    if items:
        decisions = [{"item_id": i["item_id"], "decision": "APPROVE"} for i in items]
        pv2.apply_decisions(sid, decisions, root=tmp_path)

    result = pv2.run_writer_if_allowed(sid, enable_write=True, env={}, root=tmp_path)
    wr = result["writer_result"]
    assert wr["status"] != "WRITTEN_COPY_ONLY"
    assert wr["copies_written"] == []


# --- original preservation invariant in session store ---------------------------------


def test_session_store_copy_upload_never_mutates_source_bytes_object(tmp_path):
    from document_ai.pilot_v2 import session_store

    session_root = session_store.create_session_workspace("s_regress", root=tmp_path)
    original_bytes = b"PK\x03\x04-original-payload"
    descriptor = session_store.copy_upload_into_session(session_root, "doc.docx", original_bytes)
    # The in-memory bytes object handed in must be unaffected (bytes are
    # immutable, but assert the recorded hash matches what was passed in).
    assert descriptor["sha256"] == session_store.sha256_bytes(original_bytes)
    assert original_bytes == b"PK\x03\x04-original-payload"


def test_session_store_verify_original_preserved_detects_any_tamper(tmp_path):
    from document_ai.pilot_v2 import session_store

    session_root = session_store.create_session_workspace("s_regress2", root=tmp_path)
    descriptor = session_store.copy_upload_into_session(session_root, "doc.docx", b"hello-world")
    doc_path = Path(descriptor["path"])
    assert session_store.verify_original_preserved(doc_path, descriptor["sha256"])["ok"] is True

    doc_path.write_bytes(b"hello-world-TAMPERED")
    assert session_store.verify_original_preserved(doc_path, descriptor["sha256"])["ok"] is False


def test_writer_gated_copy_asserts_source_and_dest_are_distinct_paths():
    from document_ai.pilot_v2 import security

    with pytest.raises(security.PilotSecurityError):
        p = Path("C:/tmp/session/input/doc.docx") if Path("C:/").exists() else Path("/tmp/session/input/doc.docx")
        security.assert_source_copy_distinct(p, p)


# --- domain pack imports still work (smoke) --------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "document_ai.workflow",
        "document_ai.document_identity.orchestrator",
        "document_ai.controlled_writer.capability_gate",
        "document_ai.evaluation.document_set_v2.format_preservation",
        "document_ai.pilot_v2.orchestrator",
        "document_ai.pilot_v2.scenarios",
        "document_ai.pilot_v2.security",
        "document_ai.pilot_v2.session_store",
        "document_ai.pilot_v2.metrics",
        "document_ai.pilot_v2.evaluate_run",
        "document_ai.pilot_v2.cli_support",
        "document_ai.pilot_v2.reason_i18n",
        "document_ai.pilot_v2.format_check",
    ],
)
def test_domain_pack_and_pilot_v2_modules_import_cleanly(module_name):
    import importlib

    module = importlib.import_module(module_name)
    assert module is not None


def test_pilot_ui_app_wires_pilot_v2_routes_without_error():
    from document_ai.pilot_ui.app import create_app

    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/pilot-v2" in paths
    assert "/api/pilot-v2/scenarios" in paths
    # Original workflow + legacy pilot routes must still be present.
    assert "/workflow" in paths
    assert "/" in paths


def test_cli_module_registers_pilot_subcommands():
    from document_ai import cli as cli_module

    parser = cli_module.build_parser() if hasattr(cli_module, "build_parser") else None
    if parser is None:
        # Fall back to a smoke check that the handler functions exist and are wired.
        assert hasattr(cli_module, "cmd_run_pilot_session")
        assert hasattr(cli_module, "cmd_evaluate_pilot")
        return
    args = parser.parse_args(["run-pilot-session", "--scenario", "pilot_ec_req_single", "--dry-review"])
    assert args.func is cli_module.cmd_run_pilot_session
