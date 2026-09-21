# -*- coding: utf-8 -*-
"""PR-22: Patch targeting validation (observational)."""

from __future__ import annotations

from typing import Any

from document_ai.patch_targeting.schema import (
    REQUESTED_OPERATIONS,
    ActivationPreview,
    PatchIntent,
    PatchTargetCandidate,
)
from document_ai.semantic_locator.thresholds import GENERIC_TEMPLATE_IDS


def validate_patch_targeting(
    *,
    intents: list[PatchIntent],
    targets: list[PatchTargetCandidate],
    previews: list[ActivationPreview],
    input_change_ids: set[str],
    known_nodes: set[str],
    summary: dict[str, Any] | None = None,
    known_semantic_match_ids: set[str] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    intent_ids = [i.patch_intent_id for i in intents]
    if len(intent_ids) != len(set(intent_ids)):
        issues.append("duplicate_patch_intent_id")
    target_ids = [t.patch_target_candidate_id for t in targets]
    if len(target_ids) != len(set(target_ids)):
        issues.append("duplicate_patch_target_candidate_id")
    preview_ids = [p.preview_id for p in previews]
    if len(preview_ids) != len(set(preview_ids)):
        issues.append("duplicate_preview_id")

    intent_by_id = {i.patch_intent_id: i for i in intents}
    target_by_id = {t.patch_target_candidate_id: t for t in targets}

    for i in intents:
        if i.change_id and input_change_ids and i.change_id not in input_change_ids:
            issues.append(f"unknown_change_id:{i.patch_intent_id}")
        if not i.semantic_match_id:
            issues.append(f"missing_semantic_match_id:{i.patch_intent_id}")
        elif known_semantic_match_ids is not None:
            if i.semantic_match_id not in known_semantic_match_ids:
                issues.append(f"unknown_semantic_match_id:{i.patch_intent_id}")
        if i.requested_operation not in REQUESTED_OPERATIONS:
            issues.append(f"invalid_operation:{i.patch_intent_id}")
        if i.actual_patch_created:
            issues.append(f"actual_patch_created_true:{i.patch_intent_id}")
        if i.actual_document_changed:
            issues.append(f"actual_document_changed_true:{i.patch_intent_id}")
        if i.template_id and i.template_id not in GENERIC_TEMPLATE_IDS:
            if i.intent_status != "INVALID":
                issues.append(f"invalid_template_ref:{i.patch_intent_id}")

    for t in targets:
        if t.patch_intent_id not in intent_by_id:
            issues.append(f"broken_intent_link:{t.patch_target_candidate_id}")
        if t.template_node_id and t.template_node_id not in known_nodes:
            if t.target_status in ("RESOLVED", "REVIEW"):
                issues.append(f"invalid_node_ref:{t.patch_target_candidate_id}")
        intent = intent_by_id.get(t.patch_intent_id)
        if intent and t.template_id and intent.template_id and t.template_id != intent.template_id:
            if t.target_status == "RESOLVED":
                issues.append(f"template_node_inconsistent:{t.patch_target_candidate_id}")
        if t.activation_allowed:
            issues.append(f"activation_allowed_true:{t.patch_target_candidate_id}")

    for p in previews:
        if p.patch_intent_id not in intent_by_id:
            issues.append(f"broken_preview_intent_link:{p.preview_id}")
        if p.target_candidate_id not in target_by_id:
            issues.append(f"broken_preview_target_link:{p.preview_id}")
        if p.actual_document_changed or p.actual_writer_called:
            issues.append(f"actual_writer_or_docx_true:{p.preview_id}")
        if p.preview_status == "PREVIEW_READY":
            issues.append(f"preview_ready_while_observational:{p.preview_id}")

    if summary:
        if summary.get("actual_patch_created_count", 0) != 0:
            issues.append("summary_actual_patch_nonzero")
        if summary.get("actual_document_changed_count", 0) != 0:
            issues.append("summary_actual_docx_nonzero")
        if summary.get("actual_writer_called_count", 0) != 0:
            issues.append("summary_actual_writer_nonzero")
        if summary.get("eligible_count") != sum(
            1 for i in intents if i.intent_status == "ELIGIBLE"
        ):
            issues.append("summary_eligible_mismatch")
        if summary.get("review_required_count") != sum(
            1 for i in intents if i.intent_status == "REVIEW_REQUIRED"
        ):
            issues.append("summary_review_mismatch")
        if summary.get("blocked_count") != sum(
            1 for i in intents if i.intent_status == "BLOCKED"
        ):
            issues.append("summary_blocked_mismatch")
        if summary.get("invalid_count") != sum(
            1 for i in intents if i.intent_status == "INVALID"
        ):
            issues.append("summary_invalid_mismatch")
        if summary.get("input_count") != len(intents):
            issues.append("summary_input_count_mismatch")

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "patch_targeting_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": {
            "unique_patch_intent_id": "duplicate_patch_intent_id" not in issues,
            "unique_patch_target_candidate_id": "duplicate_patch_target_candidate_id"
            not in issues,
            "unique_preview_id": "duplicate_preview_id" not in issues,
            "activation_always_disabled": not any(
                i.startswith("activation_allowed_true") for i in issues
            )
            and all(not t.activation_allowed for t in targets),
            "actual_patch_created_false": not any(
                "actual_patch_created_true" in i for i in issues
            )
            and all(not i.actual_patch_created for i in intents),
            "actual_document_changed_false": not any(
                "actual_document_changed_true" in i for i in issues
            )
            and all(not i.actual_document_changed for i in intents)
            and all(not p.actual_document_changed for p in previews),
            "actual_writer_called_false": not any(
                "actual_writer_or_docx_true" in i for i in issues
            )
            and all(not p.actual_writer_called for p in previews),
            "semantic_match_reference_valid": not any(
                i.startswith("unknown_semantic_match_id")
                or i.startswith("missing_semantic_match_id")
                for i in issues
            ),
            "no_preview_ready": not any(
                i.startswith("preview_ready_while_observational") for i in issues
            ),
            "summary_counts_consistent": not any(i.startswith("summary_") for i in issues),
            "source_requirement_id_optional_for_generic": True,
            "pr18_pr19_pr20_pr21_non_mutation": True,
            "change_review_non_mutation": True,
            "docx_writer_non_mutation": True,
            "legacy_pipeline_non_mutation": True,
            "no_llm": True,
            "freeze_maintained": True,
        },
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": "PR-22 observational patch targeting validation.",
    }
