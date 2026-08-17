from __future__ import annotations

from typing import Any

from document_ai.learn.req_ids import normalize_requirement_id


def _as_set(values: list[str] | None) -> set[str]:
    out: set[str] = set()
    for value in values or []:
        normalized = normalize_requirement_id(value) or value.strip()
        if normalized:
            out.add(normalized)
    return out


def _recall(predicted: set[str], expected: set[str]) -> float:
    if not expected:
        return 1.0
    return len(predicted & expected) / len(expected)


def _accuracy_exact(predicted: set[str], expected: set[str]) -> float:
    if not expected and not predicted:
        return 1.0
    if not expected:
        return 0.0 if predicted else 1.0
    return 1.0 if predicted == expected else len(predicted & expected) / len(expected)


def _false_positive_rate(predicted: set[str], expected: set[str]) -> float:
    if not predicted:
        return 0.0
    return len(predicted - expected) / len(predicted)


def score_prediction(predicted: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    pred_changed = _as_set(predicted.get("predicted_changed_req_ids"))
    exp_changed = _as_set(expected.get("expected_changed_req_ids"))

    pred_security = _as_set(predicted.get("predicted_linked_security_ids"))
    exp_security = _as_set(expected.get("expected_linked_security_ids"))

    pred_test = _as_set(predicted.get("predicted_linked_test_ids"))
    exp_test = _as_set(expected.get("expected_linked_test_ids"))

    pred_design = _as_set(predicted.get("predicted_design_ids"))
    exp_design = _as_set(expected.get("expected_design_ids"))

    pred_docs = set(predicted.get("predicted_linked_documents") or [])
    exp_docs = set(expected.get("expected_linked_documents") or [])

    pred_clarify = bool(predicted.get("clarification_needed"))
    exp_clarify = bool(expected.get("clarification_needed"))

    return {
        "case_id": predicted.get("case_id") or expected.get("case_id"),
        "changed_req_id_detection_accuracy": _accuracy_exact(pred_changed, exp_changed),
        "linked_security_id_recall": _recall(pred_security, exp_security),
        "linked_test_id_recall": _recall(pred_test, exp_test),
        "linked_design_id_recall": _recall(pred_design, exp_design),
        "linked_document_recall": _recall(pred_docs, exp_docs),
        "false_positive_rate": _false_positive_rate(
            pred_changed | pred_security | pred_test | pred_design | pred_docs,
            exp_changed | exp_security | exp_test | exp_design | exp_docs,
        ),
        "clarification_needed_accuracy": 1.0 if pred_clarify == exp_clarify else 0.0,
        "patch_success_rate": 1.0 if predicted.get("patch_success") else 0.0,
        "details": {
            "predicted_changed_req_ids": sorted(pred_changed),
            "expected_changed_req_ids": sorted(exp_changed),
            "predicted_linked_security_ids": sorted(pred_security),
            "expected_linked_security_ids": sorted(exp_security),
            "predicted_linked_test_ids": sorted(pred_test),
            "expected_linked_test_ids": sorted(exp_test),
            "predicted_design_ids": sorted(pred_design),
            "expected_design_ids": sorted(exp_design),
            "predicted_linked_documents": sorted(pred_docs),
            "expected_linked_documents": sorted(exp_docs),
            "predicted_clarification_needed": pred_clarify,
            "expected_clarification_needed": exp_clarify,
            "patch_success": predicted.get("patch_success"),
        },
    }


def compute_metrics(
    predictions: list[dict[str, Any]],
    expected_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    case_scores: list[dict[str, Any]] = []
    metric_keys = [
        "changed_req_id_detection_accuracy",
        "linked_security_id_recall",
        "linked_test_id_recall",
        "linked_design_id_recall",
        "linked_document_recall",
        "false_positive_rate",
        "clarification_needed_accuracy",
        "patch_success_rate",
    ]

    skipped_cases: list[dict[str, Any]] = []
    error_cases: list[dict[str, Any]] = []

    for prediction in predictions:
        case_id = prediction.get("case_id")
        if prediction.get("status") == "error":
            error_cases.append(
                {
                    "case_id": case_id,
                    "eval_skipped": True,
                    "reason": "runtime_error",
                    "error_message": prediction.get("error_message") or "",
                }
            )
            continue
        if case_id not in expected_by_id:
            skipped_cases.append(
                {
                    "case_id": case_id,
                    "eval_skipped": True,
                    "reason": "missing_expected",
                }
            )
            continue
        case_scores.append(score_prediction(prediction, expected_by_id[case_id]))

    summary: dict[str, float] = {}
    for key in metric_keys:
        values = [row[key] for row in case_scores if key in row]
        summary[key] = sum(values) / len(values) if values else 0.0

    result: dict[str, Any] = {
        "summary": summary,
        "case_count": len(case_scores),
        "cases": case_scores,
        "skipped_cases": skipped_cases,
        "skipped_count": len(skipped_cases),
        "error_cases": error_cases,
        "error_count": len(error_cases),
    }
    if len(case_scores) == 0:
        result["warning"] = (
            "No scorable cases: all cases were skipped, errored, or lacked expected labels."
        )
    return result
