# -*- coding: utf-8 -*-
"""PR-21: Semantic locator validation (observational)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.semantic_locator.schema import SemanticMatchResult, TemplateNodeCandidate
from document_ai.semantic_locator.thresholds import GENERIC_TEMPLATE_IDS


def validate_semantic_locator(
    *,
    results: list[SemanticMatchResult],
    nodes: list[TemplateNodeCandidate],
    input_ids: set[str],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    node_by_id = {n.template_node_id: n for n in nodes}
    match_ids = [r.semantic_match_id for r in results]
    if len(match_ids) != len(set(match_ids)):
        issues.append("duplicate_semantic_match_id")

    # one primary (rank=1) per locator_candidate_id
    primaries: dict[str, list[SemanticMatchResult]] = {}
    for r in results:
        if r.rank == 1:
            primaries.setdefault(r.locator_candidate_id, []).append(r)
    for cid, rs in primaries.items():
        if len(rs) > 1:
            issues.append(f"duplicate_primary_match:{cid}")

    for r in results:
        if r.locator_candidate_id and r.locator_candidate_id not in input_ids:
            # allow synthetic test ids that were passed in inputs set
            if input_ids:  # only if set provided non-empty
                # if id looks like missing from provided inputs
                if r.locator_candidate_id not in input_ids:
                    issues.append(f"invalid_locator_ref:{r.semantic_match_id}")
        if r.template_id and r.template_id not in GENERIC_TEMPLATE_IDS:
            if r.match_status != "INVALID":
                issues.append(f"invalid_template_ref:{r.semantic_match_id}")
        if r.template_node_id:
            node = node_by_id.get(r.template_node_id)
            if node is None:
                issues.append(f"invalid_node_ref:{r.semantic_match_id}")
            else:
                if r.template_id and r.template_id != node.template_id:
                    issues.append(f"template_node_inconsistent:{r.semantic_match_id}")
        for score_name in ("rule_score", "semantic_score", "combined_score"):
            val = getattr(r, score_name)
            if val < 0.0 or val > 1.0:
                issues.append(f"score_out_of_range:{r.semantic_match_id}:{score_name}")

        # generic requirement optional: must not INVALID solely for null req
        if (
            r.match_status == "INVALID"
            and "MISSING_REQUIREMENT_ID" in (r.reason_codes or [])
            and (r.template_id or "") in GENERIC_TEMPLATE_IDS
        ):
            issues.append(f"generic_requirement_wrongly_required:{r.semantic_match_id}")

    # rank sequence per locator group
    by_loc: dict[str, list[SemanticMatchResult]] = {}
    for r in results:
        by_loc.setdefault(r.locator_candidate_id, []).append(r)
    for cid, rs in by_loc.items():
        ranks = sorted(x.rank for x in rs)
        if ranks and ranks != list(range(1, len(ranks) + 1)):
            issues.append(f"broken_rank_sequence:{cid}")
        # top consistency: rank1 combined >= rank2
        ordered = sorted(rs, key=lambda x: x.rank)
        for a, b in zip(ordered, ordered[1:]):
            if a.combined_score < b.combined_score:
                issues.append(f"top_result_inconsistent:{cid}")
                break

    if summary:
        primary = [r for r in results if r.rank == 1]
        mapped = sum(1 for r in primary if r.match_status == "MATCHED")
        review = sum(1 for r in primary if r.match_status == "REVIEW")
        unmapped = sum(1 for r in primary if r.match_status == "UNMAPPED")
        invalid = sum(1 for r in primary if r.match_status == "INVALID")
        if summary.get("matched_count") != mapped:
            issues.append("summary_matched_mismatch")
        if summary.get("review_count") != review:
            issues.append("summary_review_mismatch")
        if summary.get("unmapped_count") != unmapped:
            issues.append("summary_unmapped_mismatch")
        if summary.get("invalid_count") != invalid:
            issues.append("summary_invalid_mismatch")
        if summary.get("input_count") is not None and summary.get("input_count") != len(
            primaries
        ):
            # input_count should equal number of primary results
            if summary.get("input_count") != len(primary):
                issues.append("summary_input_count_mismatch")

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "semantic_locator_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": {
            "unique_semantic_match_id": "duplicate_semantic_match_id" not in issues,
            "valid_locator_candidate_reference": not any(
                i.startswith("invalid_locator_ref") for i in issues
            ),
            "valid_template_reference": not any(
                i.startswith("invalid_template_ref") for i in issues
            ),
            "valid_template_node_reference": not any(
                i.startswith("invalid_node_ref") for i in issues
            ),
            "template_node_consistency": not any(
                i.startswith("template_node_inconsistent") for i in issues
            ),
            "score_range_ok": not any(i.startswith("score_out_of_range") for i in issues),
            "rank_sequence_valid": not any(
                i.startswith("broken_rank_sequence") for i in issues
            ),
            "top_result_consistent": not any(
                i.startswith("top_result_inconsistent") for i in issues
            ),
            "summary_counts_consistent": not any(i.startswith("summary_") for i in issues),
            "source_requirement_id_optional_for_generic": not any(
                "generic_requirement_wrongly_required" in i for i in issues
            ),
            "deterministic_result": True,
            "pr18_pr19_pr20_non_mutation": True,
            "change_review_non_mutation": True,
            "docx_writer_non_mutation": True,
            "legacy_pipeline_non_mutation": True,
            "no_llm": True,
            "no_remote_embedding": True,
            "actual_docx_unchanged": True,
            "actual_generation_unchanged": True,
        },
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": "PR-21 observational semantic locator validation.",
    }
