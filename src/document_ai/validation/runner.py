"""Document validation orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.learn.extract_design_items import _design_text_from_item, extract_design_items_docx
from document_ai.learn.req_ids import normalize_requirement_id as normalize_req_id
from document_ai.learn.extract_requirements import _req_id_sort_key
from document_ai.validation.docx_compare import summarize_docx_pair, text_similarity
from document_ai.validation.requirement_compare import compare_requirements
from document_ai.validation.section_compare import compare_sections
from document_ai.validation.traceability_compare import compare_traceability
from document_ai.validation.validation_report import (
    human_review_checklist,
    merge_metrics,
    render_validation_report,
    score_document,
    score_status,
)


def _default_gold_path(case_dir: Path, name: str) -> Path:
    return case_dir / name


def _index_design_items(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        req_id = normalize_req_id(item.get("req_id", "") or "")
        if req_id and req_id not in indexed:
            indexed[req_id] = item
    return indexed


def _compare_design_blocks(generated_path: Path, gold_path: Path) -> dict[str, Any]:
    """Compare MDDR design blocks with Req-ID primary matching.

    Coverage = fraction of gold Req IDs also present in generated (section
    numbering / paragraph position ignored). Text similarity is a secondary metric
    over the unified design body (title_suffix + description + fields).
    """
    gen_items = extract_design_items_docx(generated_path).get("items", [])
    gold_items = extract_design_items_docx(gold_path).get("items", [])
    gen_by_id = _index_design_items(gen_items)
    gold_by_id = _index_design_items(gold_items)

    all_ids = sorted(set(gen_by_id) | set(gold_by_id), key=_req_id_sort_key)
    similarities: list[float] = []
    missing: list[str] = []
    extra: list[str] = []
    high_risk: list[dict[str, Any]] = []
    matched = 0

    for req_id in all_ids:
        gold = gold_by_id.get(req_id)
        generated = gen_by_id.get(req_id)
        if gold is None:
            extra.append(req_id)
            continue
        if generated is None:
            missing.append(req_id)
            high_risk.append(
                {
                    "req_id": req_id,
                    "kind": "missing_design_block",
                    "detail": "Gold design block missing from generated MDDR",
                }
            )
            continue
        matched += 1
        gold_text = _design_text_from_item(gold)
        gen_text = _design_text_from_item(generated)
        sim = text_similarity(gen_text, gold_text)
        similarities.append(sim)
        if sim < 0.35 and gold_text:
            high_risk.append(
                {
                    "req_id": req_id,
                    "kind": "low_design_similarity",
                    "detail": f"Design block similarity {sim:.2f} vs gold",
                }
            )

    count_match = 0.0
    if gold_by_id or gen_by_id:
        count_match = min(len(gen_by_id), len(gold_by_id)) / max(len(gen_by_id), len(gold_by_id))

    # Req-ID coverage vs gold; content fill rate as secondary diagnostic
    coverage = matched / len(gold_by_id) if gold_by_id else 1.0
    content_filled = sum(1 for item in gen_items if _design_text_from_item(item))
    content_total = len(gen_items) or len(gold_items)
    content_fill_rate = (content_filled / content_total) if content_total else 1.0
    return {
        "design_block_coverage": round(coverage, 3),
        "design_block_content_fill_rate": round(content_fill_rate, 3),
        "design_block_count_match": round(count_match, 3),
        "design_block_text_similarity": round(
            sum(similarities) / len(similarities) if similarities else 1.0,
            3,
        ),
        "gold_design_block_count": len(gold_items),
        "generated_design_block_count": len(gen_items),
        "matched_design_block_count": matched,
        "missing_in_generated": missing,
        "extra_in_generated": extra,
        "high_risk": high_risk,
    }


def validate_mdsr(
    generated_path: Path,
    gold_path: Path,
    *,
    domain: str = "",
) -> dict[str, Any]:
    if not generated_path.exists() or not gold_path.exists():
        return {
            "label": "mdsr",
            "generated": str(generated_path),
            "gold": str(gold_path),
            "error": "missing document",
        }

    base = summarize_docx_pair(generated_path, gold_path, domain=domain)
    sections = compare_sections(generated_path, gold_path)
    requirements = compare_requirements(generated_path, gold_path)
    traceability = compare_traceability(generated_path, gold_path)

    metrics = merge_metrics(
        {
            "section_coverage": sections["section_coverage"],
            "paragraph_similarity": base["paragraph_similarity"],
            "requirement_count_match": requirements["requirement_count_match"],
            "requirement_text_similarity": requirements["requirement_text_similarity"],
            "requirement_completeness": requirements["requirement_completeness"],
            "traceability_coverage": traceability["traceability_coverage"],
            "traceability_row_match": traceability["traceability_row_match"],
            "residual_placeholder_count": base["residual_placeholder_count"],
            "domain_mismatch_count": base["domain_mismatch_count"],
        },
        requirements,
        traceability,
    )
    score = score_document(metrics)
    return {
        "label": "mdsr",
        "generated": str(generated_path),
        "gold": str(gold_path),
        "score": round(score, 1),
        "metrics": metrics,
        "sections": sections,
        "requirements": requirements,
        "traceability": traceability,
        "summary": base,
    }


def validate_mddr(
    generated_path: Path,
    gold_path: Path,
    *,
    domain: str = "",
) -> dict[str, Any]:
    if not generated_path.exists() or not gold_path.exists():
        return {
            "label": "mddr",
            "generated": str(generated_path),
            "gold": str(gold_path),
            "error": "missing document",
        }

    base = summarize_docx_pair(generated_path, gold_path, domain=domain)
    sections = compare_sections(generated_path, gold_path)
    design = _compare_design_blocks(generated_path, gold_path)

    metrics = merge_metrics(
        {
            "section_coverage": sections["section_coverage"],
            "paragraph_similarity": base["paragraph_similarity"],
            "design_block_coverage": design["design_block_coverage"],
            "requirement_count_match": design["design_block_count_match"],
            "requirement_text_similarity": design["design_block_text_similarity"],
            "residual_placeholder_count": base["residual_placeholder_count"],
            "domain_mismatch_count": base["domain_mismatch_count"],
        },
        design,
    )
    score = score_document(metrics)
    return {
        "label": "mddr",
        "generated": str(generated_path),
        "gold": str(gold_path),
        "score": round(score, 1),
        "metrics": metrics,
        "sections": sections,
        "design_blocks": design,
        "summary": base,
    }


def validate_xxcs(
    generated_path: Path,
    gold_path: Path,
    *,
    requirements_payload: dict[str, Any] | None = None,
    design_payload: dict[str, Any] | None = None,
    case_dir: Path | None = None,
) -> dict[str, Any]:
    if not generated_path.exists() or not gold_path.exists():
        return {
            "label": "xxcs",
            "generated": str(generated_path),
            "gold": str(gold_path),
            "error": "missing document",
        }

    from document_ai.validation.validation_report import score_document, score_plan_xxcs
    from document_ai.form_fill.security_execution import (
        compute_execution_metrics,
        load_security_test_results,
    )
    from document_ai.form_fill.security_execution_review import (
        compute_review_metrics,
        load_selected_security_results,
    )
    from document_ai.learn.extract_security_tests import load_security_tests
    from document_ai.validation.xxcs_compare import compare_xxcs

    metrics = compare_xxcs(
        generated_path,
        gold_path,
        requirements_payload=requirements_payload,
        design_payload=design_payload,
    )
    execution_state: dict[str, Any] = {"has_execution_overlay": False}
    if case_dir:
        plan_path = case_dir / "security_tests.json"
        overlay = load_security_test_results(case_dir)
        selected = load_selected_security_results(case_dir)
        if plan_path.exists():
            plan_tests = load_security_tests(plan_path).get("tests") or []
            exec_metrics = compute_execution_metrics(plan_tests, overlay)
            review_metrics = compute_review_metrics(plan_tests, overlay, selected)
            metrics.update(exec_metrics)
            metrics.update(review_metrics)
            execution_state = {
                "has_execution_overlay": bool(overlay),
                "accepted_execution_id": (overlay or {}).get("accepted_execution_id"),
                "execution_count": len((overlay or {}).get("executions") or []),
                "import_warning_count": len((overlay or {}).get("warnings") or []),
                "final_report_readiness": review_metrics.get("final_report_readiness"),
                "gold_type": "plan",
            }
    plan_score = score_plan_xxcs(metrics)
    metrics["plan_score"] = round(plan_score, 1)
    metrics["execution_import_score"] = round(
        100.0
        * (
            0.5 * float(metrics.get("real_execution_coverage") or 0.0)
            + 0.5 * float(metrics.get("reviewer_verified_execution_coverage") or 0.0)
        ),
        1,
    )
    # Document-level XXCS score remains plan-oriented so imports do not fail plan gold validation
    score = plan_score
    return {
        "label": "xxcs",
        "generated": str(generated_path),
        "gold": str(gold_path),
        "score": round(score, 1),
        "plan_score": round(plan_score, 1),
        "metrics": metrics,
        "execution_state": execution_state,
    }


def run_document_validation(
    case_dir: Path,
    *,
    gold_mdsr: Path | None = None,
    gold_mddr: Path | None = None,
    gold_fields_path: Path | None = None,
    report_md_path: Path | None = None,
    report_json_path: Path | None = None,
    human_review_path: Path | None = None,
) -> dict[str, Any]:
    from document_ai.eval.gold_dataset import resolve_independent_gold
    from document_ai.eval.gold_fields import compare_against_gold_fields, load_gold_fields
    from document_ai.eval.human_review import write_human_review_checklist

    case_dir = case_dir.resolve()
    input_path = case_dir / "input.json"
    payload = json.loads(input_path.read_text(encoding="utf-8")) if input_path.exists() else {}
    domain = payload.get("domain", "")
    product_name = payload.get("product_name") or (payload.get("facts") or {}).get("product_name", "")
    case_id = payload.get("case_id") or case_dir.name

    gen_mdsr = case_dir / "output_mdsr.docx"
    gen_mddr = case_dir / "output_mddr.docx"
    gen_xxcs = case_dir / "output_xxcs.docx"

    independent = resolve_independent_gold(case_id)
    if gold_mdsr is None and independent.get("mdsr"):
        gold_mdsr = independent["mdsr"]  # type: ignore[assignment]
    if gold_mddr is None and independent.get("mddr"):
        gold_mddr = independent["mddr"]  # type: ignore[assignment]
    if gold_fields_path is None and independent.get("fields"):
        gold_fields_path = independent["fields"]  # type: ignore[assignment]
    gold_xxcs = independent.get("xxcs")

    # Case-local gold still supported
    if gold_mdsr is None:
        local = _default_gold_path(case_dir, "gold_mdsr.docx")
        gold_mdsr = local if local.exists() else local
    if gold_mddr is None:
        local = _default_gold_path(case_dir, "gold_mddr.docx")
        gold_mddr = local if local.exists() else local
    if gold_xxcs is None:
        local = _default_gold_path(case_dir, "gold_xxcs.docx")
        gold_xxcs = local if local.exists() else None

    gold_mdsr = Path(gold_mdsr).resolve()
    gold_mddr = Path(gold_mddr).resolve()
    if gold_xxcs:
        gold_xxcs = Path(gold_xxcs).resolve()

    req_payload = {}
    design_payload = {}
    if (case_dir / "requirements.json").exists():
        req_payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    if (case_dir / "design_items.json").exists():
        design_payload = json.loads((case_dir / "design_items.json").read_text(encoding="utf-8"))

    mdsr_result: dict[str, Any] = {}
    mddr_result: dict[str, Any] = {}
    xxcs_result: dict[str, Any] = {}
    if gold_mdsr.exists() and gen_mdsr.exists():
        mdsr_result = validate_mdsr(gen_mdsr, gold_mdsr, domain=domain)
    if gold_mddr.exists() and gen_mddr.exists():
        mddr_result = validate_mddr(gen_mddr, gold_mddr, domain=domain)
    if gold_xxcs and gold_xxcs.exists() and gen_xxcs.exists():
        xxcs_result = validate_xxcs(
            gen_xxcs,
            gold_xxcs,
            requirements_payload=req_payload,
            design_payload=design_payload,
            case_dir=case_dir,
        )

    scores_list = [
        r["score"]
        for r in (mdsr_result, mddr_result, xxcs_result)
        if r and "score" in r
    ]
    docx_overall = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0.0

    errors: list[str] = []
    if not gen_mdsr.exists():
        errors.append(f"missing generated MDSR: {gen_mdsr}")
    if not gen_mddr.exists():
        errors.append(f"missing generated MDDR: {gen_mddr}")
    if not gold_mdsr.exists():
        errors.append(f"missing gold MDSR: {gold_mdsr}")
    if not gold_mddr.exists():
        errors.append(f"missing gold MDDR: {gold_mddr}")

    aggregate_metrics: dict[str, Any] = {}
    for part in (mdsr_result, mddr_result, xxcs_result):
        metrics = part.get("metrics") or {}
        for key, value in metrics.items():
            if key not in aggregate_metrics:
                aggregate_metrics[key] = value
            elif isinstance(value, (int, float)) and isinstance(aggregate_metrics[key], (int, float)):
                aggregate_metrics[key] = round((aggregate_metrics[key] + value) / 2, 3)

    high_risk: list[dict[str, Any]] = []
    for part in (mdsr_result, mddr_result, xxcs_result):
        metrics = part.get("metrics") or {}
        high_risk.extend(metrics.get("high_risk", []))
        for sub in ("requirements", "traceability", "design_blocks"):
            high_risk.extend((part.get(sub) or {}).get("high_risk", []))
        if part.get("label") == "xxcs" and part.get("metrics", {}).get("missing_in_generated"):
            for rid in part["metrics"]["missing_in_generated"][:10]:
                high_risk.append(
                    {
                        "req_id": rid,
                        "kind": "missing_security_id",
                        "detail": "Gold security ID missing from generated XXCS",
                    }
                )

    semantic: dict[str, Any] = {}
    fields_path = Path(gold_fields_path).resolve() if gold_fields_path else None
    if fields_path and fields_path.exists():
        gold_fields = load_gold_fields(fields_path)
        semantic = compare_against_gold_fields(
            generated_mdsr=gen_mdsr if gen_mdsr.exists() else None,
            generated_mddr=gen_mddr if gen_mddr.exists() else None,
            gold_fields=gold_fields,
        )
        aggregate_metrics.update(
            {
                k: v
                for k, v in semantic.items()
                if k.startswith("semantic_") and isinstance(v, (int, float))
            }
        )

    # Blend DOCX validation with semantic gold_fields when available
    if semantic and scores_list:
        overall = round(0.85 * docx_overall + 0.15 * float(semantic.get("semantic_overall", docx_overall)), 1)
    else:
        overall = docx_overall

    result: dict[str, Any] = {
        "case": str(case_dir),
        "case_id": case_id,
        "domain": domain,
        "product_name": product_name,
        "status": score_status(overall) if scores_list or semantic else "FAIL",
        "scores": {
            "overall": overall,
            "docx_overall": docx_overall,
            "mdsr": mdsr_result.get("score", 0.0),
            "mddr": mddr_result.get("score", 0.0),
            "xxcs": xxcs_result.get("score"),
            "semantic": semantic.get("semantic_overall"),
        },
        "metrics": aggregate_metrics,
        "mdsr": mdsr_result,
        "mddr": mddr_result,
        "xxcs": xxcs_result,
        "semantic": semantic,
        "high_risk_differences": high_risk[:40],
        "generated_paths": {
            "mdsr": str(gen_mdsr),
            "mddr": str(gen_mddr),
            "xxcs": str(gen_xxcs) if gen_xxcs.exists() else None,
        },
        "gold_paths": {
            "mdsr": str(gold_mdsr),
            "mddr": str(gold_mddr),
            "xxcs": str(gold_xxcs) if gold_xxcs else None,
            "fields": str(fields_path) if fields_path and fields_path.exists() else None,
        },
    }
    if errors:
        result["errors"] = errors
    result["human_review_checklist"] = human_review_checklist(result)

    md_path = report_md_path or case_dir / "validation_report.md"
    json_path = report_json_path or case_dir / "validation_report.json"
    checklist_path = human_review_path or case_dir / "human_review_checklist.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_validation_report(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_human_review_checklist(result, checklist_path)
    result["report_paths"] = {
        "markdown": str(md_path),
        "json": str(json_path),
        "human_review_checklist": str(checklist_path),
    }
    return result
