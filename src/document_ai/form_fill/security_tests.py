"""XXCS security-test learning helpers and synthesis."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_ai.learn.extract_security_tests import (
    extract_security_tests_docx,
    load_security_tests,
    save_security_tests,
)
from document_ai.learn.req_ids import normalize_requirement_id, parse_linked_ids

SECURITY_PREFIX = re.compile(r"^(IA|UC|SI|DC|RA)-\d+", re.IGNORECASE)
DEFAULT_SEED = Path("data/examples/ec_sw/security_tests_mindrium_xa.json")
STATUS_NOT_EXECUTED = "NOT_EXECUTED"


def normalize_security_id(value: str) -> str | None:
    """Normalize IA-04 / IA 04 / IA04 security IDs."""
    raw = (value or "").strip()
    if not raw:
        return None
    match = re.search(r"\b(IA|UC|SI|DC|RA)[\s-]?(\d{1,3})\b", raw, re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1).upper()}-{int(match.group(2)):02d}"


def extract_security_test_ids_from_requirements(requirements_payload: dict[str, Any]) -> list[str]:
    """Collect IA/UC/SI/DC/RA ids from MDSR-style requirements.traceability."""
    found: list[str] = []
    for row in requirements_payload.get("traceability") or []:
        raw = str(row.get("requirement") or "").strip()
        token = raw.split()[0] if raw else ""
        normalized = normalize_security_id(token)
        if normalized and normalized not in found:
            found.append(normalized)
        for linked in parse_linked_ids(str(row.get("linked_reqs") or "")):
            sec = normalize_security_id(linked)
            if sec and sec not in found:
                found.append(sec)
    return found


def design_ids_from_payload(design_payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in design_payload.get("items") or []:
        rid = normalize_requirement_id(item.get("req_id") or item.get("design_id") or "")
        if rid and rid not in ids:
            ids.append(rid)
    return ids


def _linked_req_ids(text: str) -> list[str]:
    if not text or text.strip().upper() == "N/A":
        return []
    ids: list[str] = []
    for part in re.split(r"[,;/\n]+", text):
        normalized = normalize_requirement_id(part.strip())
        if normalized and normalized not in ids:
            ids.append(normalized)
    return ids


def _traceability_map(requirements_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    trace: dict[str, dict[str, Any]] = {}
    for row in requirements_payload.get("traceability") or []:
        security_id = normalize_security_id(str(row.get("requirement") or ""))
        if not security_id:
            continue
        linked = _linked_req_ids(str(row.get("linked_reqs") or ""))
        trace[security_id] = {
            "linked_req_ids": linked,
            "title": row.get("title") or "",
            "applicability": row.get("applicability") or "",
        }
    return trace


def _linked_design_ids_for_req_ids(
    linked_req_ids: list[str],
    design_payload: dict[str, Any],
) -> list[str]:
    design_ids = set(design_ids_from_payload(design_payload))
    linked: list[str] = []
    for req_id in linked_req_ids:
        normalized = normalize_requirement_id(req_id) or req_id
        if normalized in design_ids and normalized not in linked:
            linked.append(normalized)
    return linked


def enrich_security_test_links(
    test: dict[str, Any],
    *,
    trace_map: dict[str, dict[str, Any]],
    design_payload: dict[str, Any],
) -> dict[str, Any]:
    security_id = normalize_security_id(str(test.get("req_id") or test.get("security_test_id") or ""))
    if not security_id:
        return test
    trace = trace_map.get(security_id, {})
    linked_req_ids = list(test.get("linked_req_ids") or [])
    if not linked_req_ids:
        linked_req_ids = _linked_req_ids(str(test.get("linked_reqs") or ""))
    if not linked_req_ids:
        linked_req_ids = list(trace.get("linked_req_ids") or [])
    linked_design_ids = list(test.get("linked_design_ids") or [])
    if isinstance(test.get("linked_design_ids"), str):
        linked_design_ids = _linked_req_ids(str(test.get("linked_design_ids") or ""))
    if not linked_design_ids:
        linked_design_ids = _linked_design_ids_for_req_ids(linked_req_ids, design_payload)

    provenance = dict(test.get("provenance") or {})
    provenance.setdefault("linked_design_rule", "security linked_req_ids intersect MDDR design req_id")
    provenance.setdefault("linked_req_source", "requirements.traceability")
    return {
        **test,
        "req_id": security_id,
        "security_test_id": test.get("security_test_id") or f"{security_id}-T01",
        "security_category": test.get("security_category") or security_id.split("-", 1)[0],
        "title": test.get("title") or trace.get("title") or security_id,
        "linked_req_ids": linked_req_ids,
        "linked_design_ids": linked_design_ids,
        "linked_reqs": ", ".join(linked_req_ids),
        "provenance": provenance,
    }


def _default_row(
    req_id: str,
    *,
    product: str,
    title: str,
    linked_req_ids: list[str],
    linked_design_ids: list[str],
    applicability: str = "",
) -> dict[str, Any]:
    linked_reqs = ", ".join(linked_req_ids)
    linked_designs = ", ".join(linked_design_ids)
    method = "document_review_and_static_analysis"
    procedure = (
        f"{product} {req_id}({title}) 보안 요구사항에 대해 산출물 검토, "
        "요구사항-설계 추적성 확인, 정적 점검 계획을 작성한다."
    )
    expected = "연결된 요구사항과 설계 블록이 식별되고, 실제 시험 수행 전 검토 항목이 명확해야 한다."
    actual = "NOT_EXECUTED - 실제 시험 결과는 아직 수집되지 않았으며 human/security review에서 보완한다."
    evidence = "NOT_COLLECTED - 자동 생성 단계에서는 시험 증적을 첨부하지 않는다."
    return {
        "req_id": req_id,
        "security_test_id": f"{req_id}-T01",
        "security_category": req_id.split("-", 1)[0],
        "title": title or req_id,
        "requirement": req_id,
        "linked_req_ids": linked_req_ids,
        "linked_design_ids": linked_design_ids,
        "test_method": method,
        "test_procedure": procedure,
        "expected_result": expected,
        "actual_result": actual,
        "satisfaction": STATUS_NOT_EXECUTED if applicability != "비해당" else "NOT_APPLICABLE",
        "execution_status": "not_executed" if applicability != "비해당" else "not_applicable",
        "evidence": evidence,
        "reviewer_note": "자동 생성 시험 계획이다. 실제 시험 수행 후 actual_result/evidence를 갱신해야 한다.",
        # Backward-compatible runtime keys
        "test_result": f"시험방법: {method}\n절차: {procedure}\n예상결과: {expected}\n실제결과: {actual}",
        "applied": "비해당" if applicability == "비해당" else "planned",
        "notes": (
            f"linked_reqs: {linked_reqs or 'N/A'}\n"
            f"linked_design_ids: {linked_designs or 'N/A'}\n"
            f"evidence: {evidence}\n"
            "source: rule_generated_plan"
        ),
        "linked_reqs": linked_reqs,
        "provenance": {
            "source": "rule_generated_plan",
            "linked_design_rule": "security linked_req_ids intersect MDDR design req_id",
            "execution_truth": "not a real test execution",
        },
    }


def synthesize_security_tests(
    *,
    intake: dict[str, Any],
    requirements_payload: dict[str, Any] | None = None,
    design_payload: dict[str, Any] | None = None,
    seed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build security_tests.json from seed adaptation or MDSR traceability."""
    from document_ai.form_fill.rules import adapt_json_value, build_substitution_map

    product = (
        intake.get("product_name")
        or (intake.get("facts") or {}).get("product_name")
        or "Product"
    )
    requirements_payload = requirements_payload or {}
    design_payload = design_payload or {}
    trace_map = _traceability_map(requirements_payload)

    # Generate one clean, traceable plan row per security ID. Seed remains metadata
    # but is not copied verbatim because seed tables include label rows.
    security_ids = extract_security_test_ids_from_requirements(requirements_payload)
    if not security_ids:
        # fallback minimal set so XXCS render is still exercisable
        security_ids = [f"IA-{i:02d}" for i in range(1, 6)] + [f"UC-{i:02d}" for i in range(1, 4)]

    tests: list[dict[str, Any]] = []
    for rid in security_ids:
        trace = trace_map.get(rid, {})
        linked_req_ids = list(trace.get("linked_req_ids") or [])
        linked_design_ids = _linked_design_ids_for_req_ids(linked_req_ids, design_payload)
        tests.append(
            _default_row(
                rid,
                product=str(product),
                title=str(trace.get("title") or rid),
                linked_req_ids=linked_req_ids,
                linked_design_ids=linked_design_ids,
                applicability=str(trace.get("applicability") or ""),
            )
        )
    return {
        "source": "harness/form_fill synthesized from MDSR traceability",
        "tests": tests,
        "security_req_ids": security_ids,
        "linked_design_ids": design_ids_from_payload(design_payload),
        "seed_source": seed.get("source") if seed else None,
        "model_version": "xxcs-security-test-v2",
    }


def load_default_security_seed() -> dict[str, Any] | None:
    if DEFAULT_SEED.exists():
        return load_security_tests(DEFAULT_SEED)
    return None


def ensure_security_tests_payload(
    case_dir: Path,
    *,
    intake: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Ensure case/security_tests.json exists; build from seed/requirements if needed."""
    import json

    case_dir = case_dir.resolve()
    out = case_dir / "security_tests.json"
    if out.exists() and not overwrite:
        return json.loads(out.read_text(encoding="utf-8"))

    intake = intake or (
        json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
        if (case_dir / "input.json").exists()
        else {}
    )
    req = {}
    if (case_dir / "requirements.json").exists():
        req = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    design = {}
    if (case_dir / "design_items.json").exists():
        design = json.loads((case_dir / "design_items.json").read_text(encoding="utf-8"))

    seed = load_default_security_seed()
    payload = synthesize_security_tests(
        intake=intake,
        requirements_payload=req,
        design_payload=design,
        seed=seed,
    )
    save_security_tests(payload, out)
    return payload


# Re-export extract for learners / CLI callers that expect a single module entry.
__all__ = [
    "DEFAULT_SEED",
    "design_ids_from_payload",
    "ensure_security_tests_payload",
    "enrich_security_test_links",
    "extract_security_test_ids_from_requirements",
    "extract_security_tests_docx",
    "load_default_security_seed",
    "normalize_security_id",
    "synthesize_security_tests",
]
