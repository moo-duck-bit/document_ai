from __future__ import annotations

from typing import Any

from document_ai.eval.metrics import _as_set, _recall
from document_ai.learn.req_ids import normalize_requirement_id


def precision_recall_f1(predicted: set[str], expected: set[str]) -> dict[str, float]:
    if not predicted and not expected:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not predicted:
        return {"precision": 0.0, "recall": 0.0 if expected else 1.0, "f1": 0.0}
    if not expected:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0}

    tp = len(predicted & expected)
    precision = tp / len(predicted)
    recall = tp / len(expected)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def score_planner_prediction(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    intent_match = 1.0 if actual.get("intent") == expected.get("intent") else 0.0
    template_match = 1.0 if actual.get("workflow_template") == expected.get("workflow_template") else 0.0
    hybrid_match = 1.0 if bool(actual.get("hybrid")) == bool(expected.get("hybrid")) else 0.0
    accuracy = (intent_match + template_match + hybrid_match) / 3.0
    return {
        "intent_accuracy": intent_match,
        "workflow_template_accuracy": template_match,
        "hybrid_accuracy": hybrid_match,
        "planner_accuracy": accuracy,
        "actual": actual,
        "expected": expected,
    }


def score_document_impact(
    impact: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    traceability = impact.get("agents", {}).get("traceability", {}).get("data", {})
    pred_changed = _as_set(traceability.get("changed_req_ids"))
    pred_security = _as_set(traceability.get("linked_security_ids"))
    pred_test = _as_set(traceability.get("linked_test_ids"))
    pred_design = _as_set(traceability.get("linked_design_req_ids"))
    pred_docs = set((traceability.get("documents") or {}).keys())

    exp_changed = _as_set(expected.get("expected_changed_req_ids"))
    exp_security = _as_set(expected.get("expected_linked_security_ids"))
    exp_test = _as_set(expected.get("expected_linked_test_ids"))
    exp_design = _as_set(expected.get("expected_design_ids"))
    exp_docs = set(expected.get("expected_linked_documents") or [])

    changed = precision_recall_f1(pred_changed, exp_changed)
    security = precision_recall_f1(pred_security, exp_security)
    test = precision_recall_f1(pred_test, exp_test)
    design = precision_recall_f1(pred_design, exp_design)
    documents = precision_recall_f1(pred_docs, exp_docs)

    components = [changed["f1"], security["f1"], test["f1"], design["f1"], documents["f1"]]
    impact_f1 = sum(components) / len(components)

    return {
        "impact_precision": (changed["precision"] + security["precision"]) / 2,
        "impact_recall": _recall(pred_security | pred_changed, exp_security | exp_changed),
        "impact_f1": impact_f1,
        "changed_req_f1": changed["f1"],
        "linked_security_f1": security["f1"],
        "linked_document_f1": documents["f1"],
        "details": {
            "predicted_changed_req_ids": sorted(pred_changed),
            "expected_changed_req_ids": sorted(exp_changed),
            "predicted_linked_security_ids": sorted(pred_security),
            "expected_linked_security_ids": sorted(exp_security),
            "predicted_linked_documents": sorted(pred_docs),
            "expected_linked_documents": sorted(exp_docs),
        },
    }


def score_operation_incidents(
    report: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    incidents = report.get("incidents", [])
    keywords = [keyword.lower() for keyword in expected.get("expected_incident_keywords", [])]
    matched = 0
    for incident in incidents:
        title = str(incident.get("title", "")).lower()
        if any(keyword in title for keyword in keywords):
            matched += 1

    detected_types = {event.get("event_type") for event in report.get("log_events", [])}
    expected_types = set(expected.get("min_log_event_types", []))
    type_recall = len(detected_types & expected_types) / len(expected_types) if expected_types else 1.0

    false_positives = max(0, len(incidents) - matched)
    precision = matched / len(incidents) if incidents else 0.0
    recall = matched / max(len(keywords), 1)

    return {
        "incident_count": len(incidents),
        "incident_detection_precision": precision,
        "incident_detection_recall": min(1.0, recall),
        "false_positive_incidents": false_positives,
        "severity_match": 1.0 if report.get("severity") == expected.get("expected_severity") else 0.0,
        "log_event_type_recall": type_recall,
        "detected_log_event_types": sorted(detected_types),
    }


def score_memory_artifacts(
    case_dir: Any,
    *,
    required_artifacts: list[str],
    knowledge_payload: dict[str, Any] | None = None,
    reasoning_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from pathlib import Path

    case_path = Path(case_dir)
    checks: dict[str, bool] = {}
    for relative in required_artifacts:
        checks[relative] = (case_path / relative).exists()

    generation_rate = sum(1 for value in checks.values() if value) / len(checks) if checks else 0.0
    orphan_count = 0
    if knowledge_payload:
        orphan_count = int(knowledge_payload.get("orphan_count", 0))

    trace_steps = 0
    if reasoning_trace:
        trace_steps = len(reasoning_trace.get("steps", []))

    return {
        "memory_generation_rate": generation_rate,
        "artifact_checks": checks,
        "orphan_node_count": orphan_count,
        "reasoning_step_count": trace_steps,
        "trace_completeness": 1.0 if trace_steps > 0 else 0.0,
    }


def score_improvement_feedback(feedback: dict[str, Any]) -> dict[str, Any]:
    has_recommendations = any(
        feedback.get(key)
        for key in (
            "planner_recommendations",
            "harness_recommendations",
            "workflow_recommendations",
            "strategy_recommendations",
            "retry_candidates",
        )
    )
    return {
        "recommendation_generation_rate": 1.0 if has_recommendations else 0.0,
        "retry_candidate_generation_rate": 1.0 if feedback.get("retry_candidates") else 0.0,
        "strategy_recommendation_generation_rate": 1.0 if feedback.get("strategy_recommendations") else 0.0,
        "failure_pattern_count": len(feedback.get("failure_patterns", [])),
    }


def score_collaboration(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    proposals = result.get("proposals", [])
    discussion = result.get("discussion", {})
    consensus = result.get("consensus", {})
    proposal_count = len(proposals)
    conflict_count = len(discussion.get("conflicts", []))
    agent_ids = {proposal.get("agent_id") for proposal in proposals}
    min_proposals = int(expected.get("min_proposal_count", 1))
    min_agents = int(expected.get("min_agents", 1))

    return {
        "proposal_count": proposal_count,
        "proposal_count_met": proposal_count >= min_proposals,
        "agent_count": len(agent_ids),
        "agent_count_met": len(agent_ids) >= min_agents,
        "conflict_count": conflict_count,
        "consensus_confidence": float(consensus.get("confidence", 0.0)),
        "review_approval_rate": 1.0 if result.get("review_approved") else 0.0,
        "review_status": consensus.get("review_status", "unknown"),
    }


def score_runtime_result(
    runtime_result: Any,
    *,
    latency_ms: float,
    memory_generated: bool,
) -> dict[str, Any]:
    task_results = getattr(runtime_result, "task_results", {}) or {}
    task_count = len(task_results)
    completed = sum(1 for result in task_results.values() if result)
    task_success_rate = completed / task_count if task_count else 0.0

    return {
        "workflow_success_rate": 1.0 if task_count and completed == task_count else 0.0,
        "task_success_rate": task_success_rate,
        "task_count": task_count,
        "execution_latency_ms": round(latency_ms, 2),
        "memory_generated": memory_generated,
        "workflow_id": getattr(runtime_result, "workflow_id", ""),
        "evaluation_id": getattr(runtime_result, "evaluation_id", ""),
    }


def compute_overall_score(category_scores: dict[str, float]) -> float:
    if not category_scores:
        return 0.0
    return round(sum(category_scores.values()) / len(category_scores), 4)
