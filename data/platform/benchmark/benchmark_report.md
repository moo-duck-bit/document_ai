# Platform Benchmark Report

- **Version:** 1.0
- **Overall score:** 0.9848
- **Scenarios run:** document_change, operation_analysis, hybrid_workflow, self_improvement

## Planner

| Metric | Value |
|--------|-------|
| intent_accuracy | 1.0 |
| workflow_template_accuracy | 1.0 |
| hybrid_accuracy | 1.0 |
| planner_accuracy | 1.0 |

## Runtime

| Metric | Value |
|--------|-------|
| workflow_success_rate | 1.0 |
| task_success_rate | 1.0 |
| avg_execution_latency_ms | 298.39 |
| memory_generation_rate | 0.6667 |
| scenario_count | 3 |

## Document Harness

| Metric | Value |
|--------|-------|
| impact_precision | 0.8333333333333333 |
| impact_recall | 1.0 |
| impact_f1 | 0.8933333333333333 |
| changed_req_f1 | 1.0 |
| linked_security_f1 | 0.8 |
| linked_document_f1 | 0.6666666666666666 |

## Operation Harness

| Metric | Value |
|--------|-------|
| incident_count | 11 |
| incident_detection_precision | 0.8181818181818182 |
| incident_detection_recall | 1.0 |
| false_positive_incidents | 2 |
| severity_match | 1.0 |
| log_event_type_recall | 1.0 |

## Memory

| Metric | Value |
|--------|-------|
| memory_generation_rate | 1.0 |
| orphan_node_count | 0 |
| reasoning_step_count | 5 |
| trace_completeness | 1.0 |

## Self Improvement

| Metric | Value |
|--------|-------|
| recommendation_generation_rate | 1.0 |
| retry_candidate_generation_rate | 0.0 |
| strategy_recommendation_generation_rate | 1.0 |
| failure_pattern_count | 0 |

## Collaboration

| Metric | Value |
|--------|-------|
| proposal_count | 12.0 |
| conflict_count | 1.33 |
| consensus_confidence | 0.8925 |
| review_approval_rate | 1.0 |
