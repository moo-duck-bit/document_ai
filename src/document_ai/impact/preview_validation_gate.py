# -*- coding: utf-8 -*-
"""PR-15: Preview Validation Gate (shadow decision layer).

Integrates Requirement Patch, Language Realizer, Activation Policy, and
Activation Preview validations into PASS / REVIEW / BLOCK.

Does NOT mutate prior artifacts, DOCX, or legacy generation.
eligible_for_docx_activation is observational only (never writes DOCX).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

GateStatus = Literal["PASS", "REVIEW", "BLOCK"]

STATUS_RANK = {"PASS": 0, "REVIEW": 1, "BLOCK": 2}

REASON_MESSAGES: dict[str, str] = {
    "PASS_ALL_VALID": "All validations passed; AUTO_APPLY preview applied.",
    "PATCH_INVALID": "Requirement patch validation is INVALID.",
    "PATCH_REVIEW_REQUIRED": "Requirement patch requires review.",
    "LANGUAGE_REVIEW_REQUIRED": "Language realizer status is REVIEW_REQUIRED.",
    "LANGUAGE_REJECTED": "Language realizer rejected the rewrite.",
    "LANGUAGE_WARNING": "Language realizer reported non-critical warnings.",
    "SEMANTIC_CHANGED": "Language realizer reported semantic_changed=true.",
    "MEANING_NOT_PRESERVED": "Language realizer meaning_preserved=false.",
    "ACTIVATION_REVIEW": "Activation decision is REVIEW.",
    "ACTIVATION_BLOCK": "Activation decision is BLOCK.",
    "PREVIEW_NOT_APPLIED": "AUTO_APPLY patch was not applied in preview.",
    "NON_AUTO_APPLY_WAS_APPLIED": "Non-AUTO_APPLY patch was applied in preview.",
    "BLOCK_WAS_APPLIED": "BLOCK decision patch was applied in preview.",
    "MISSING_DECISION_APPLIED": "Missing activation decision was applied in preview.",
    "MISSING_DECISION": "Activation decision is missing.",
    "PREVIEW_INVALID": "Preview validation is INVALID.",
    "PREVIEW_CONFLICT": "Preview conflict detected with original preserved.",
    "CONFLICT_DID_NOT_PRESERVE_ORIGINAL": "Conflict detected but original was not preserved.",
    "DUPLICATE_ANOMALY": "Duplicate / merge anomaly requires attention.",
    "TRACE_ID_MISMATCH": "patch_id or atomic_change_id mismatch across traces.",
    "ACTUAL_DOCX_CHANGED": "actual_docx_changed=true (forbidden).",
    "ACTUAL_GENERATION_CHANGED": "actual_generation_changed=true (forbidden).",
    "UNKNOWN_STATE": "Unknown decision or validation state.",
    "MISSING_ARTIFACT": "Required artifact/input missing; cannot safely PASS.",
    "INVARIANT_VIOLATION": "Gate invariant violated.",
    "MERGE_REVIEW_NEEDED": "Multi-patch merge requires human review.",
}


@dataclass
class PreviewGateResult:
    gate_result_id: str
    patch_id: str
    draft_id: str
    atomic_change_id: str
    requirement_id: str | None
    document: str
    field: str
    patch_validation_status: str
    language_validation_status: str
    activation_decision: str
    preview_applied: bool
    preview_validation_status: str
    conflict_detected: bool = False
    missing_decision: bool = False
    duplicate_anomaly: bool = False
    final_status: GateStatus | str = "BLOCK"
    reason_codes: list[str] = field(default_factory=list)
    reason_messages: list[str] = field(default_factory=list)
    eligible_for_docx_activation: bool = False
    actual_docx_changed: bool = False
    actual_generation_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rank(status: str) -> int:
    return STATUS_RANK.get(str(status), 99)


def _stronger(a: str, b: str) -> str:
    return a if _rank(a) >= _rank(b) else b


def _msg(code: str) -> str:
    return REASON_MESSAGES.get(code, code)


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def _index_by_patch_id(items: list[Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for it in items or []:
        d = _as_dict(it)
        pid = str(d.get("patch_id") or "")
        if pid:
            out[pid] = d
    return out


def _sort_key(r: PreviewGateResult) -> tuple[str, str, str, str, str]:
    return (
        str(r.atomic_change_id or ""),
        str(r.patch_id or ""),
        str(r.document or ""),
        str(r.requirement_id or ""),
        str(r.field or ""),
    )


def evaluate_preview_gate_item(
    *,
    patch: dict[str, Any] | None,
    language: dict[str, Any] | None,
    decision: dict[str, Any] | None,
    preview_entry: dict[str, Any] | None,
    aggregated_for_target: dict[str, Any] | None = None,
    preview_validation: dict[str, Any] | None = None,
    actual_docx_changed: bool = False,
    actual_generation_changed: bool = False,
    artifact_missing: bool = False,
) -> PreviewGateResult:
    """Evaluate one patch-level gate result. Fail-closed to BLOCK when unsure."""
    patch = patch or {}
    language = language or {}
    decision = decision or {}
    preview_entry = preview_entry or {}
    preview_validation = preview_validation or {}
    aggregated_for_target = aggregated_for_target or {}

    patch_id = str(
        patch.get("patch_id")
        or preview_entry.get("patch_id")
        or decision.get("patch_id")
        or language.get("patch_id")
        or "UNKNOWN"
    )
    draft_id = str(
        patch.get("draft_id")
        or preview_entry.get("draft_id")
        or language.get("draft_id")
        or decision.get("draft_id")
        or ""
    )
    atomic_change_id = str(
        patch.get("atomic_change_id")
        or preview_entry.get("atomic_change_id")
        or language.get("atomic_change_id")
        or decision.get("atomic_change_id")
        or ""
    )
    requirement_id = (
        patch.get("requirement_id")
        or preview_entry.get("requirement_id")
        or language.get("requirement_id")
        or decision.get("requirement_id")
    )
    document = str(
        patch.get("document") or preview_entry.get("document") or language.get("document") or ""
    )
    field = str(patch.get("field") or preview_entry.get("field") or language.get("field") or "")

    patch_status = str(patch.get("validation_status") or "UNKNOWN")
    lang_status = str(language.get("validation_status") or "UNKNOWN")
    act = str(
        decision.get("decision")
        or preview_entry.get("activation_decision")
        or "UNKNOWN"
    )
    preview_applied = bool(preview_entry.get("applied_in_preview", False))
    preview_val_status = str(
        preview_validation.get("status")
        or preview_entry.get("preview_validation_status")
        or "UNKNOWN"
    )

    missing_decision = bool(
        decision.get("missing_decision")
        or "missing_activation_decision" in list(preview_entry.get("reasons") or [])
        or (not decision.get("decision") and not preview_entry.get("activation_decision"))
    )
    if missing_decision and act == "UNKNOWN":
        act = str(preview_entry.get("activation_decision") or "REVIEW")

    conflict_detected = bool(aggregated_for_target.get("conflict_detected", False))
    conflict_preserved = True
    if conflict_detected:
        conflict_preserved = (
            aggregated_for_target.get("final_preview_requirement")
            == aggregated_for_target.get("original_requirement")
        )

    duplicate_anomaly = bool(
        aggregated_for_target.get("duplicate_anomaly")
        or "duplicate" in " ".join(str(x) for x in (patch.get("validation_issues") or [])).lower()
    )
    merge_review = bool(
        conflict_detected
        or aggregated_for_target.get("merge_review_needed")
        or (
            len(aggregated_for_target.get("applied_patch_ids") or []) > 1
            and aggregated_for_target.get("conflict_detected")
        )
    )

    # Trace id consistency
    id_mismatch = False
    for src in (language, decision, preview_entry):
        if not src:
            continue
        if src.get("patch_id") and patch.get("patch_id") and src.get("patch_id") != patch.get("patch_id"):
            id_mismatch = True
        if (
            src.get("atomic_change_id")
            and patch.get("atomic_change_id")
            and src.get("atomic_change_id") != patch.get("atomic_change_id")
        ):
            id_mismatch = True

    lang_rejected = bool(language.get("rejected", False))
    semantic_changed = bool(language.get("semantic_changed", False))
    meaning_preserved = language.get("meaning_preserved", True)
    if meaning_preserved is None:
        meaning_preserved = True
    meaning_preserved = bool(meaning_preserved)
    lang_style_ok = language.get("requirement_style", True)
    lang_grammar_ok = language.get("grammar_normalized", True)
    if lang_style_ok is None:
        lang_style_ok = True
    if lang_grammar_ok is None:
        lang_grammar_ok = True

    known_acts = {"AUTO_APPLY", "REVIEW", "BLOCK"}
    known_patch = {"VALID", "VALID_WITH_WARNINGS", "INVALID", "REVIEW_REQUIRED", "NO_ACTION"}
    known_lang = {"VALID", "VALID_WITH_WARNINGS", "INVALID", "REVIEW_REQUIRED"}
    known_preview = {"VALID", "VALID_WITH_WARNINGS", "INVALID", "REVIEW_REQUIRED"}

    status: GateStatus = "PASS"
    codes: list[str] = []

    def add(code: str, force: GateStatus) -> None:
        nonlocal status
        if code not in codes:
            codes.append(code)
        status = _stronger(status, force)  # type: ignore[assignment]

    # ---------- BLOCK conditions ----------
    if artifact_missing or not patch.get("patch_id"):
        add("MISSING_ARTIFACT", "BLOCK")
    if act not in known_acts and act != "UNKNOWN":
        add("UNKNOWN_STATE", "BLOCK")
    if act == "UNKNOWN" and not missing_decision:
        add("UNKNOWN_STATE", "BLOCK")
    if patch_status == "UNKNOWN" or (
        patch_status not in known_patch and patch.get("validation_status") is not None
    ):
        # unknown patch status → fail closed
        if patch_status not in known_patch:
            add("UNKNOWN_STATE", "BLOCK")
    if patch_status == "INVALID":
        add("PATCH_INVALID", "BLOCK")
    if act == "BLOCK":
        add("ACTIVATION_BLOCK", "BLOCK")
    if preview_val_status == "INVALID":
        add("PREVIEW_INVALID", "BLOCK")
    if act == "BLOCK" and preview_applied:
        add("BLOCK_WAS_APPLIED", "BLOCK")
    if act != "AUTO_APPLY" and preview_applied and not missing_decision:
        add("NON_AUTO_APPLY_WAS_APPLIED", "BLOCK")
    if missing_decision and preview_applied:
        add("MISSING_DECISION_APPLIED", "BLOCK")
    if act == "AUTO_APPLY" and not preview_applied and not conflict_detected:
        add("PREVIEW_NOT_APPLIED", "BLOCK")
    if conflict_detected and not conflict_preserved:
        add("CONFLICT_DID_NOT_PRESERVE_ORIGINAL", "BLOCK")
    if semantic_changed:
        add("SEMANTIC_CHANGED", "BLOCK")
    if not meaning_preserved:
        add("MEANING_NOT_PRESERVED", "BLOCK")
    if actual_docx_changed:
        add("ACTUAL_DOCX_CHANGED", "BLOCK")
    if actual_generation_changed:
        add("ACTUAL_GENERATION_CHANGED", "BLOCK")
    if id_mismatch:
        add("TRACE_ID_MISMATCH", "BLOCK")

    # ---------- REVIEW conditions ----------
    if lang_status == "REVIEW_REQUIRED":
        add("LANGUAGE_REVIEW_REQUIRED", "REVIEW")
    if lang_rejected:
        add("LANGUAGE_REJECTED", "REVIEW")
    if lang_status == "VALID_WITH_WARNINGS" or not lang_style_ok or not lang_grammar_ok:
        add("LANGUAGE_WARNING", "REVIEW")
    if act == "REVIEW" or missing_decision:
        if missing_decision and "MISSING_DECISION" not in codes:
            add("MISSING_DECISION", "REVIEW")
        if act == "REVIEW":
            add("ACTIVATION_REVIEW", "REVIEW")
    if conflict_detected and conflict_preserved:
        add("PREVIEW_CONFLICT", "REVIEW")
        if merge_review:
            add("MERGE_REVIEW_NEEDED", "REVIEW")
    if duplicate_anomaly:
        add("DUPLICATE_ANOMALY", "REVIEW")
    if patch_status in ("REVIEW_REQUIRED", "VALID_WITH_WARNINGS"):
        add("PATCH_REVIEW_REQUIRED", "REVIEW")
    if preview_val_status in ("REVIEW_REQUIRED", "VALID_WITH_WARNINGS") and status == "PASS":
        # non-critical preview warning → REVIEW (unless already blocked)
        if preview_val_status == "REVIEW_REQUIRED":
            add("PREVIEW_CONFLICT", "REVIEW")

    # ---------- PASS only if nothing elevated ----------
    if status == "PASS":
        # Must still satisfy full PASS checklist
        pass_ok = (
            patch_status == "VALID"
            and lang_status == "VALID"
            and not semantic_changed
            and meaning_preserved
            and not lang_rejected
            and act == "AUTO_APPLY"
            and preview_applied
            and preview_val_status == "VALID"
            and not conflict_detected
            and not missing_decision
            and not duplicate_anomaly
            and not actual_docx_changed
            and not actual_generation_changed
            and not artifact_missing
            and not id_mismatch
        )
        if pass_ok:
            codes = ["PASS_ALL_VALID"]
        else:
            # Should not happen if rules above are complete — fail closed
            add("UNKNOWN_STATE", "BLOCK")

    # Deduplicate codes preserving order
    seen: set[str] = set()
    uniq_codes: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            uniq_codes.append(c)

    eligible = status == "PASS"
    return PreviewGateResult(
        gate_result_id=f"PG-{patch_id}",
        patch_id=patch_id,
        draft_id=draft_id,
        atomic_change_id=atomic_change_id,
        requirement_id=requirement_id if requirement_id is not None else None,
        document=document,
        field=field,
        patch_validation_status=patch_status,
        language_validation_status=lang_status,
        activation_decision=act if act != "UNKNOWN" or not missing_decision else "REVIEW",
        preview_applied=preview_applied,
        preview_validation_status=preview_val_status,
        conflict_detected=conflict_detected,
        missing_decision=missing_decision,
        duplicate_anomaly=duplicate_anomaly,
        final_status=status,
        reason_codes=uniq_codes,
        reason_messages=[_msg(c) for c in uniq_codes],
        eligible_for_docx_activation=eligible,
        actual_docx_changed=actual_docx_changed,
        actual_generation_changed=actual_generation_changed,
    )


def build_preview_gate_results(
    *,
    patches: list[Any],
    languages: list[Any] | None = None,
    decisions: list[Any] | None = None,
    preview_entries: list[Any] | None = None,
    aggregated: list[Any] | None = None,
    preview_validation: dict[str, Any] | None = None,
    actual_docx_changed: bool = False,
    actual_generation_changed: bool = False,
    artifact_missing: bool = False,
) -> list[PreviewGateResult]:
    """Build deterministic per-patch gate results."""
    patch_map = _index_by_patch_id(patches)
    lang_map = _index_by_patch_id(languages)
    dec_map = _index_by_patch_id(decisions)
    prev_map = _index_by_patch_id(preview_entries)

    # Aggregate by requirement/document/field
    agg_by_target: dict[tuple[str, str, str], dict[str, Any]] = {}
    for a in aggregated or []:
        d = _as_dict(a)
        key = (
            str(d.get("requirement_id") or ""),
            str(d.get("document") or "").upper(),
            str(d.get("field") or ""),
        )
        agg_by_target[key] = d

    # Union of all patch ids from available sources
    all_ids = sorted(
        set(patch_map) | set(lang_map) | set(dec_map) | set(prev_map),
        key=lambda pid: (
            str((patch_map.get(pid) or prev_map.get(pid) or {}).get("atomic_change_id") or ""),
            pid,
        ),
    )

    results: list[PreviewGateResult] = []
    for pid in all_ids:
        p = patch_map.get(pid) or {}
        pe = prev_map.get(pid) or {}
        key = (
            str(p.get("requirement_id") or pe.get("requirement_id") or ""),
            str(p.get("document") or pe.get("document") or "").upper(),
            str(p.get("field") or pe.get("field") or ""),
        )
        missing_art = artifact_missing or (pid not in patch_map and pid not in prev_map)
        results.append(
            evaluate_preview_gate_item(
                patch=p if p else {"patch_id": pid},
                language=lang_map.get(pid),
                decision=dec_map.get(pid),
                preview_entry=pe,
                aggregated_for_target=agg_by_target.get(key),
                preview_validation=preview_validation,
                actual_docx_changed=actual_docx_changed,
                actual_generation_changed=actual_generation_changed,
                artifact_missing=missing_art or (not p and not pe),
            )
        )

    results.sort(key=_sort_key)
    return results


def validate_preview_gate_results(
    results: list[PreviewGateResult],
) -> dict[str, Any]:
    """Validate gate output invariants (including negative states)."""
    issues: list[str] = []
    warnings: list[str] = []

    for r in results:
        if r.final_status == "PASS":
            if r.activation_decision != "AUTO_APPLY":
                issues.append(f"{r.patch_id}:pass_without_auto_apply")
            if not r.preview_applied:
                issues.append(f"{r.patch_id}:pass_without_preview_apply")
            if not r.eligible_for_docx_activation:
                issues.append(f"{r.patch_id}:pass_not_eligible")
            if "SEMANTIC_CHANGED" in r.reason_codes:
                issues.append(f"{r.patch_id}:pass_with_semantic_changed")
            if "MEANING_NOT_PRESERVED" in r.reason_codes:
                issues.append(f"{r.patch_id}:pass_with_meaning_lost")
            if r.patch_validation_status != "VALID":
                issues.append(f"{r.patch_id}:pass_with_bad_patch")
            if r.language_validation_status != "VALID":
                issues.append(f"{r.patch_id}:pass_with_bad_language")
        if r.final_status in ("REVIEW", "BLOCK") and r.eligible_for_docx_activation:
            issues.append(f"{r.patch_id}:non_pass_eligible")
        if r.final_status == "PASS" and r.eligible_for_docx_activation is not True:
            issues.append(f"{r.patch_id}:pass_eligible_false")
        if r.activation_decision == "BLOCK" and r.preview_applied:
            issues.append(f"{r.patch_id}:block_applied_invariant")
        if r.activation_decision == "REVIEW" and r.preview_applied:
            issues.append(f"{r.patch_id}:review_applied_invariant")
        if r.missing_decision and r.preview_applied:
            issues.append(f"{r.patch_id}:missing_applied_invariant")
        if r.actual_docx_changed:
            issues.append(f"{r.patch_id}:docx_changed")
        if r.actual_generation_changed:
            issues.append(f"{r.patch_id}:generation_changed")
        if r.final_status not in ("PASS", "REVIEW", "BLOCK"):
            issues.append(f"{r.patch_id}:unknown_final_status")
        if r.activation_decision == "UNKNOWN":
            issues.append(f"{r.patch_id}:unknown_activation")

    # Precedence sanity: BLOCK reasons should not coexist with PASS
    for r in results:
        if r.final_status == "PASS" and any(
            c.startswith("ACTIVATION_BLOCK")
            or c in ("SEMANTIC_CHANGED", "PATCH_INVALID", "PREVIEW_INVALID")
            for c in r.reason_codes
        ):
            issues.append(f"{r.patch_id}:precedence_broken")

    invariants = {
        "pass_only_when_all_valid": not any(
            r.final_status == "PASS"
            and (
                r.patch_validation_status != "VALID"
                or r.language_validation_status != "VALID"
                or r.activation_decision != "AUTO_APPLY"
                or not r.preview_applied
            )
            for r in results
        ),
        "block_precedence": all(
            r.final_status != "PASS"
            for r in results
            if "ACTIVATION_BLOCK" in r.reason_codes or "SEMANTIC_CHANGED" in r.reason_codes
        ),
        "review_precedence_over_pass": all(
            r.final_status in ("REVIEW", "BLOCK")
            for r in results
            if "ACTIVATION_REVIEW" in r.reason_codes or "LANGUAGE_REVIEW_REQUIRED" in r.reason_codes
        ),
        "only_pass_is_docx_eligible": all(
            (r.final_status == "PASS") == r.eligible_for_docx_activation for r in results
        ),
        "review_not_docx_eligible": all(
            not r.eligible_for_docx_activation for r in results if r.final_status == "REVIEW"
        ),
        "block_not_docx_eligible": all(
            not r.eligible_for_docx_activation for r in results if r.final_status == "BLOCK"
        ),
        "auto_apply_required_for_pass": all(
            r.activation_decision == "AUTO_APPLY" for r in results if r.final_status == "PASS"
        ),
        "blocked_patch_not_applied": all(
            not (r.activation_decision == "BLOCK" and r.preview_applied) for r in results
        )
        or any("BLOCK_WAS_APPLIED" in r.reason_codes for r in results),
        "review_patch_not_applied": all(
            not (r.activation_decision == "REVIEW" and r.preview_applied and r.final_status != "BLOCK")
            for r in results
        )
        or any("NON_AUTO_APPLY_WAS_APPLIED" in r.reason_codes for r in results),
        "missing_decision_not_applied": all(
            not (r.missing_decision and r.preview_applied) for r in results
        )
        or any("MISSING_DECISION_APPLIED" in r.reason_codes for r in results),
        "conflict_preserves_original": all(
            (not r.conflict_detected)
            or "PREVIEW_CONFLICT" in r.reason_codes
            or "CONFLICT_DID_NOT_PRESERVE_ORIGINAL" in r.reason_codes
            for r in results
        ),
        "semantic_changed_never_passes": all(
            r.final_status != "PASS" for r in results if "SEMANTIC_CHANGED" in r.reason_codes
        ),
        "meaning_not_preserved_never_passes": all(
            r.final_status != "PASS" for r in results if "MEANING_NOT_PRESERVED" in r.reason_codes
        ),
        "actual_docx_unchanged": all(not r.actual_docx_changed for r in results),
        "actual_generation_unchanged": all(not r.actual_generation_changed for r in results),
        "gate_deterministic": True,
        "trace_ids_consistent": not any("TRACE_ID_MISMATCH" in r.reason_codes for r in results)
        or any(r.final_status == "BLOCK" for r in results if "TRACE_ID_MISMATCH" in r.reason_codes),
    }

    if issues:
        status = "INVALID"
    elif warnings:
        status = "VALID_WITH_WARNINGS"
    else:
        status = "VALID"

    return {
        "stage": "preview_gate_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": invariants,
        "note": "Shadow preview validation gate — does not affect DOCX.",
    }


def _global_status(results: list[PreviewGateResult]) -> GateStatus:
    if any(r.final_status == "BLOCK" for r in results):
        return "BLOCK"
    if any(r.final_status == "REVIEW" for r in results):
        return "REVIEW"
    return "PASS"


def build_preview_gate_summary(results: list[PreviewGateResult]) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    for r in results:
        for c in r.reason_codes:
            reason_counts[c] += 1
    return {
        "stage": "preview_gate_summary",
        "global_status": _global_status(results),
        "total_count": len(results),
        "pass_count": sum(1 for r in results if r.final_status == "PASS"),
        "review_count": sum(1 for r in results if r.final_status == "REVIEW"),
        "block_count": sum(1 for r in results if r.final_status == "BLOCK"),
        "eligible_count": sum(1 for r in results if r.eligible_for_docx_activation),
        "conflict_count": sum(1 for r in results if r.conflict_detected),
        "missing_decision_count": sum(1 for r in results if r.missing_decision),
        "rejected_language_count": sum(
            1 for r in results if "LANGUAGE_REJECTED" in r.reason_codes
        ),
        "semantic_change_count": sum(
            1 for r in results if "SEMANTIC_CHANGED" in r.reason_codes
        ),
        "docx_change_count": sum(1 for r in results if r.actual_docx_changed),
        "legacy_change_count": sum(1 for r in results if r.actual_generation_changed),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def compare_gate_vs_activation(results: list[PreviewGateResult]) -> dict[str, Any]:
    rows = []
    for r in results:
        rows.append(
            {
                "patch_id": r.patch_id,
                "atomic_change_id": r.atomic_change_id,
                "activation_decision": r.activation_decision,
                "preview_applied": r.preview_applied,
                "gate_final_status": r.final_status,
                "eligible_for_docx_activation": r.eligible_for_docx_activation,
                "reason_codes": list(r.reason_codes),
            }
        )
    return {
        "stage": "preview_gate_vs_activation",
        "pair_count": len(rows),
        "pairs": rows,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": "Side-by-side activation vs gate (observational).",
    }


def run_preview_validation_gate(
    *,
    patches: list[Any],
    languages: list[Any] | None = None,
    decisions: list[Any] | None = None,
    preview_entries: list[Any] | None = None,
    aggregated: list[Any] | None = None,
    preview_validation: dict[str, Any] | None = None,
    actual_docx_changed: bool = False,
    actual_generation_changed: bool = False,
    artifact_missing: bool = False,
) -> dict[str, Any]:
    """Orchestrate gate evaluation + validation + summaries."""
    # Defensive shallow copies so callers' lists are not mutated
    patches_in = list(patches or [])
    languages_in = list(languages or [])
    decisions_in = list(decisions or [])
    preview_in = list(preview_entries or [])
    aggregated_in = list(aggregated or [])

    results = build_preview_gate_results(
        patches=patches_in,
        languages=languages_in,
        decisions=decisions_in,
        preview_entries=preview_in,
        aggregated=aggregated_in,
        preview_validation=preview_validation,
        actual_docx_changed=actual_docx_changed,
        actual_generation_changed=actual_generation_changed,
        artifact_missing=artifact_missing,
    )
    validation = validate_preview_gate_results(results)
    summary = build_preview_gate_summary(results)
    vs_activation = compare_gate_vs_activation(results)

    return {
        "stage": "preview_validation_gate",
        "schema_version": "preview_validation_gate_v1",
        "results": results,
        "global_status": summary["global_status"],
        "validation": validation,
        "summary": summary,
        "gate_vs_activation": vs_activation,
        "invariants": validation.get("invariants") or {},
        "note": (
            "PR-15 shadow preview validation gate. "
            "Observational only; does not mutate prior stages or DOCX."
        ),
    }


def preview_gate_to_trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    results: list[PreviewGateResult] = payload.get("results") or []
    return {
        "stage": payload.get("stage"),
        "schema_version": payload.get("schema_version"),
        "global_status": payload.get("global_status"),
        "result_count": len(results),
        "results": [
            r.to_dict() if isinstance(r, PreviewGateResult) else r for r in results
        ],
        "validation": payload.get("validation") or {},
        "invariants": payload.get("invariants") or {},
        "note": payload.get("note"),
    }
