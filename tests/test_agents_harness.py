import json
from pathlib import Path

import pytest

from document_ai.agents.orchestrator import IMPACT_REPORT_NAME, run_change_pipeline
from document_ai.agents.requirement_agent import RequirementAgent
from document_ai.agents.traceability_agent import TraceabilityAgent
from document_ai.agents.base import AgentContext


@pytest.fixture(scope="module")
def mindrium_case():
    return Path("data/cases/mindrium_xa")


@pytest.fixture(scope="module")
def req6_change(mindrium_case):
    return json.loads((mindrium_case / "changes" / "req6_update.json").read_text(encoding="utf-8"))


def test_requirement_agent_validates_change(req6_change, mindrium_case):
    payload = json.loads((mindrium_case / "requirements.json").read_text(encoding="utf-8"))
    ctx = AgentContext(case_dir=mindrium_case, change=req6_change, requirements_payload=payload)
    result = RequirementAgent().run(ctx)
    assert result.status == "ok"
    assert result.data["req_ids"] == ["Req. 6"]
    assert result.data["confirmed"] is True


def test_traceability_agent_req6(req6_change, mindrium_case):
    payload = json.loads((mindrium_case / "requirements.json").read_text(encoding="utf-8"))
    ctx = AgentContext(case_dir=mindrium_case, change=req6_change, requirements_payload=payload)
    req_result = RequirementAgent().run(ctx)
    ctx.prior["requirement"] = req_result.data
    trace = TraceabilityAgent().run(ctx)
    assert trace.status == "ok"
    assert "IA-04" in trace.data["linked_security_ids"]
    assert trace.data["documents"]["spec_requirements"]["action"] == "patch"


def test_run_change_pipeline_dry_run_writes_report(req6_change, mindrium_case, tmp_path):
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    for name in ("requirements.json",):
        src = mindrium_case / name
        if src.exists():
            (case_copy / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    changes_dir = case_copy / "changes"
    changes_dir.mkdir()
    change_path = changes_dir / "req6_update.json"
    change_path.write_text(json.dumps(req6_change, ensure_ascii=False, indent=2), encoding="utf-8")

    report = run_change_pipeline(case_copy, change_path, dry_run=True, apply=False, change_path=change_path)
    report_file = case_copy / IMPACT_REPORT_NAME

    assert report_file.exists()
    assert report["dry_run"] is True
    assert report["mode"] == "dry-run"
    assert "requirement" in report["agents"]
    assert "traceability" in report["agents"]
    assert "IA-04" in report["impact"]["linked_security_ids"]
    assert report["impact_report"] == str(report_file)


def test_cli_impact_command(mindrium_case, capsys):
    from argparse import Namespace
    from document_ai.cli import cmd_impact

    change = mindrium_case / "changes" / "req6_update.json"
    code = cmd_impact(
        Namespace(case=str(mindrium_case), change=str(change), dry_run=True)
    )
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["agents"]["traceability"]["data"]["linked_security_ids"]
    assert (mindrium_case / IMPACT_REPORT_NAME).exists()
