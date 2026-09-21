# -*- coding: utf-8 -*-
"""PR-13: Shadow Activation Preview Builder.

Shows pre-apply state for AUTO_APPLY requirement patches only.
Does NOT write DOCX or change legacy generation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.activation_policy import RequirementActivationDecision
from document_ai.impact.requirement_patch import (
    RequirementPatch,
    apply_requirement_patch,
)
from document_ai.impact.semantic_draft import SemanticDraft

PreviewValidationStatus = Literal[
    "VALID",
    "VALID_WITH_WARNINGS",
    "REVIEW_REQUIRED",
    "INVALID",
]


@dataclass
class ActivationPreviewEntry:
    preview_id: str
    patch_id: str
    draft_id: str
    atomic_change_id: str
    requirement_id: str | None
    document: str
    field: str
    operation: str
    activation_decision: str
    original_requirement: str
    proposed_requirement: str
    preview_requirement: str
    applied_in_preview: bool
    reasons: list[str] = field(default_factory=list)
    validation_status: str = ""
    scope_preserved: bool = False
    review_required: bool = True
    changed_spans: list[str] = field(default_factory=list)
    unchanged_spans: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AggregatedRequirementPreview:
    requirement_id: str | None
    document: str
    field: str
    original_requirement: str
    applied_patch_ids: list[str] = field(default_factory=list)
    skipped_patch_ids: list[str] = field(default_factory=list)
    final_preview_requirement: str = ""
    decision_trace: list[dict[str, Any]] = field(default_factory=list)
    conflict_detected: bool = False
    conflict_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _target_key(patch: RequirementPatch) -> tuple[str, str, str]:
    return (
        str(patch.requirement_id or ""),
        str(patch.document or "").upper(),
        str(patch.field or ""),
    )


def _draft_from_patch(patch: RequirementPatch) -> SemanticDraft:
    return SemanticDraft(
        draft_id=patch.draft_id,
        contract_id=patch.contract_id,
        atomic_change_id=patch.atomic_change_id,
        target={
            "document": patch.document,
            "requirement_id": patch.requirement_id,
            "field": patch.field,
        },
        operation=patch.operation,
        draft_text=patch.semantic_draft or "",
        generation_mode="RULE_BASED_SHADOW",
        used_inputs=["requirement_patch"],
        omitted_inputs=["full_change_request"],
        source_span=patch.semantic_draft or "",
        provenance=dict(patch.provenance or {}),
        validation_status=(
            "VALID"
            if patch.validation_status == "VALID"
            else (
                "VALID_WITH_WARNINGS"
                if patch.validation_status == "VALID_WITH_WARNINGS"
                else "REVIEW_REQUIRED"
            )
        ),
        validation_issues=list(patch.validation_issues or []),
        review_required=bool(patch.review_required),
        activation_eligible=bool((patch.provenance or {}).get("activation_eligible", True)),
        semantic_intent={},
    )


def build_activation_preview_entries(
    patches: list[RequirementPatch],
    decisions: list[RequirementActivationDecision],
) -> tuple[list[ActivationPreviewEntry], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build per-patch preview entries + review/blocked queues."""
    by_id = {d.patch_id: d for d in decisions}
    entries: list[ActivationPreviewEntry] = []
    review_queue: list[dict[str, Any]] = []
    blocked_queue: list[dict[str, Any]] = []

    for patch in patches:
        decision = by_id.get(patch.patch_id)
        reasons: list[str] = []
        if decision is None:
            act = "REVIEW"
            reasons = ["missing_activation_decision"]
            applied = False
            preview_text = patch.original_requirement
            review_required = True
            validation_status = patch.validation_status
            scope = patch.scope_preserved
        else:
            act = str(decision.decision)
            reasons = list(decision.reasons or [])
            # Guard: decision requirement_id mismatch (soft warning in reasons)
            if (
                decision.requirement_id
                and patch.requirement_id
                and decision.requirement_id != patch.requirement_id
            ):
                act = "REVIEW"
                reasons = list(reasons) + ["patch_decision_requirement_mismatch"]
            if act == "AUTO_APPLY":
                applied = True
                preview_text = patch.patched_requirement
                review_required = False
            elif act == "BLOCK":
                applied = False
                preview_text = patch.original_requirement
                review_required = True
            else:
                # REVIEW or unknown → conservative
                if act not in ("AUTO_APPLY", "REVIEW", "BLOCK"):
                    reasons = list(reasons) + [f"unknown_decision:{act}"]
                    act = "REVIEW"
                applied = False
                preview_text = patch.original_requirement
                review_required = True
            validation_status = decision.validation_status or patch.validation_status
            scope = decision.scope_preserved if decision else patch.scope_preserved

        entry = ActivationPreviewEntry(
            preview_id=f"PV-{patch.patch_id}",
            patch_id=patch.patch_id,
            draft_id=patch.draft_id,
            atomic_change_id=patch.atomic_change_id,
            requirement_id=patch.requirement_id,
            document=patch.document,
            field=patch.field,
            operation=patch.operation,
            activation_decision=act,
            original_requirement=patch.original_requirement,
            proposed_requirement=patch.patched_requirement,
            preview_requirement=preview_text,
            applied_in_preview=applied,
            reasons=reasons,
            validation_status=str(validation_status),
            scope_preserved=bool(scope),
            review_required=review_required,
            changed_spans=list(patch.changed_spans or []) if applied else [],
            unchanged_spans=list(patch.unchanged_spans or []),
        )
        entries.append(entry)

        if act == "REVIEW":
            review_queue.append(
                {
                    "patch_id": patch.patch_id,
                    "requirement_id": patch.requirement_id,
                    "reasons": reasons,
                    "original_requirement": patch.original_requirement,
                    "proposed_requirement": patch.patched_requirement,
                }
            )
        elif act == "BLOCK":
            blocked_queue.append(
                {
                    "patch_id": patch.patch_id,
                    "requirement_id": patch.requirement_id,
                    "reasons": reasons,
                    "validation_status": str(validation_status),
                }
            )

    return entries, review_queue, blocked_queue


def _sequential_merge_auto_apply(
    patches: list[RequirementPatch],
) -> AggregatedRequirementPreview:
    """Deterministically merge AUTO_APPLY patches for one target field."""
    patches_sorted = sorted(
        patches,
        key=lambda p: (str(p.atomic_change_id or ""), str(p.patch_id or "")),
    )
    original = patches_sorted[0].original_requirement if patches_sorted else ""
    # Prefer the shared original; if patches disagree on original, conflict
    originals = {p.original_requirement for p in patches_sorted}
    conflict = False
    conflict_reasons: list[str] = []
    if len(originals) > 1:
        conflict = True
        conflict_reasons.append("inconsistent_original_bases")

    current = original
    applied: list[str] = []
    skipped: list[str] = []
    trace: list[dict[str, Any]] = []

    if conflict:
        return AggregatedRequirementPreview(
            requirement_id=patches_sorted[0].requirement_id,
            document=patches_sorted[0].document,
            field=patches_sorted[0].field,
            original_requirement=original,
            applied_patch_ids=[],
            skipped_patch_ids=[p.patch_id for p in patches_sorted],
            final_preview_requirement=original,
            decision_trace=[
                {
                    "patch_id": p.patch_id,
                    "action": "skipped_conflict",
                    "reason": "inconsistent_original_bases",
                }
                for p in patches_sorted
            ],
            conflict_detected=True,
            conflict_reasons=conflict_reasons,
        )

    for p in patches_sorted:
        draft = _draft_from_patch(p)
        # Force VALID path for re-apply of already AUTO_APPLY patches
        draft.validation_status = "VALID"
        draft.review_required = False
        draft.activation_eligible = True
        before = current
        result = apply_requirement_patch(
            original_requirement=current,
            draft=draft,
            requirement_id=p.requirement_id,
            document=p.document,
            field=p.field,
        )
        if result.validation_status == "INVALID":
            conflict = True
            conflict_reasons.append(f"merge_invalid:{p.patch_id}")
            skipped.append(p.patch_id)
            trace.append(
                {
                    "patch_id": p.patch_id,
                    "action": "conflict",
                    "issues": list(result.validation_issues),
                }
            )
            break
        if result.validation_status == "REVIEW_REQUIRED" and result.operation not in (
            "NO_ACTION",
            "LINK",
        ):
            # Could not safely apply onto evolving base
            conflict = True
            conflict_reasons.append(f"merge_review_required:{p.patch_id}")
            skipped.append(p.patch_id)
            trace.append(
                {
                    "patch_id": p.patch_id,
                    "action": "conflict",
                    "issues": list(result.validation_issues),
                }
            )
            break
        current = result.patched_requirement
        applied.append(p.patch_id)
        trace.append(
            {
                "patch_id": p.patch_id,
                "action": "applied",
                "before_len": len(before),
                "after_len": len(current),
                "changed_spans": list(result.changed_spans),
            }
        )

    if conflict:
        # Silent resolution forbidden — keep original, mark all for review context
        return AggregatedRequirementPreview(
            requirement_id=patches_sorted[0].requirement_id,
            document=patches_sorted[0].document,
            field=patches_sorted[0].field,
            original_requirement=original,
            applied_patch_ids=[],
            skipped_patch_ids=[p.patch_id for p in patches_sorted],
            final_preview_requirement=original,
            decision_trace=trace,
            conflict_detected=True,
            conflict_reasons=conflict_reasons,
        )

    return AggregatedRequirementPreview(
        requirement_id=patches_sorted[0].requirement_id,
        document=patches_sorted[0].document,
        field=patches_sorted[0].field,
        original_requirement=original,
        applied_patch_ids=applied,
        skipped_patch_ids=skipped,
        final_preview_requirement=current,
        decision_trace=trace,
        conflict_detected=False,
        conflict_reasons=[],
    )


def build_aggregated_requirement_previews(
    patches: list[RequirementPatch],
    decisions: list[RequirementActivationDecision],
) -> list[AggregatedRequirementPreview]:
    """Aggregate AUTO_APPLY patches per requirement/document/field."""
    by_id = {d.patch_id: d for d in decisions}
    groups: dict[tuple[str, str, str], list[RequirementPatch]] = defaultdict(list)
    for p in patches:
        d = by_id.get(p.patch_id)
        if d is None or str(d.decision) != "AUTO_APPLY":
            continue
        groups[_target_key(p)].append(p)

    aggregated: list[AggregatedRequirementPreview] = []
    for key in sorted(groups.keys()):
        group = groups[key]
        if not group:
            continue
        if len(group) == 1:
            p = group[0]
            aggregated.append(
                AggregatedRequirementPreview(
                    requirement_id=p.requirement_id,
                    document=p.document,
                    field=p.field,
                    original_requirement=p.original_requirement,
                    applied_patch_ids=[p.patch_id],
                    skipped_patch_ids=[],
                    final_preview_requirement=p.patched_requirement,
                    decision_trace=[
                        {"patch_id": p.patch_id, "action": "applied_single"}
                    ],
                    conflict_detected=False,
                    conflict_reasons=[],
                )
            )
        else:
            aggregated.append(_sequential_merge_auto_apply(group))
    return aggregated


def validate_activation_preview(
    *,
    entries: list[ActivationPreviewEntry],
    aggregated: list[AggregatedRequirementPreview],
    decisions: list[RequirementActivationDecision],
) -> dict[str, Any]:
    """Preview invariants (shadow)."""
    issues: list[str] = []
    warnings: list[str] = []
    decision_ids = {d.patch_id for d in decisions}

    for e in entries:
        if e.applied_in_preview and e.activation_decision != "AUTO_APPLY":
            issues.append(f"{e.patch_id}:non_auto_applied")
        if e.activation_decision in ("REVIEW", "BLOCK"):
            if e.preview_requirement != e.original_requirement:
                issues.append(f"{e.patch_id}:review_block_not_original")
            if e.applied_in_preview:
                issues.append(f"{e.patch_id}:review_block_applied")
        if e.activation_decision == "BLOCK" and e.applied_in_preview:
            issues.append(f"{e.patch_id}:block_applied")
        if "missing_activation_decision" in e.reasons and e.applied_in_preview:
            issues.append(f"{e.patch_id}:missing_decision_applied")
        if e.patch_id not in decision_ids and e.applied_in_preview:
            issues.append(f"{e.patch_id}:orphan_applied")

    conflict_count = sum(1 for a in aggregated if a.conflict_detected)
    for a in aggregated:
        if a.conflict_detected:
            if a.final_preview_requirement != a.original_requirement:
                issues.append(
                    f"{a.requirement_id}:conflict_not_reverted"
                )
            warnings.append(f"conflict:{a.requirement_id}:{a.field}")

    status: PreviewValidationStatus
    if issues:
        status = "INVALID"
    elif conflict_count or warnings:
        status = "REVIEW_REQUIRED" if conflict_count else "VALID_WITH_WARNINGS"
    else:
        status = "VALID"

    applied = sum(1 for e in entries if e.applied_in_preview)
    return {
        "stage": "preview_validation",
        "status": status,
        "total_patch_count": len(entries),
        "applied_patch_count": applied,
        "review_count": sum(1 for e in entries if e.activation_decision == "REVIEW"),
        "block_count": sum(1 for e in entries if e.activation_decision == "BLOCK"),
        "conflict_count": conflict_count,
        "valid_count": 1 if status == "VALID" else 0,
        "warning_count": 1 if status == "VALID_WITH_WARNINGS" else 0,
        "review_required_count": 1 if status == "REVIEW_REQUIRED" else 0,
        "invalid_count": 1 if status == "INVALID" else 0,
        "invariants": {
            "only_auto_apply_applied": not any(
                e.applied_in_preview and e.activation_decision != "AUTO_APPLY"
                for e in entries
            ),
            "review_block_keep_original": not any(
                e.activation_decision in ("REVIEW", "BLOCK")
                and e.preview_requirement != e.original_requirement
                for e in entries
            ),
            "block_never_applied": not any(
                e.activation_decision == "BLOCK" and e.applied_in_preview for e in entries
            ),
            "missing_decision_not_applied": not any(
                "missing_activation_decision" in e.reasons and e.applied_in_preview
                for e in entries
            ),
            "conflict_keeps_original": all(
                (not a.conflict_detected)
                or a.final_preview_requirement == a.original_requirement
                for a in aggregated
            ),
            "actual_docx_unchanged": True,
            "actual_generation_unchanged": True,
        },
        "issues": issues,
        "warnings": warnings,
        "entries": [
            {
                "preview_id": e.preview_id,
                "patch_id": e.patch_id,
                "activation_decision": e.activation_decision,
                "applied_in_preview": e.applied_in_preview,
            }
            for e in entries
        ],
        "note": "Shadow preview validation — does not affect DOCX.",
    }


def build_preview_summary(
    *,
    entries: list[ActivationPreviewEntry],
    aggregated: list[AggregatedRequirementPreview],
    review_queue: list[dict[str, Any]],
    blocked_queue: list[dict[str, Any]],
) -> dict[str, Any]:
    by_doc: dict[str, int] = defaultdict(int)
    by_field: dict[str, int] = defaultdict(int)
    by_req_applied: dict[str, int] = defaultdict(int)
    for e in entries:
        if e.applied_in_preview:
            by_doc[str(e.document)] += 1
            by_field[str(e.field)] += 1
            by_req_applied[str(e.requirement_id)] += 1
    return {
        "stage": "preview_summary",
        "auto_apply_count": sum(
            1 for e in entries if e.activation_decision == "AUTO_APPLY"
        ),
        "applied_in_preview_count": sum(1 for e in entries if e.applied_in_preview),
        "review_count": len(review_queue),
        "block_count": len(blocked_queue),
        "aggregated_requirement_count": len(aggregated),
        "conflict_count": sum(1 for a in aggregated if a.conflict_detected),
        "applied_patches_by_requirement": dict(sorted(by_req_applied.items())),
        "by_document": dict(sorted(by_doc.items())),
        "by_field": dict(sorted(by_field.items())),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": "PR-13 activation preview is shadow-only.",
    }


def compare_preview_vs_legacy(
    *,
    entries: list[ActivationPreviewEntry],
    aggregated: list[AggregatedRequirementPreview],
    legacy_generation_texts: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "stage": "preview_vs_legacy",
        "legacy_generation_texts": list(legacy_generation_texts or []),
        "activation_preview_entries": [e.to_dict() for e in entries],
        "aggregated_requirement_previews": [a.to_dict() for a in aggregated],
        "applied_preview_count": sum(1 for e in entries if e.applied_in_preview),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": (
            "Shadow activation preview vs legacy whole-CR generation. "
            "Legacy DOCX remains actual output."
        ),
    }


def build_activation_preview(
    *,
    patches: list[RequirementPatch],
    decisions: list[RequirementActivationDecision],
    legacy_generation_texts: list[str] | None = None,
) -> dict[str, Any]:
    """Orchestrate preview entries, aggregation, queues, validation, summary."""
    # Detect decision patch_ids that don't match any patch
    patch_ids = {p.patch_id for p in patches}
    orphan_decisions = [d for d in decisions if d.patch_id not in patch_ids]

    entries, review_queue, blocked_queue = build_activation_preview_entries(
        patches, decisions
    )
    # Orphan decisions → blocked queue note
    for d in orphan_decisions:
        blocked_queue.append(
            {
                "patch_id": d.patch_id,
                "requirement_id": d.requirement_id,
                "reasons": list(d.reasons or []) + ["patch_id_mismatch_orphan_decision"],
                "validation_status": d.validation_status,
            }
        )

    aggregated = build_aggregated_requirement_previews(patches, decisions)
    # Conflicts → ensure review visibility
    for a in aggregated:
        if a.conflict_detected:
            for pid in a.skipped_patch_ids:
                if not any(r.get("patch_id") == pid for r in review_queue):
                    review_queue.append(
                        {
                            "patch_id": pid,
                            "requirement_id": a.requirement_id,
                            "reasons": ["multi_patch_conflict"] + list(a.conflict_reasons),
                            "original_requirement": a.original_requirement,
                            "proposed_requirement": "",
                        }
                    )

    validation = validate_activation_preview(
        entries=entries, aggregated=aggregated, decisions=decisions
    )
    summary = build_preview_summary(
        entries=entries,
        aggregated=aggregated,
        review_queue=review_queue,
        blocked_queue=blocked_queue,
    )
    vs_legacy = compare_preview_vs_legacy(
        entries=entries,
        aggregated=aggregated,
        legacy_generation_texts=legacy_generation_texts,
    )
    return {
        "stage": "activation_preview",
        "schema_version": "activation_preview_v1",
        "entries": [e.to_dict() for e in entries],
        "aggregated_requirement_previews": [a.to_dict() for a in aggregated],
        "review_queue": review_queue,
        "blocked_queue": blocked_queue,
        "validation": validation,
        "summary": summary,
        "preview_vs_legacy": vs_legacy,
        "note": (
            "PR-13 shadow activation preview. "
            "AUTO_APPLY only reflected in preview; DOCX unchanged."
        ),
    }
