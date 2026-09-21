import json
from argparse import Namespace
from pathlib import Path

import pytest

from document_ai.cli import cmd_platform_ops_analyze, cmd_platform_plan, cmd_platform_run

SAMPLES = Path("data/ops/samples")
MINDRIUM = Path("data/cases/mindrium_xa")
CHANGE = MINDRIUM / "changes" / "req6_update.json"
HYBRID_GOAL = "Req 변경 후 GPU 서버 장애 로그 분석"


def _copy_mindrium_case(tmp_path: Path) -> Path:
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    (case_copy / "requirements.json").write_text(
        (MINDRIUM / "requirements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    changes_dir = case_copy / "changes"
    changes_dir.mkdir()
    change_path = changes_dir / "req6_update.json"
    change_path.write_text(CHANGE.read_text(encoding="utf-8"), encoding="utf-8")
    return case_copy


def test_platform_plan_smoke(capsys):
    code = cmd_platform_plan(
        Namespace(
            goal=HYBRID_GOAL,
            case=str(MINDRIUM),
            change=str(CHANGE),
            sample_dir=str(SAMPLES),
            request_id="cli-plan",
            apply=False,
            out=None,
        )
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["plan_id"].startswith("plan-")
    assert data["intent"] == "document_change"
    assert data["hybrid"] is True
    assert data["workflow_template"] == "hybrid_workflow"
    assert data["harness_sequence"] == ["document", "operation"]
    assert data["execution_strategy"] == "sequential"
    assert data["estimated_steps"] == 2
    assert data["task_graph"]["graph_id"]


def test_platform_run_document_workflow_smoke(tmp_path, capsys):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    code = cmd_platform_run(
        Namespace(
            case=str(case_copy),
            change=str(change_path),
            goal=None,
            sample_dir=None,
            request_id="cli-run-doc",
            apply=False,
            out=None,
        )
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["correlation_id"] == "corr-cli-run-doc"
    assert data["workflow_id"]
    assert data["reasoning_id"]
    assert data["evaluation_id"]
    assert data["execution_plan_id"].startswith("plan-")
    assert "task-document-change-pipeline" in data["task_results"]
    assert data["task_results"]["task-document-change-pipeline"]["mode"] == "dry-run"


def test_platform_run_hybrid_workflow_smoke(tmp_path, capsys):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    code = cmd_platform_run(
        Namespace(
            case=str(case_copy),
            change=str(change_path),
            goal=HYBRID_GOAL,
            sample_dir=str(SAMPLES),
            request_id="cli-run-hybrid",
            apply=False,
            out=None,
        )
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data["task_results"].keys()) == {
        "task-document-change-pipeline",
        "task-operation-incident-analysis",
    }
    assert data["harness"] == "operation"


def test_platform_ops_analyze_smoke(capsys):
    code = cmd_platform_ops_analyze(
        Namespace(samples=str(SAMPLES), out=None)
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["sample_dir"]
    assert data["gpu_status"]
    assert data["docker_status"]
    assert data["log_events"]
    assert data["severity"] in {"low", "medium", "high", "critical"}
    assert data["incidents"]


def test_platform_run_writes_out_file(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"
    out_path = tmp_path / "runtime_result.json"

    code = cmd_platform_run(
        Namespace(
            case=str(case_copy),
            change=str(change_path),
            goal=None,
            sample_dir=None,
            request_id="cli-run-out",
            apply=False,
            out=str(out_path),
        )
    )
    assert code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["correlation_id"] == "corr-cli-run-out"
    assert data["task_results"]


def test_platform_plan_writes_out_file(tmp_path):
    out_path = tmp_path / "plan.json"
    code = cmd_platform_plan(
        Namespace(
            goal=HYBRID_GOAL,
            case=str(MINDRIUM),
            change=str(CHANGE),
            sample_dir=str(SAMPLES),
            request_id="cli-plan-out",
            apply=False,
            out=str(out_path),
        )
    )
    assert code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["plan_id"].startswith("plan-")


def test_platform_ops_analyze_writes_out_file(tmp_path):
    out_path = tmp_path / "incident_report.json"
    code = cmd_platform_ops_analyze(
        Namespace(samples=str(SAMPLES), out=str(out_path))
    )
    assert code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["incidents"]
