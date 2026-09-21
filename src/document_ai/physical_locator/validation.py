# -*- coding: utf-8 -*-
"""PR-23: Physical locator validation (observational)."""

from __future__ import annotations

from typing import Any

from document_ai.physical_locator.schema import (
    LOCATION_TYPES,
    PhysicalLocationCandidate,
    PrimaryPhysicalLocation,
)

SPAN_KINDS = frozenset(
    {"ESTIMATED_BLOCK_LOCAL", "SOURCE_ABSOLUTE", "OOXML_LOCAL", "NONE"}
)


def validate_physical_locator(
    *,
    candidates: list[PhysicalLocationCandidate],
    primaries: list[PrimaryPhysicalLocation],
    input_target_ids: set[str],
    known_document_ids: set[str],
    summary: dict[str, Any] | None = None,
    external_activation_flag: bool = False,
    artifact_candidates: list[PhysicalLocationCandidate] | None = None,
) -> dict[str, Any]:
    """Validate using full ranked candidates; artifact Top-K is checked separately."""
    issues: list[str] = []
    warnings: list[str] = []

    cids = [c.physical_candidate_id for c in candidates]
    if len(cids) != len(set(cids)):
        issues.append("duplicate_physical_candidate_id")

    pids = [p.primary_location_id for p in primaries]
    if len(pids) != len(set(pids)):
        issues.append("duplicate_primary_location_id")

    cand_by_id = {c.physical_candidate_id: c for c in candidates}
    by_target: dict[str, list[PhysicalLocationCandidate]] = {}
    for c in candidates:
        by_target.setdefault(c.patch_target_candidate_id, []).append(c)

    for c in candidates:
        if c.patch_target_candidate_id not in input_target_ids:
            issues.append(f"invalid_patch_target:{c.physical_candidate_id}")
        if c.document_id and known_document_ids and c.document_id not in known_document_ids:
            issues.append(f"invalid_document:{c.physical_candidate_id}")
        if c.location_type not in LOCATION_TYPES:
            issues.append(f"invalid_location_type:{c.physical_candidate_id}")
        if c.location_score < 0.0 or c.location_score > 1.0:
            issues.append(f"score_out_of_range:{c.physical_candidate_id}")
        if c.span_kind not in SPAN_KINDS:
            issues.append(f"invalid_span_kind:{c.physical_candidate_id}")
        if c.character_span is not None and c.span_kind == "NONE":
            warnings.append(f"span_without_kind:{c.physical_candidate_id}")
        if (
            c.location_type == "TABLE_CELL"
            and c.character_span is not None
            and c.span_kind != "ESTIMATED_BLOCK_LOCAL"
            and c.span_kind != "NONE"
        ):
            warnings.append(f"table_cell_span_not_block_local:{c.physical_candidate_id}")

    primary_targets = [p.patch_target_candidate_id for p in primaries]
    if len(primary_targets) != len(set(primary_targets)):
        issues.append("duplicate_primary_per_target")

    artifact_by_target: dict[str, list[PhysicalLocationCandidate]] = {}
    if artifact_candidates is not None:
        for c in artifact_candidates:
            artifact_by_target.setdefault(c.patch_target_candidate_id, []).append(c)

    for p in primaries:
        if p.patch_target_candidate_id not in input_target_ids:
            issues.append(f"primary_unknown_target:{p.primary_location_id}")
        if p.actual_docx_changed or p.actual_writer_called or p.actual_patch_created:
            issues.append(f"actual_mutation_true:{p.primary_location_id}")
        if p.location_status in ("RESOLVED", "REVIEW"):
            if not p.physical_candidate_id:
                issues.append(f"primary_missing_candidate:{p.primary_location_id}")
            elif p.physical_candidate_id not in cand_by_id:
                issues.append(f"primary_candidate_missing:{p.primary_location_id}")
            else:
                top = cand_by_id[p.physical_candidate_id]
                group = sorted(
                    by_target.get(p.patch_target_candidate_id, []),
                    key=lambda x: x.rank,
                )
                if group and group[0].physical_candidate_id != p.physical_candidate_id:
                    issues.append(f"top1_inconsistent:{p.primary_location_id}")
                if abs(top.location_score - p.location_score) > 1e-6:
                    issues.append(f"primary_score_mismatch:{p.primary_location_id}")
                if artifact_candidates is not None:
                    art_group = artifact_by_target.get(p.patch_target_candidate_id, [])
                    art_ids = {c.physical_candidate_id for c in art_group}
                    if p.physical_candidate_id not in art_ids:
                        issues.append(
                            f"primary_not_in_artifact_topk:{p.primary_location_id}"
                        )

        # ranking consistency within full group
        group = by_target.get(p.patch_target_candidate_id, [])
        ranks = sorted(c.rank for c in group)
        if ranks and ranks != list(range(1, len(ranks) + 1)):
            issues.append(f"broken_rank_sequence:{p.patch_target_candidate_id}")

    if summary:
        if summary.get("actual_docx_changed_count", 0) != 0:
            issues.append("summary_docx_nonzero")
        if summary.get("actual_writer_called_count", 0) != 0:
            issues.append("summary_writer_nonzero")
        if summary.get("actual_patch_created_count", 0) != 0:
            issues.append("summary_patch_nonzero")
        if summary.get("input_count") != len(primaries):
            issues.append("summary_input_mismatch")
        if summary.get("resolved_count") != sum(
            1 for p in primaries if p.location_status == "RESOLVED"
        ):
            issues.append("summary_resolved_mismatch")
        if summary.get("review_count") != sum(
            1 for p in primaries if p.location_status == "REVIEW"
        ):
            issues.append("summary_review_mismatch")
        if summary.get("unresolved_count") != sum(
            1 for p in primaries if p.location_status == "UNRESOLVED"
        ):
            issues.append("summary_unresolved_mismatch")
        if summary.get("invalid_count") != sum(
            1 for p in primaries if p.location_status == "INVALID"
        ):
            issues.append("summary_invalid_mismatch")
        if summary.get("full_candidate_count") is not None:
            if summary.get("full_candidate_count") != len(candidates):
                issues.append("summary_full_candidate_mismatch")
        if (
            artifact_candidates is not None
            and summary.get("artifact_candidate_count") is not None
        ):
            if summary.get("artifact_candidate_count") != len(artifact_candidates):
                issues.append("summary_artifact_candidate_mismatch")
        if summary.get("activation_allowed") is True:
            issues.append("summary_activation_allowed_true")
        if summary.get("observational_gate_forced_off") is False:
            issues.append("summary_observational_gate_not_forced")

    no_mutation = (
        not any("actual_mutation_true" in i for i in issues)
        and all(not p.actual_docx_changed for p in primaries)
        and all(not p.actual_writer_called for p in primaries)
        and all(not p.actual_patch_created for p in primaries)
        and (summary is None or summary.get("actual_docx_changed_count", 0) == 0)
        and (summary is None or summary.get("actual_writer_called_count", 0) == 0)
        and (summary is None or summary.get("actual_patch_created_count", 0) == 0)
    )
    observational_gate_ok = (
        (summary is None or summary.get("observational_gate_forced_off") is True)
        and (summary is None or summary.get("activation_allowed") is False)
        and no_mutation
    )
    # External flag may be ON; safety requires gate still blocks activation.
    activation_blocked = observational_gate_ok and no_mutation

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "physical_locator_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": {
            "unique_candidate_ids": "duplicate_physical_candidate_id" not in issues,
            "valid_patch_target": not any(
                i.startswith("invalid_patch_target") for i in issues
            ),
            "valid_document": not any(i.startswith("invalid_document") for i in issues),
            "ranking_consistency": not any(
                i.startswith("broken_rank_sequence") for i in issues
            ),
            "primary_exists": not any(
                i.startswith("primary_missing_candidate") for i in issues
            ),
            "top1_consistency": not any(
                i.startswith("top1_inconsistent") for i in issues
            ),
            "score_range_ok": not any(
                i.startswith("score_out_of_range") for i in issues
            ),
            "span_kind_valid": not any(
                i.startswith("invalid_span_kind") for i in issues
            ),
            "primary_in_artifact_topk": not any(
                i.startswith("primary_not_in_artifact_topk") for i in issues
            ),
            "summary_counts_consistent": not any(
                i.startswith("summary_") for i in issues
            ),
            "actual_docx_changed_false": all(
                not p.actual_docx_changed for p in primaries
            ),
            "actual_writer_called_false": all(
                not p.actual_writer_called for p in primaries
            ),
            "actual_patch_created_false": all(
                not p.actual_patch_created for p in primaries
            ),
            "observational_only": observational_gate_ok,
            "pr18_to_pr22_non_mutation": no_mutation,
            "external_activation_flag": external_activation_flag,
            "observational_gate_forced_off": True,
            "activation_allowed": False,
            "activation_blocked_despite_external_flag": activation_blocked,
            # Deprecated alias: flag OFF is NOT the sole safety condition.
            "feature_flag_off": (not external_activation_flag) and activation_blocked,
        },
        "external_activation_flag": external_activation_flag,
        "observational_gate_forced_off": True,
        "activation_allowed": False,
        "actual_docx_changed": False,
        "actual_writer_called": False,
        "actual_patch_created": False,
        "note": (
            "PR-23 observational physical locator validation. "
            "Validation uses full_candidates; artifact stores Top-K. "
            "character_span is ESTIMATED_BLOCK_LOCAL unless SOURCE_ABSOLUTE."
        ),
    }
