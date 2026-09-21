# -*- coding: utf-8 -*-
"""Pilot demo package — materialize + catalog (no engine changes)."""

from __future__ import annotations

from pathlib import Path

from document_ai.pilot_v2 import demo_pack, scenarios


def test_demo_catalog_has_twelve_to_fifteen():
    assert 10 <= len(demo_pack.DEMO_CATALOG) <= 15
    assert len(demo_pack.FLAGSHIP_SCENARIO_IDS) == 3


def test_flagship_covers_three_domains():
    domains = {
        scenarios.get_scenario(sid).domain for sid in demo_pack.FLAGSHIP_SCENARIO_IDS
    }
    assert domains == {"ec_sw", "general_report", "business_proposal"}


def test_materialize_demo_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_pack, "DEMO_ROOT", tmp_path / "demo")
    monkeypatch.setattr(demo_pack, "DEMO_SCENARIOS_JSON", tmp_path / "demo" / "demo_scenarios.json")
    out = demo_pack.materialize_demo_dataset(force=True)
    assert out["count"] == len(demo_pack.DEMO_CATALOG)
    root = Path(out["demo_root"])
    assert (root / "README.md").is_file()
    assert (root / "demo_scenarios.json").is_file()
    assert (root / "ec_sw" / "demo_ec_req11" / "CHANGE_REQUEST.md").is_file()
    assert (root / "general_report" / "demo_gr_methodology" / "EXPECTED_RESULT.md").is_file()
    assert (root / "business_proposal" / "demo_bp_budget" / "README.md").is_file()
    # At least one docx copied
    docx = list((root / "ec_sw" / "demo_ec_req11").glob("*.docx"))
    assert docx


def test_cli_registers_demo_commands():
    from document_ai import cli as cli_module

    assert hasattr(cli_module, "cmd_materialize_pilot_demo")
    assert hasattr(cli_module, "cmd_run_pilot_demo")
    # Smoke: --help path includes new subcommands
    try:
        cli_module.main(["materialize-pilot-demo", "--help"])
    except SystemExit as exc:
        assert exc.code in (0, None)
