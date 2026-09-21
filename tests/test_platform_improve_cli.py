import json
from argparse import Namespace
from pathlib import Path

import pytest

from document_ai.cli import cmd_platform_improve, cmd_platform_run
from document_ai.platform.runtime import PlatformRuntime

MINDRIUM = Path("data/cases/mindrium_xa")
CHANGE = MINDRIUM / "changes" / "req6_update.json"


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


def test_platform_improve_smoke(tmp_path, capsys):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    runtime = PlatformRuntime()
    runtime.run(
        case_dir=case_copy,
        change=change_path,
        request_id="improve-smoke",
    )

    code = cmd_platform_improve(
        Namespace(case=str(case_copy), correlation_id=None, out=None)
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["case_id"] == case_copy.name
    assert "failure_patterns" in data
    assert "retry_candidates" in data
    assert "planner_recommendations" in data
    assert "memory_summary" in data


def test_platform_improve_writes_out_file(tmp_path):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"
    out_path = tmp_path / "improvement_feedback.json"

    runtime = PlatformRuntime()
    runtime.run(
        case_dir=case_copy,
        change=change_path,
        request_id="improve-out",
    )

    code = cmd_platform_improve(
        Namespace(case=str(case_copy), correlation_id=None, out=str(out_path))
    )
    assert code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["case_id"] == case_copy.name


def test_platform_improve_includes_recommendation_fields_after_failure(tmp_path, capsys):
    case_copy = _copy_mindrium_case(tmp_path)
    change_path = case_copy / "changes" / "req6_update.json"

    class BrokenHarnessManager:
        def run(self, name, request, task):
            raise RuntimeError("improve cli harness failed")

    runtime = PlatformRuntime(harness_manager=BrokenHarnessManager())
    with pytest.raises(RuntimeError, match="improve cli harness failed"):
        runtime.run(
            case_dir=case_copy,
            change=change_path,
            request_id="improve-failed",
        )

    code = cmd_platform_improve(
        Namespace(case=str(case_copy), correlation_id=None, out=None)
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)

    assert data["failure_patterns"]
    assert any(item["action"] == "retry_task" for item in data["retry_candidates"])
    assert any(item["action"] == "apply_improvement_feedback" for item in data["planner_recommendations"])


def test_platform_improve_missing_case_returns_error(tmp_path, capsys):
    out_path = tmp_path / "error.json"
    code = cmd_platform_improve(
        Namespace(
            case=str(tmp_path / "missing-case"),
            correlation_id=None,
            out=str(out_path),
        )
    )
    assert code == 1
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["error"]["type"] == "FileNotFoundError"
