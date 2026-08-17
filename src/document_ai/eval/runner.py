from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.agents.requirement_agent import RequirementAgent
from document_ai.eval.metrics import compute_metrics
from document_ai.eval.report import write_evaluation_report
from document_ai.intake.change_intake import load_requirements_payload
from document_ai.learn.req_ids import normalize_requirement_id
from document_ai.paths import PROJECT_ROOT


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    rows: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    idx = 0
    length = len(text)
    while idx < length:
        while idx < length and text[idx] in " \t\r\n":
            idx += 1
        if idx >= length:
            break
        obj, end = decoder.raw_decode(text, idx)
        rows.append(obj)
        idx = end
    return rows


def assert_no_duplicate_case_ids(rows: list[dict[str, Any]], *, source: str) -> None:
    seen: set[str] = set()
    for row in rows:
        case_id = row.get("case_id")
        if not case_id:
            continue
        if case_id in seen:
            raise ValueError(f"duplicate case_id in {source}: {case_id!r}")
        seen.add(case_id)


def index_by_case_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    assert_no_duplicate_case_ids(rows, source="expected impacts dataset")
    return {row["case_id"]: row for row in rows if row.get("case_id")}


def resolve_case_path(case_path: str | Path) -> Path:
    raw = Path(case_path)
    return raw if raw.is_absolute() else (PROJECT_ROOT / raw)


PREDICTION_SCHEMA_KEYS = (
    "case_id",
    "status",
    "predicted_changed_req_ids",
    "predicted_linked_security_ids",
    "predicted_linked_test_ids",
    "predicted_design_ids",
    "clarification_needed",
    "patch_success",
    "raw_report_path",
    "error_message",
)


def finalize_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "case_id": prediction.get("case_id", ""),
        "status": prediction.get("status", "ok"),
        "predicted_changed_req_ids": list(prediction.get("predicted_changed_req_ids") or []),
        "predicted_linked_security_ids": list(prediction.get("predicted_linked_security_ids") or []),
        "predicted_linked_test_ids": list(prediction.get("predicted_linked_test_ids") or []),
        "predicted_design_ids": list(prediction.get("predicted_design_ids") or []),
        "clarification_needed": bool(prediction.get("clarification_needed")),
        "patch_success": bool(prediction.get("patch_success")),
        "raw_report_path": prediction.get("raw_report_path") or "",
        "error_message": prediction.get("error_message") or prediction.get("error") or "",
    }
    if "predicted_linked_documents" in prediction:
        out["predicted_linked_documents"] = list(prediction.get("predicted_linked_documents") or [])
    if "method" in prediction:
        out["method"] = prediction["method"]
    return out


def make_error_prediction(case_id: str, error_message: str) -> dict[str, Any]:
    return finalize_prediction(
        {
            "case_id": case_id,
            "status": "error",
            "error_message": error_message,
            "patch_success": False,
        }
    )


def normalize_change_dict(change: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(change)
    req_changes: list[dict[str, Any]] = []
    for item in change.get("requirement_changes", []):
        req_id = normalize_requirement_id(item.get("req_id") or item.get("id", ""))
        if not req_id:
            continue
        req_changes.append(
            {
                "req_id": req_id,
                "description": item.get("description", ""),
                "purpose": item.get("purpose"),
                "criteria": item.get("criteria"),
            }
        )
    normalized["requirement_changes"] = req_changes
    return normalized


def _linked_documents_from_report(report: dict[str, Any]) -> list[str]:
    documents = (report.get("impact") or {}).get("documents") or {}
    linked: list[str] = []
    for doc_id, spec in documents.items():
        action = (spec or {}).get("action", "skip")
        if action in {"patch", "review"}:
            linked.append(doc_id)
    return sorted(linked)


def prediction_from_report(case_id: str, report: dict[str, Any], *, report_path: Path) -> dict[str, Any]:
    impact = report.get("impact") or {}
    agents = report.get("agents") or {}
    requirement = agents.get("requirement", {}).get("data", {})
    traceability = agents.get("traceability", {}).get("data", {})
    design = agents.get("design", {}).get("data", {})

    clarification_needed = not requirement.get("confirmed", True)
    if requirement.get("clarifying_questions"):
        clarification_needed = True

    review_status = (report.get("review") or {}).get("status", "ok")
    patch_success = review_status != "error" and not report.get("error")

    return finalize_prediction(
        {
            "case_id": case_id,
            "status": "ok",
            "predicted_changed_req_ids": impact.get("changed_req_ids")
            or requirement.get("req_ids")
            or [],
            "predicted_linked_security_ids": impact.get("linked_security_ids")
            or traceability.get("linked_security_ids")
            or [],
            "predicted_linked_test_ids": impact.get("linked_test_ids")
            or traceability.get("linked_test_ids")
            or [],
            "predicted_design_ids": design.get("linked_design_req_ids")
            or traceability.get("linked_design_req_ids")
            or [],
            "predicted_linked_documents": _linked_documents_from_report(report),
            "clarification_needed": clarification_needed,
            "patch_success": patch_success,
            "raw_report_path": str(report_path),
            "error_message": "",
            "method": report.get("method", "harness"),
        }
    )


def run_eval_case(case: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    case_id = case["case_id"]
    case_path = resolve_case_path(case["case_path"])
    method = case.get("method", "harness")
    reports_dir = out_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{case_id}_impact_report.json"

    if case.get("input_type") == "natural_language":
        requirements_payload = load_requirements_payload(case_path)
        change = RequirementAgent.draft_from_request(
            case.get("request", ""),
            requirements_payload=requirements_payload,
        )
    else:
        change = normalize_change_dict(case.get("change", {}))

    change.setdefault("change_id", f"eval-{case_id}")

    if not change.get("requirement_changes"):
        report = {
            "case_dir": str(case_path),
            "change_id": change.get("change_id"),
            "dry_run": True,
            "mode": "dry-run",
            "method": method,
            "agents": {
                "requirement": {
                    "data": {
                        "req_ids": [],
                        "confirmed": change.get("intake", {}).get("confirmed", False),
                        "clarifying_questions": change.get("intake", {}).get("clarifying_questions", []),
                    }
                }
            },
            "impact": {
                "changed_req_ids": [],
                "linked_security_ids": [],
                "linked_test_ids": [],
                "documents": {},
            },
            "review": {"status": "ok", "issues": []},
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        prediction = prediction_from_report(case_id, report, report_path=report_path)
        if method != "harness":
            prediction["method"] = method
        return finalize_prediction(prediction)

    report = run_change_pipeline(
        case_path,
        change,
        dry_run=True,
        apply=False,
        report_path=report_path,
    )
    report["method"] = method
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    prediction = prediction_from_report(case_id, report, report_path=report_path)
    if method != "harness":
        prediction["method"] = method
    return finalize_prediction(prediction)


def run_evaluation(
    cases_path: Path,
    expected_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = load_jsonl(cases_path)
    assert_no_duplicate_case_ids(cases, source=str(cases_path))
    expected_rows = load_jsonl(expected_path)
    expected_by_id = index_by_case_id(expected_rows)
    case_ids = {case["case_id"] for case in cases if case.get("case_id")}
    orphan_expected_cases = sorted(set(expected_by_id) - case_ids)

    predictions: list[dict[str, Any]] = []
    runtime_errors: list[dict[str, Any]] = []

    for case in cases:
        case_id = case.get("case_id", "unknown")
        try:
            predictions.append(run_eval_case(case, out_dir))
        except Exception as exc:  # noqa: BLE001 — collect per-case eval errors
            runtime_errors.append({"case_id": case_id, "error": str(exc)})
            predictions.append(make_error_prediction(case_id, str(exc)))

    metrics = compute_metrics(predictions, expected_by_id)
    metrics["orphan_expected_cases"] = orphan_expected_cases
    metrics["orphan_expected_count"] = len(orphan_expected_cases)
    metrics["runtime_errors"] = runtime_errors

    predictions_path = out_dir / "predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as fh:
        for row in predictions:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_evaluation_report(metrics, predictions, runtime_errors, out_dir)
    metrics["predictions_path"] = str(predictions_path)
    metrics["output_dir"] = str(out_dir)
    return metrics
