from __future__ import annotations

from typing import Any

from document_ai.platform.improvement.execution_feedback import FailurePattern, Recommendation


def detect_failure_patterns(memory_snapshot: dict[str, Any]) -> list[FailurePattern]:
    patterns: list[FailurePattern] = []

    evaluations = memory_snapshot.get("evaluations", {}).get("evaluations", [])
    failed_evaluations = [entry for entry in evaluations if entry.get("status") == "failed"]
    if len(failed_evaluations) >= 2:
        patterns.append(
            FailurePattern(
                pattern_id="repeated_evaluation_failure",
                category="evaluation",
                description="Multiple failed evaluations detected for this case",
                count=len(failed_evaluations),
                evidence=failed_evaluations[-3:],
            )
        )
    elif failed_evaluations:
        patterns.append(
            FailurePattern(
                pattern_id="evaluation_failure",
                category="evaluation",
                description="Recent evaluation failed",
                count=1,
                evidence=failed_evaluations,
            )
        )

    events = memory_snapshot.get("events", {}).get("events", [])
    runtime_failed = [event for event in events if event.get("event_type") == "RuntimeFailed"]
    if len(runtime_failed) >= 2:
        patterns.append(
            FailurePattern(
                pattern_id="repeated_runtime_failure",
                category="event",
                description="Runtime failures occurred repeatedly",
                count=len(runtime_failed),
                evidence=runtime_failed[-3:],
            )
        )
    elif runtime_failed:
        patterns.append(
            FailurePattern(
                pattern_id="runtime_failure",
                category="event",
                description="Recent runtime failure detected",
                count=1,
                evidence=runtime_failed,
            )
        )

    workflows = memory_snapshot.get("tasks", {}).get("workflows", [])
    failed_workflows = [entry for entry in workflows if entry.get("status") == "FAILED"]
    if failed_workflows:
        patterns.append(
            FailurePattern(
                pattern_id="workflow_failure",
                category="task",
                description="One or more workflows ended in FAILED state",
                count=len(failed_workflows),
                evidence=failed_workflows[-3:],
            )
        )

    traces = memory_snapshot.get("reasoning", {}).get("traces", [])
    failed_traces = [trace for trace in traces if trace.get("status") == "failed"]
    if failed_traces:
        patterns.append(
            FailurePattern(
                pattern_id="reasoning_failure",
                category="reasoning",
                description="Reasoning traces recorded failure outcomes",
                count=len(failed_traces),
                evidence=failed_traces[-3:],
            )
        )

    harness_failures = _count_harness_failures(events)
    for harness, count in harness_failures.items():
        if count >= 2:
            patterns.append(
                FailurePattern(
                    pattern_id=f"repeated_{harness}_harness_failure",
                    category="harness",
                    description=f"{harness} harness failed repeatedly",
                    count=count,
                    evidence=[
                        event
                        for event in events
                        if event.get("event_type") == "RuntimeFailed"
                        and event.get("harness") == harness
                    ][-3:],
                )
            )

    return patterns


def recommend_retries(
    memory_snapshot: dict[str, Any],
    *,
    failure_patterns: list[FailurePattern],
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    events = memory_snapshot.get("events", {}).get("events", [])

    for event in reversed(events):
        if event.get("event_type") != "RuntimeFailed":
            continue
        task_id = event.get("task_id") or ""
        workflow_id = event.get("workflow_id") or ""
        if not task_id:
            continue
        recommendations.append(
            Recommendation(
                category="retry",
                action="retry_task",
                reason=f"Retry task {task_id} after runtime failure",
                confidence=0.7,
                metadata={
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "correlation_id": event.get("correlation_id"),
                },
            )
        )
        break

    if any(pattern.pattern_id == "repeated_evaluation_failure" for pattern in failure_patterns):
        recommendations.append(
            Recommendation(
                category="retry",
                action="retry_with_dry_run",
                reason="Repeated evaluation failures suggest validating with dry-run before apply",
                confidence=0.8,
                metadata={"dry_run": True, "apply": False},
            )
        )

    return recommendations


def recommend_workflow_changes(
    memory_snapshot: dict[str, Any],
    *,
    failure_patterns: list[FailurePattern],
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    workflows = memory_snapshot.get("tasks", {}).get("workflows", [])

    hybrid_failures = [
        workflow
        for workflow in workflows
        if workflow.get("status") == "FAILED"
        and workflow.get("metadata", {}).get("hybrid") is True
    ]
    if hybrid_failures:
        recommendations.append(
            Recommendation(
                category="workflow",
                action="split_hybrid_workflow",
                reason="Hybrid workflow failures may improve if document and operation are planned separately",
                confidence=0.65,
                metadata={"suggested_templates": ["document_workflow", "operation_workflow"]},
            )
        )

    if any(pattern.category == "task" for pattern in failure_patterns):
        recommendations.append(
            Recommendation(
                category="workflow",
                action="reduce_workflow_scope",
                reason="Task failures suggest narrowing workflow scope before re-planning",
                confidence=0.6,
                metadata={"prefer_single_harness": True},
            )
        )

    return recommendations


def recommend_harness_changes(
    memory_snapshot: dict[str, Any],
    *,
    failure_patterns: list[FailurePattern],
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    knowledge = memory_snapshot.get("knowledge", {})

    for pattern in failure_patterns:
        if pattern.pattern_id == "repeated_document_harness_failure":
            recommendations.append(
                Recommendation(
                    category="harness",
                    action="validate_document_inputs",
                    reason="Document harness failures often trace to missing requirements or change files",
                    confidence=0.75,
                    metadata={"harness": "document"},
                )
            )
        if pattern.pattern_id == "repeated_operation_harness_failure":
            recommendations.append(
                Recommendation(
                    category="harness",
                    action="validate_operation_samples",
                    reason="Operation harness failures may be caused by missing sample_dir or log files",
                    confidence=0.75,
                    metadata={"harness": "operation"},
                )
            )

    if knowledge.get("available") is False:
        recommendations.append(
            Recommendation(
                category="harness",
                action="refresh_knowledge_graph",
                reason="Knowledge graph unavailable; document harness planning may lack traceability context",
                confidence=0.7,
                metadata={"harness": "document"},
            )
        )

    return recommendations


def recommend_strategy_changes(
    memory_snapshot: dict[str, Any],
    *,
    failure_patterns: list[FailurePattern],
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    workflows = memory_snapshot.get("tasks", {}).get("workflows", [])

    has_cascade_failure = any(
        pattern.pattern_id in {"runtime_failure", "repeated_runtime_failure", "workflow_failure"}
        for pattern in failure_patterns
    )
    if has_cascade_failure:
        recommendations.append(
            Recommendation(
                category="strategy",
                action="prefer_sequential",
                reason="Cascade failures benefit from sequential execution with dependency checks",
                confidence=0.8,
                metadata={"execution_strategy": "sequential"},
            )
        )
    elif workflows and not failure_patterns:
        recommendations.append(
            Recommendation(
                category="strategy",
                action="consider_parallel",
                reason="No recent failures detected; independent harness steps may run in parallel",
                confidence=0.55,
                metadata={"execution_strategy": "parallel"},
            )
        )

    if any(pattern.pattern_id == "repeated_runtime_failure" for pattern in failure_patterns):
        recommendations.append(
            Recommendation(
                category="strategy",
                action="prefer_sequential",
                reason="Repeated runtime failures indicate unstable parallel execution conditions",
                confidence=0.85,
                metadata={"execution_strategy": "sequential"},
            )
        )

    return recommendations


def _count_harness_failures(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if event.get("event_type") != "RuntimeFailed":
            continue
        harness = event.get("harness")
        if not harness:
            continue
        counts[harness] = counts.get(harness, 0) + 1
    return counts
