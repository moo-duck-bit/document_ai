"""XXCS gold vs generated comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.learn.extract_security_tests import extract_security_tests_docx
from document_ai.learn.req_ids import normalize_requirement_id, parse_linked_ids
from document_ai.validation.docx_compare import text_similarity

EXPLICIT_EMPTY_OK = {
    "NOT_EXECUTED",
    "NOT_APPLICABLE",
    "NOT_COLLECTED",
    "REVIEW_REQUIRED",
}


def _id_set(tests: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for test in tests:
        rid = normalize_requirement_id(test.get("req_id", "")) or test.get("req_id", "")
        if rid:
            ids.add(rid)
    return ids


def _is_filled(value: Any, *, allow_status: bool = True) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if allow_status and any(token in text for token in EXPLICIT_EMPTY_OK):
        return True
    return True


def _field_completeness(test: dict[str, Any], field: str) -> float:
    aliases = {
        "test_method": ("test_method",),
        "test_procedure": ("test_procedure",),
        "expected_result": ("expected_result",),
        "actual_result": ("actual_result", "test_result"),
        "satisfaction": ("satisfaction",),
        "evidence": ("evidence", "notes"),
    }[field]
    return 1.0 if any(_is_filled(test.get(alias)) for alias in aliases) else 0.0


def _plan_completeness(test: dict[str, Any]) -> float:
    fields = ("test_method", "test_procedure", "expected_result")
    return sum(_field_completeness(test, field) for field in fields) / len(fields)


def _execution_completeness(test: dict[str, Any]) -> float:
    actual = str(test.get("actual_result") or test.get("test_result") or "")
    evidence = str(test.get("evidence") or test.get("notes") or "")
    if any(token in actual for token in ("NOT_EXECUTED", "NOT_APPLICABLE")):
        return 1.0
    if "NOT_COLLECTED" in evidence and not any(
        token in actual for token in EXPLICIT_EMPTY_OK
    ):
        return 0.0
    fields = ("actual_result", "satisfaction", "evidence")
    return sum(_field_completeness(test, field) for field in fields) / len(fields)


def _completeness(test: dict[str, Any]) -> float:
    fields = (
        "test_method",
        "test_procedure",
        "expected_result",
        "actual_result",
        "satisfaction",
        "evidence",
    )
    return sum(_field_completeness(test, field) for field in fields) / len(fields)


def _linked_ids(test: dict[str, Any], key: str) -> list[str]:
    value = test.get(key)
    if isinstance(value, list):
        return [
            normalized
            for item in value
            if (normalized := normalize_requirement_id(str(item)))
        ]
    return parse_linked_ids(str(value or ""))


def compare_xxcs(
    generated_path: Path,
    gold_path: Path,
    *,
    requirements_payload: dict[str, Any] | None = None,
    design_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gen = extract_security_tests_docx(generated_path)
    gold = extract_security_tests_docx(gold_path)
    gen_tests = gen.get("tests") or []
    gold_tests = gold.get("tests") or []
    gen_ids = _id_set(gen_tests)
    gold_ids = _id_set(gold_tests)

    matched = len(gold_ids & gen_ids)
    security_coverage = matched / len(gold_ids) if gold_ids else (1.0 if not gen_ids else 0.0)

    gen_by = { (normalize_requirement_id(t.get("req_id","")) or t.get("req_id")): t for t in gen_tests }
    gold_by = { (normalize_requirement_id(t.get("req_id","")) or t.get("req_id")): t for t in gold_tests }
    sims: list[float] = []
    completeness: list[float] = []
    plan_completeness: list[float] = []
    execution_completeness: list[float] = []
    field_scores: dict[str, list[float]] = {
        "test_method_completeness": [],
        "procedure_completeness": [],
        "expected_result_completeness": [],
        "actual_result_completeness": [],
        "satisfaction_completeness": [],
        "evidence_completeness": [],
    }
    for rid, gold_t in gold_by.items():
        gen_t = gen_by.get(rid)
        if not gen_t:
            continue
        sims.append(text_similarity(gen_t.get("test_result", ""), gold_t.get("test_result", "")))
        completeness.append(_completeness(gen_t))
        plan_completeness.append(_plan_completeness(gen_t))
        execution_completeness.append(_execution_completeness(gen_t))
        field_scores["test_method_completeness"].append(_field_completeness(gen_t, "test_method"))
        field_scores["procedure_completeness"].append(_field_completeness(gen_t, "test_procedure"))
        field_scores["expected_result_completeness"].append(_field_completeness(gen_t, "expected_result"))
        field_scores["actual_result_completeness"].append(_field_completeness(gen_t, "actual_result"))
        field_scores["satisfaction_completeness"].append(_field_completeness(gen_t, "satisfaction"))
        field_scores["evidence_completeness"].append(_field_completeness(gen_t, "evidence"))

    # Linked requirement coverage: security rows referencing Req.* present in MDSR
    req_ids: set[str] = set()
    if requirements_payload:
        for item in requirements_payload.get("requirements") or []:
            rid = normalize_requirement_id(item.get("req_id", ""))
            if rid:
                req_ids.add(rid)
        for row in requirements_payload.get("traceability") or []:
            for linked in parse_linked_ids(str(row.get("linked_reqs") or "")):
                if linked.startswith("Req"):
                    req_ids.add(linked)

    design_ids: set[str] = set()
    if design_payload:
        for item in design_payload.get("items") or []:
            rid = normalize_requirement_id(item.get("req_id") or item.get("design_id") or "")
            if rid:
                design_ids.add(rid)

    linked_req_hits = 0
    linked_req_total = 0
    linked_design_hits = 0
    linked_design_total = 0
    for test in gen_tests:
        linked = _linked_ids(test, "linked_req_ids") or _linked_ids(test, "linked_reqs")
        # Also parse from test_result annotation
        if not linked:
            linked = [t for t in parse_linked_ids(str(test.get("test_result") or "")) if t.startswith("Req")]
        if linked:
            linked_req_total += 1
            if any(r in req_ids for r in linked) or not req_ids:
                linked_req_hits += 1
        design_linked = _linked_ids(test, "linked_design_ids")
        if not design_linked:
            design_linked = [
                t for t in parse_linked_ids(str(test.get("notes") or "") + "\n" + str(test.get("test_result") or ""))
                if t.startswith("Req")
            ]
        if design_ids:
            linked_design_total += 1
            if any(d in design_ids for d in design_linked) or any(
                d in design_ids for d in linked
            ):
                linked_design_hits += 1

    item_completeness = (
        sum(completeness) / len(completeness) if completeness else (1.0 if not gold_tests else 0.0)
    )
    plan_item_completeness = (
        sum(plan_completeness) / len(plan_completeness)
        if plan_completeness
        else (1.0 if not gold_tests else 0.0)
    )
    execution_item_completeness = (
        sum(execution_completeness) / len(execution_completeness)
        if execution_completeness
        else (1.0 if not gold_tests else 0.0)
    )

    detailed = {
        key: round(sum(values) / len(values) if values else (1.0 if not gold_tests else 0.0), 3)
        for key, values in field_scores.items()
    }
    return {
        "security_coverage": round(security_coverage, 3),
        "security_id_count_match": round(
            min(len(gen_ids), len(gold_ids)) / max(len(gen_ids), len(gold_ids), 1),
            3,
        ),
        "test_text_similarity": round(sum(sims) / len(sims) if sims else 1.0, 3),
        "test_item_completeness": round(item_completeness, 3),
        "plan_test_completeness": round(plan_item_completeness, 3),
        "execution_test_completeness": round(execution_item_completeness, 3),
        **detailed,
        "linked_requirement_coverage": round(
            linked_req_hits / linked_req_total if linked_req_total else 1.0,
            3,
        ),
        "linked_design_coverage": round(
            linked_design_hits / linked_design_total if linked_design_total else 1.0,
            3,
        ),
        "gold_security_id_count": len(gold_ids),
        "generated_security_id_count": len(gen_ids),
        "missing_in_generated": sorted(gold_ids - gen_ids),
        "extra_in_generated": sorted(gen_ids - gold_ids),
        "gold_test_count": len(gold_tests),
        "generated_test_count": len(gen_tests),
    }
