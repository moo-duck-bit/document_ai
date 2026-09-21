import json
from argparse import Namespace
from pathlib import Path

import pytest

from document_ai.cli import cmd_platform_benchmark
from document_ai.platform.evaluation.benchmark_runner import PlatformBenchmarkRunner, load_benchmark_config
from document_ai.platform.evaluation.metrics import precision_recall_f1, score_planner_prediction
from document_ai.platform.evaluation.regression import compare_against_baseline
from document_ai.platform.evaluation.report_generator import generate_markdown_report


def test_precision_recall_f1_perfect_match():
    scores = precision_recall_f1({"A", "B"}, {"A", "B"})
    assert scores["f1"] == 1.0


def test_planner_prediction_scoring():
    result = score_planner_prediction(
        {"intent": "document_change", "workflow_template": "document_workflow", "hybrid": False},
        {"intent": "document_change", "workflow_template": "document_workflow", "hybrid": False},
    )
    assert result["planner_accuracy"] == 1.0


def test_regression_detects_drop():
    current = {"overall_score": 0.7, "planner_metrics": {"planner_accuracy": 0.8}}
    baseline = {"overall_score": 0.9, "planner_metrics": {"planner_accuracy": 0.95}}
    result = compare_against_baseline(current, baseline)
    assert result["passed"] is False
    assert result["regression_count"] >= 1


def test_markdown_report_generation():
    report = {
        "version": "1.0",
        "overall_score": 0.85,
        "scenarios_run": ["document_change"],
        "planner_metrics": {"planner_accuracy": 1.0},
        "runtime_metrics": {"workflow_success_rate": 1.0},
    }
    md = generate_markdown_report(report)
    assert "# Platform Benchmark Report" in md
    assert "planner_accuracy" in md


def test_benchmark_runner_smoke(tmp_path):
    runner = PlatformBenchmarkRunner(
        config=load_benchmark_config(),
        work_dir=tmp_path / "work",
    )
    report = runner.run(out_dir=tmp_path / "results", update_baseline=False)

    assert report["overall_score"] > 0
    assert "document_change" in report["scenarios_run"]
    assert "hybrid_workflow" in report["scenarios_run"]
    assert "operation_analysis" in report["scenarios_run"]
    assert "self_improvement" in report["scenarios_run"]
    assert report["planner_metrics"]["planner_accuracy"] >= 0
    assert report["runtime_metrics"]["workflow_success_rate"] == 1.0
    assert report["document_metrics"]["impact_f1"] > 0
    assert report["operation_metrics"]["incident_count"] >= 5
    assert report["memory_metrics"]["memory_generation_rate"] >= 0.8
    assert "proposal_count" in report["collaboration_metrics"]

    json_path = tmp_path / "results" / "benchmark_report.json"
    md_path = tmp_path / "results" / "benchmark_report.md"
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["overall_score"] == report["overall_score"]


def test_platform_benchmark_cli(tmp_path, capsys):
    code = cmd_platform_benchmark(
        Namespace(
            out=str(tmp_path / "cli-benchmark"),
            baseline=None,
            work_dir=str(tmp_path / "cli-work"),
            update_baseline=False,
        )
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["overall_score"] > 0
    assert (tmp_path / "cli-benchmark" / "benchmark_report.json").exists()
