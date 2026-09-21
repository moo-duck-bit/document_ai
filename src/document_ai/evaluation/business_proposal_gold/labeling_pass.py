# -*- coding: utf-8 -*-
"""Pass1 / Pass2 independent labeling passes + disagreement detection.

Both passes call the SAME deterministic policy function
(``policy.classify_case``) but Pass2 re-derives the document inventory
independently (re-parses the DOCX) rather than reusing Pass1's in-memory
result, so a real regression in either the inventory scan or the policy
function would surface as a disagreement rather than being silently masked
by a shared cache.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from document_ai.evaluation.business_proposal_gold.document_inventory import inventory_document
from document_ai.evaluation.business_proposal_gold.policy import classify_case
from document_ai.evaluation.business_proposal_gold.schema import BusinessProposalGoldRow

PASS1_LABELER = "pass1_structure_policy"
PASS2_LABELER = "pass2_independent_review"


def label_case(
    *,
    case: dict[str, Any],
    docx_path: str | Path,
    labeled_by: str,
    review_note: str | None = None,
) -> BusinessProposalGoldRow:
    """Label one case from scratch: re-read the DOCX + re-run the policy."""
    document_id = (case.get("enabled_documents") or [None])[0] or Path(docx_path).stem.upper()
    inventory = inventory_document(docx_path, document_id=document_id)
    row = classify_case(
        case_id=case["case_id"],
        document_id=document_id,
        change_request=case.get("change_request") or "",
        tags=case.get("tags") or [],
        inventory=inventory,
    )
    row = replace(row, labeled_by=labeled_by)
    if review_note:
        row = replace(row, label_rationale=f"{row.label_rationale} [review_note: {review_note}]")
    return row


def run_pass1(cases: list[dict[str, Any]], *, fixtures_root: Path) -> list[BusinessProposalGoldRow]:
    rows = []
    for case in cases:
        docx_path = resolve_fixture(case, fixtures_root)
        rows.append(label_case(case=case, docx_path=docx_path, labeled_by=PASS1_LABELER))
    return rows


def run_pass2(cases: list[dict[str, Any]], *, fixtures_root: Path) -> list[BusinessProposalGoldRow]:
    """Independent second pass: re-derive from inventory again (no shared state)."""
    rows = []
    for case in cases:
        docx_path = resolve_fixture(case, fixtures_root)
        rows.append(label_case(case=case, docx_path=docx_path, labeled_by=PASS2_LABELER))
    return rows


def resolve_fixture(case: dict[str, Any], fixtures_root: Path) -> Path:
    docs = case.get("input_documents") or []
    if not docs:
        raise ValueError(f"case {case.get('case_id')} has no input_documents")
    rel = docs[0]["path"]
    p = Path(rel)
    if p.is_file():
        return p
    # rel is usually "fixtures/business_proposal/xxx.docx" relative to the benchmark root
    candidate = fixtures_root.parent / rel
    if candidate.is_file():
        return candidate
    candidate2 = fixtures_root / Path(rel).name
    if candidate2.is_file():
        return candidate2
    raise FileNotFoundError(f"fixture not found for case {case.get('case_id')}: {rel}")


def _row_disagreement_fields(row: BusinessProposalGoldRow) -> dict[str, Any]:
    ref = row.primary_reference or {}
    return {
        "node_evaluation_mode": row.node_evaluation_mode,
        "primary_template_node_id": ref.get("template_node_id"),
        "primary_document_node_id": ref.get("document_node_id"),
        "acceptable_groups": sorted(tuple(sorted(g)) for g in (row.acceptable_groups or [])),
        "expected_physical_node_type": row.expected_physical_node_type,
        "expected_operation": row.expected_operation,
    }


def detect_disagreements(
    pass1_rows: list[BusinessProposalGoldRow],
    pass2_rows: list[BusinessProposalGoldRow],
) -> list[dict[str, Any]]:
    """Compare pass1 vs pass2 on substantive fields (ignoring labeled_by/labeled_at/rationale text)."""
    by1 = {r.case_id: r for r in pass1_rows}
    by2 = {r.case_id: r for r in pass2_rows}
    disagreements: list[dict[str, Any]] = []
    for case_id in sorted(set(by1) | set(by2)):
        r1 = by1.get(case_id)
        r2 = by2.get(case_id)
        if r1 is None or r2 is None:
            disagreements.append({"case_id": case_id, "issue": "MISSING_IN_ONE_PASS"})
            continue
        f1 = _row_disagreement_fields(r1)
        f2 = _row_disagreement_fields(r2)
        if f1 != f2:
            disagreements.append({"case_id": case_id, "pass1": f1, "pass2": f2, "issue": "FIELD_MISMATCH"})
    return disagreements


def agreement_metrics(
    pass1_rows: list[BusinessProposalGoldRow],
    pass2_rows: list[BusinessProposalGoldRow],
) -> dict[str, Any]:
    """Raw agreement, mode agreement, reference agreement between pass1/pass2."""
    by1 = {r.case_id: r for r in pass1_rows}
    by2 = {r.case_id: r for r in pass2_rows}
    common = sorted(set(by1) & set(by2))
    n = len(common) or 1

    mode_agree = 0
    ref_agree = 0
    raw_agree = 0
    for cid in common:
        r1, r2 = by1[cid], by2[cid]
        f1, f2 = _row_disagreement_fields(r1), _row_disagreement_fields(r2)
        if f1["node_evaluation_mode"] == f2["node_evaluation_mode"]:
            mode_agree += 1
        if (
            f1["primary_template_node_id"] == f2["primary_template_node_id"]
            and f1["primary_document_node_id"] == f2["primary_document_node_id"]
        ):
            ref_agree += 1
        if f1 == f2:
            raw_agree += 1
    return {
        "n_common_cases": len(common),
        "raw_agreement_rate": raw_agree / n,
        "mode_agreement_rate": mode_agree / n,
        "reference_agreement_rate": ref_agree / n,
    }
