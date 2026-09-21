# Evaluation Report

## Summary Metrics

| Metric | Score |
|--------|-------|
| `changed_req_id_detection_accuracy` | 100.0% |
| `linked_security_id_recall` | 100.0% |
| `linked_test_id_recall` | 100.0% |
| `linked_design_id_recall` | 100.0% |
| `linked_document_recall` | 100.0% |
| `false_positive_rate` | 11.1% |
| `clarification_needed_accuracy` | 100.0% |
| `patch_success_rate` | 100.0% |

**Cases evaluated:** 4

## Case Details

### req6_login_policy_change

- **changed_req_id_detection_accuracy**: 100.0%
- **linked_security_id_recall**: 100.0%
- **linked_test_id_recall**: 100.0%
- **linked_design_id_recall**: 100.0%
- **linked_document_recall**: 100.0%
- **false_positive_rate**: 22.2%
- **clarification_needed_accuracy**: 100.0%
- **patch_success_rate**: 100.0%

```json
{
  "predicted_changed_req_ids": [
    "Req. 6"
  ],
  "expected_changed_req_ids": [
    "Req. 6"
  ],
  "predicted_linked_security_ids": [
    "DC-01",
    "IA-04",
    "IA-06",
    "IA-07",
    "SI-06",
    "SI-07"
  ],
  "expected_linked_security_ids": [
    "IA-04",
    "IA-06",
    "IA-07",
    "SI-06"
  ],
  "predicted_linked_test_ids": [],
  "expected_linked_test_ids": [],
  "predicted_design_ids": [],
  "expected_design_ids": [],
  "predicted_linked_documents": [
    "report_security_verification",
    "spec_requirements"
  ],
  "expected_linked_documents": [
    "report_security_verification",
    "spec_requirements"
  ],
  "predicted_clarification_needed": false,
  "expected_clarification_needed": false,
  "patch_success": true
}
```

### req6_nl_missing_description

- **changed_req_id_detection_accuracy**: 100.0%
- **linked_security_id_recall**: 100.0%
- **linked_test_id_recall**: 100.0%
- **linked_design_id_recall**: 100.0%
- **linked_document_recall**: 100.0%
- **false_positive_rate**: 0.0%
- **clarification_needed_accuracy**: 100.0%
- **patch_success_rate**: 100.0%

```json
{
  "predicted_changed_req_ids": [],
  "expected_changed_req_ids": [],
  "predicted_linked_security_ids": [],
  "expected_linked_security_ids": [],
  "predicted_linked_test_ids": [],
  "expected_linked_test_ids": [],
  "predicted_design_ids": [],
  "expected_design_ids": [],
  "predicted_linked_documents": [],
  "expected_linked_documents": [],
  "predicted_clarification_needed": true,
  "expected_clarification_needed": true,
  "patch_success": true
}
```

### req6_nl_with_description

- **changed_req_id_detection_accuracy**: 100.0%
- **linked_security_id_recall**: 100.0%
- **linked_test_id_recall**: 100.0%
- **linked_design_id_recall**: 100.0%
- **linked_document_recall**: 100.0%
- **false_positive_rate**: 22.2%
- **clarification_needed_accuracy**: 100.0%
- **patch_success_rate**: 100.0%

```json
{
  "predicted_changed_req_ids": [
    "Req. 6"
  ],
  "expected_changed_req_ids": [
    "Req. 6"
  ],
  "predicted_linked_security_ids": [
    "DC-01",
    "IA-04",
    "IA-06",
    "IA-07",
    "SI-06",
    "SI-07"
  ],
  "expected_linked_security_ids": [
    "IA-04",
    "IA-06",
    "IA-07",
    "SI-06"
  ],
  "predicted_linked_test_ids": [],
  "expected_linked_test_ids": [],
  "predicted_design_ids": [],
  "expected_design_ids": [],
  "predicted_linked_documents": [
    "report_security_verification",
    "spec_requirements"
  ],
  "expected_linked_documents": [
    "report_security_verification",
    "spec_requirements"
  ],
  "predicted_clarification_needed": false,
  "expected_clarification_needed": false,
  "patch_success": true
}
```

### fr02_stt_tc_link

- **changed_req_id_detection_accuracy**: 100.0%
- **linked_security_id_recall**: 100.0%
- **linked_test_id_recall**: 100.0%
- **linked_design_id_recall**: 100.0%
- **linked_document_recall**: 100.0%
- **false_positive_rate**: 0.0%
- **clarification_needed_accuracy**: 100.0%
- **patch_success_rate**: 100.0%

```json
{
  "predicted_changed_req_ids": [
    "FR-02"
  ],
  "expected_changed_req_ids": [
    "FR-02"
  ],
  "predicted_linked_security_ids": [
    "TC-02"
  ],
  "expected_linked_security_ids": [],
  "predicted_linked_test_ids": [
    "TC-02"
  ],
  "expected_linked_test_ids": [
    "TC-02"
  ],
  "predicted_design_ids": [],
  "expected_design_ids": [],
  "predicted_linked_documents": [
    "spec_requirements",
    "test_cases"
  ],
  "expected_linked_documents": [
    "spec_requirements",
    "test_cases"
  ],
  "predicted_clarification_needed": false,
  "expected_clarification_needed": false,
  "patch_success": true
}
```

## Runtime Error Analysis

- No runtime errors during evaluation.

## Interpretation

This evaluation compares Multi-Agent Harness predictions against expected impact labels defined in `expected_impacts.jsonl`. Recall metrics treat an empty expected set as fully satisfied (1.0) to avoid division-by-zero. `false_positive_rate` aggregates extra predicted IDs across requirement, security, test, design, and document targets.

Use this report to compare harness vs single-LLM baselines by running the same `change_cases.jsonl` with different `method` values as baselines are added.
