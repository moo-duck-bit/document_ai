from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_BASELINE_PATH = Path("data/eval/platform_baseline.json")


def load_baseline(path: str | Path | None = None) -> dict[str, Any]:
    baseline_path = Path(path) if path else DEFAULT_BASELINE_PATH
    if not baseline_path.exists():
        return {}
    return json.loads(baseline_path.read_text(encoding="utf-8"))


def save_baseline(report: dict[str, Any], path: str | Path | None = None) -> Path:
    baseline_path = Path(path) if path else DEFAULT_BASELINE_PATH
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": report.get("version", "1.0"),
        "overall_score": report.get("overall_score", 0.0),
        "planner_metrics": report.get("planner_metrics", {}),
        "runtime_metrics": report.get("runtime_metrics", {}),
        "document_metrics": report.get("document_metrics", {}),
        "operation_metrics": report.get("operation_metrics", {}),
        "memory_metrics": report.get("memory_metrics", {}),
        "improvement_metrics": report.get("improvement_metrics", {}),
        "collaboration_metrics": report.get("collaboration_metrics", {}),
    }
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return baseline_path
