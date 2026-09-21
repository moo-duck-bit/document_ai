from __future__ import annotations

from typing import Any


DEFAULT_THRESHOLDS = {
    "overall_score": -0.05,
    "planner_metrics.planner_accuracy": -0.05,
    "runtime_metrics.workflow_success_rate": -0.01,
    "document_metrics.impact_f1": -0.05,
    "operation_metrics.incident_detection_recall": -0.05,
    "memory_metrics.memory_generation_rate": -0.01,
}


def _get_nested(data: dict[str, Any], dotted_key: str) -> Any:
    current: Any = data
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def compare_against_baseline(
    report: dict[str, Any],
    baseline: dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    limits = thresholds or DEFAULT_THRESHOLDS
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []

    for key, min_delta in limits.items():
        current = _get_nested(report, key)
        previous = _get_nested(baseline, key)
        if current is None or previous is None:
            continue
        delta = float(current) - float(previous)
        entry = {"metric": key, "current": current, "baseline": previous, "delta": round(delta, 4)}
        if delta < min_delta:
            entry["status"] = "regression"
            regressions.append(entry)
        elif delta > 0:
            entry["status"] = "improved"
            improvements.append(entry)
        else:
            entry["status"] = "stable"
            improvements.append(entry)

    return {
        "baseline_available": bool(baseline),
        "regression_count": len(regressions),
        "regressions": regressions,
        "improvements": improvements,
        "passed": len(regressions) == 0,
    }
