"""Validation score calculation and markdown/JSON report rendering."""

from __future__ import annotations

from typing import Any


def score_status(score: float) -> str:
    if score >= 85:
        return "PASS"
    if score >= 70:
        return "WARNING"
    return "FAIL"


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def score_document(metrics: dict[str, Any]) -> float:
    """Compute 0–100 score for one document comparison."""
    weights = {
        "section_coverage": 0.12,
        "paragraph_similarity": 0.18,
        "requirement_count_match": 0.08,
        "requirement_text_similarity": 0.18,
        "requirement_completeness": 0.12,
        "design_block_coverage": 0.12,
        "traceability_coverage": 0.12,
        "traceability_row_match": 0.08,
        # XXCS (used when present)
        "security_coverage": 0.20,
        "linked_requirement_coverage": 0.15,
        "linked_design_coverage": 0.15,
        "test_item_completeness": 0.15,
        "test_text_similarity": 0.15,
        "security_id_count_match": 0.10,
    }

    total_weight = 0.0
    weighted = 0.0
    for key, weight in weights.items():
        value = metrics.get(key)
        if value is None:
            continue
        total_weight += weight
        weighted += float(value) * weight

    base = (weighted / total_weight * 100.0) if total_weight else 0.0
    placeholder_penalty = min(20.0, metrics.get("residual_placeholder_count", 0) * 4)
    domain_penalty = min(15.0, metrics.get("domain_mismatch_count", 0) * 3)
    high_risk_penalty = min(15.0, len(metrics.get("high_risk", [])) * 2)
    return _clamp(base - placeholder_penalty - domain_penalty - high_risk_penalty)


def score_plan_xxcs(metrics: dict[str, Any]) -> float:
    """
    Plan-gold XXCS score.

    When generated XXCS includes imported execution actuals, do not penalize
    plan validation via test_text_similarity against plan-only gold. Prefer
    plan_test_completeness over mixed test_item_completeness.
    """
    plan_metrics = dict(metrics)
    if plan_metrics.get("plan_test_completeness") is not None:
        plan_metrics["test_item_completeness"] = plan_metrics["plan_test_completeness"]
    has_execution = bool(
        plan_metrics.get("executed_test_count")
        or plan_metrics.get("synthetic_execution_count")
        or plan_metrics.get("execution_coverage")
    )
    if has_execution:
        plan_metrics.pop("test_text_similarity", None)
    return score_document(plan_metrics)


def merge_metrics(*parts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    high_risk: list[dict[str, Any]] = []
    for part in parts:
        for key, value in part.items():
            if key == "high_risk":
                high_risk.extend(value)
            elif key not in merged:
                merged[key] = value
    if high_risk:
        merged["high_risk"] = high_risk
    return merged


def human_review_checklist(result: dict[str, Any]) -> list[str]:
    checklist: list[str] = []
    scores = result.get("scores", {})
    if scores.get("mdsr", 0) < 85:
        checklist.append("Review MDSR section gaps and requirement text differences vs gold.")
    if scores.get("mddr", 0) < 85:
        checklist.append("Review MDDR design blocks and paragraph differences vs gold.")
    if result.get("metrics", {}).get("residual_placeholder_count", 0):
        checklist.append("Replace remaining XX-XX-XXXX or placeholder tokens in generated documents.")
    if result.get("metrics", {}).get("domain_mismatch_count", 0):
        checklist.append("Scan generated text for foreign domain terminology.")
    for item in result.get("high_risk_differences", [])[:8]:
        detail = item.get("detail") or item.get("kind", "")
        req = item.get("req_id") or item.get("requirement", "")
        label = f"{req}: " if req else ""
        checklist.append(f"High-risk diff — {label}{detail}")
    xxcs = result.get("xxcs") or {}
    exec_state = xxcs.get("execution_state") or {}
    exec_metrics = (xxcs.get("metrics") or {}) if xxcs else {}
    if exec_state.get("has_execution_overlay"):
        checklist.append(
            "Verify imported security test statuses match actual evidence (PASS/FAIL/REVIEW_REQUIRED)."
        )
        checklist.append(
            "Confirm PASS/FAIL judgments have sufficient justification and reviewer can approve imported results."
        )
        if exec_metrics.get("unresolved_review_required_count", 0):
            checklist.append(
                f"Resolve {exec_metrics['unresolved_review_required_count']} REVIEW_REQUIRED execution result(s)."
            )
        if exec_state.get("import_warning_count", 0):
            checklist.append(
                f"Review {exec_state['import_warning_count']} execution import warning(s) (missing evidence, etc.)."
            )
        checklist.append(
            "Confirm sensitive data or large logs were not copied verbatim into the XXCS DOCX."
        )
    if not checklist:
        checklist.append("No critical validation gaps flagged; spot-check product overview and traceability links.")
    return checklist


def render_validation_report(result: dict[str, Any]) -> str:
    scores = result.get("scores", {})
    overall = scores.get("overall", 0)
    status = result.get("status", score_status(overall))
    metrics = result.get("metrics", {})
    mdsr = result.get("mdsr", {})
    mddr = result.get("mddr", {})

    lines = [
        f"# Document Validation Report — {result.get('case', '')}",
        "",
        f"**Overall:** {status} ({overall}/100)",
        "",
        f"**Product:** {result.get('product_name', '')} | **Domain:** {result.get('domain', '')}",
        "",
        "## Scores",
        "",
        "| Document | Score | Status |",
        "|----------|------:|--------|",
        f"| MDSR | {scores.get('mdsr', 0)} | {score_status(scores.get('mdsr', 0) or 0)} |",
        f"| MDDR | {scores.get('mddr', 0)} | {score_status(scores.get('mddr', 0) or 0)} |",
    ]
    if scores.get("xxcs") is not None:
        lines.append(
            f"| XXCS | {scores.get('xxcs')} | {score_status(scores.get('xxcs') or 0)} |"
        )
    lines.extend(
        [
        f"| **Overall** | **{overall}** | **{status}** |",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        ]
    )

    metric_labels = [
        ("section_coverage", "Section coverage"),
        ("paragraph_similarity", "Paragraph similarity"),
        ("requirement_count_match", "Requirement count match"),
        ("requirement_text_similarity", "Requirement text similarity"),
        ("requirement_completeness", "Requirement purpose/criteria completeness"),
        ("design_block_coverage", "Design block coverage"),
        ("traceability_coverage", "Traceability coverage"),
        ("traceability_row_match", "Traceability row match"),
        ("residual_placeholder_count", "Residual placeholder count"),
        ("domain_mismatch_count", "Domain mismatch count"),
        ("security_coverage", "XXCS security ID coverage"),
        ("linked_requirement_coverage", "XXCS linked requirement coverage"),
        ("linked_design_coverage", "XXCS linked design coverage"),
        ("test_item_completeness", "XXCS test item completeness"),
        ("test_method_completeness", "XXCS test method completeness"),
        ("procedure_completeness", "XXCS procedure completeness"),
        ("expected_result_completeness", "XXCS expected result completeness"),
        ("actual_result_completeness", "XXCS actual result completeness"),
        ("satisfaction_completeness", "XXCS satisfaction completeness"),
        ("evidence_completeness", "XXCS evidence completeness"),
        ("plan_test_completeness", "XXCS plan field completeness"),
        ("execution_test_completeness", "XXCS execution field completeness"),
        ("execution_coverage", "Security test execution coverage"),
        ("evidence_coverage", "Security test evidence coverage"),
        ("executed_result_completeness", "Executed result completeness"),
        ("pass_with_evidence_ratio", "PASS with evidence ratio"),
        ("fail_with_evidence_ratio", "FAIL with evidence ratio"),
        ("unresolved_review_required_count", "Unresolved REVIEW_REQUIRED count"),
        ("stale_execution_count", "Stale execution history count"),
        ("execution_readiness", "Execution readiness (informational)"),
        ("plan_score", "XXCS plan score"),
        ("execution_import_score", "XXCS execution import score (informational)"),
        ("reviewer_verified_execution_coverage", "Reviewer-verified execution coverage"),
        ("selected_result_coverage", "Selected-for-report coverage"),
        ("verified_evidence_coverage", "Verified evidence coverage"),
        ("unresolved_review_count", "Unresolved review count"),
        ("synthetic_result_count", "Synthetic result count"),
        ("real_execution_count", "Real execution count"),
        ("real_execution_coverage", "Real execution coverage (excludes synthetic)"),
        ("final_report_readiness", "Final report readiness"),
        ("final_report_readiness_score", "Final report readiness score"),
    ]
    for key, label in metric_labels:
        if key in metrics:
            value = metrics[key]
            if isinstance(value, float) and key.endswith(("coverage", "similarity", "match", "completeness")):
                lines.append(f"| {label} | {value:.1%} |" if value <= 1 else f"| {label} | {value} |")
            else:
                lines.append(f"| {label} | {value} |")

    lines.extend(["", "## Section-level Comparison", ""])
    section = mdsr.get("sections") or mddr.get("sections") or {}
    if section:
        lines.append(
            f"- Gold sections: {section.get('gold_section_count', 0)} | "
            f"Generated: {section.get('generated_section_count', 0)} | "
            f"Matched: {section.get('matched_section_count', 0)}"
        )
        if section.get("missing_in_generated"):
            lines.append("- Missing in generated:")
            for item in section["missing_in_generated"][:8]:
                lines.append(f"  - {item}")
        if section.get("extra_in_generated"):
            lines.append("- Extra in generated:")
            for item in section["extra_in_generated"][:8]:
                lines.append(f"  - {item}")
    else:
        lines.append("- No section comparison data.")

    lines.extend(["", "## Requirement-level Comparison", ""])
    req = mdsr.get("requirements") or {}
    if req:
        lines.append(
            f"- Gold reqs: {req.get('gold_requirement_count', 0)} | "
            f"Generated: {req.get('generated_requirement_count', 0)} | "
            f"Text similarity: {req.get('requirement_text_similarity', 0):.1%}"
        )
        if req.get("missing_in_generated"):
            lines.append(f"- Missing in generated: {', '.join(req['missing_in_generated'][:10])}")
        if req.get("extra_in_generated"):
            lines.append(f"- Extra in generated: {', '.join(req['extra_in_generated'][:10])}")
    else:
        lines.append("- No requirement comparison data.")

    lines.extend(["", "## Traceability Comparison", ""])
    trace = mdsr.get("traceability") or {}
    if trace:
        lines.append(
            f"- Generated coverage: {trace.get('traceability_coverage', 0):.1%} | "
            f"Row match vs gold: {trace.get('traceability_row_match', 0):.1%}"
        )
        if trace.get("linked_req_mismatches"):
            lines.append("- Linked-req mismatches:")
            for item in trace["linked_req_mismatches"][:6]:
                lines.append(
                    f"  - {item['requirement']}: gold=`{item.get('gold_linked_reqs', '')[:60]}` "
                    f"gen=`{item.get('generated_linked_reqs', '')[:60]}`"
                )
    else:
        lines.append("- No traceability comparison data.")

    semantic = result.get("semantic") or {}
    if semantic:
        lines.extend(
            [
                "",
                "## Semantic Validation (gold_fields)",
                "",
                f"- Semantic overall: {semantic.get('semantic_overall', '-')}",
                f"- Requirement ID coverage: {semantic.get('semantic_requirement_id_coverage', '-')}",
                f"- Design ID coverage: {semantic.get('semantic_design_id_coverage', '-')}",
                f"- Traceability coverage: {semantic.get('semantic_traceability_coverage', '-')}",
                f"- Product name match: {semantic.get('semantic_product_name_match', '-')}",
            ]
        )

    lines.extend(["", "## High-risk Differences", ""])
    high_risk = result.get("high_risk_differences", [])
    if high_risk:
        for item in high_risk[:15]:
            req = item.get("req_id") or item.get("requirement", "")
            kind = item.get("kind", "diff")
            detail = item.get("detail", "")
            prefix = f"**{req}** " if req else ""
            lines.append(f"- {prefix}[{kind}] {detail}")
    else:
        lines.append("- None flagged.")

    lines.extend(["", "## Human Review Checklist", ""])
    for item in result.get("human_review_checklist", []):
        lines.append(f"- [ ] {item}")

    lines.extend(["", "## Document Paths", ""])
    if result.get("errors"):
        lines.extend(["", "## Errors", ""])
        for err in result["errors"]:
            lines.append(f"- {err}")

    for label in ("mdsr", "mddr"):
        doc = result.get(label, {})
        if doc.get("generated") or doc.get("gold"):
            lines.append(f"- **{label.upper()}** generated: `{doc.get('generated', '')}`")
            lines.append(f"- **{label.upper()}** gold: `{doc.get('gold', '')}`")

    return "\n".join(lines) + "\n"
