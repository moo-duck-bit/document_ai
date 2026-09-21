# -*- coding: utf-8 -*-
"""PR-11: Shadow Requirement-level Patch Application.

Applies one SemanticDraft to one structured Requirement text field.
No DOCX / Word / serialization. Shadow comparison only.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.patch_contract import normalize_patch_operation
from document_ai.impact.semantic_draft import SemanticDraft

PatchValidationStatus = Literal[
    "VALID",
    "VALID_WITH_WARNINGS",
    "INVALID",
    "REVIEW_REQUIRED",
    "NO_ACTION",
]

CLAUSE_SPLIT_RE = re.compile(r"(?<=다\.)\s+|(?<=다)\n+|\n+")
TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")


@dataclass
class RequirementPatch:
    """One draft applied to one requirement field (shadow)."""

    patch_id: str
    draft_id: str
    contract_id: str
    atomic_change_id: str
    requirement_id: str | None
    document: str
    field: str
    operation: str
    original_requirement: str
    semantic_draft: str
    patched_requirement: str
    changed_spans: list[str] = field(default_factory=list)
    unchanged_spans: list[str] = field(default_factory=list)
    validation_status: PatchValidationStatus | str = "REVIEW_REQUIRED"
    validation_issues: list[str] = field(default_factory=list)
    review_required: bool = True
    scope_preserved: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clauses(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(raw) if p and p.strip()]
    return parts if parts else [raw]


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "") if len(t) >= 2}


def _overlap_score(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _best_clause_index(clauses: list[str], draft: str) -> int | None:
    if not clauses or not draft:
        return None
    scored = [(i, _overlap_score(c, draft), len(_tokens(c) & _tokens(draft))) for i, c in enumerate(clauses)]
    scored.sort(key=lambda x: (-x[1], -x[2], x[0]))
    best_i, best_score, best_hits = scored[0]
    # Accept modest Jaccard or at least 2 shared content tokens
    if best_score < 0.12 and best_hits < 2:
        return None
    if best_hits <= 0:
        return None
    return best_i


def _join_clauses(clauses: list[str]) -> str:
    out: list[str] = []
    for c in clauses:
        c = c.strip()
        if not c:
            continue
        if not c.endswith((".", "。", "다")):
            # keep as-is; Korean requirements often end with 다.
            pass
        out.append(c)
    return "\n".join(out).strip()


def _normalize_for_dup(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def _already_contains(original: str, draft: str) -> bool:
    if not draft.strip():
        return True
    o = _normalize_for_dup(original)
    d = _normalize_for_dup(draft)
    if d and d in o:
        return True
    # High token overlap with any clause
    for c in _clauses(original):
        if _overlap_score(c, draft) >= 0.85:
            return True
    return False


def _compute_spans(original: str, patched: str) -> tuple[list[str], list[str]]:
    orig_c = _clauses(original)
    new_c = _clauses(patched)
    unchanged: list[str] = []
    changed: list[str] = []
    orig_norm = {_normalize_for_dup(c): c for c in orig_c}
    new_norms = {_normalize_for_dup(c) for c in new_c}
    for n, c in orig_norm.items():
        if n in new_norms:
            unchanged.append(c)
        else:
            changed.append(f"- {c}")
    for c in new_c:
        if _normalize_for_dup(c) not in orig_norm:
            changed.append(f"+ {c}")
    return changed, unchanged


def apply_requirement_patch(
    *,
    original_requirement: str,
    draft: SemanticDraft,
    requirement_id: str | None = None,
    document: str | None = None,
    field: str | None = None,
) -> RequirementPatch:
    """Apply one semantic draft to one requirement text (deterministic, shadow)."""
    op = normalize_patch_operation(str(draft.operation))
    rid = requirement_id or (draft.target or {}).get("requirement_id")
    doc = (document or (draft.target or {}).get("document") or "").upper()
    fld = field or (draft.target or {}).get("field") or ""
    draft_text = (draft.draft_text or "").strip()
    original = original_requirement or ""
    patch_id = f"RP-{draft.draft_id}"

    base = RequirementPatch(
        patch_id=patch_id,
        draft_id=draft.draft_id,
        contract_id=draft.contract_id,
        atomic_change_id=draft.atomic_change_id,
        requirement_id=rid,
        document=doc,
        field=fld,
        operation=op,
        original_requirement=original,
        semantic_draft=draft_text,
        patched_requirement=original,
        provenance={
            "path": "shadow_requirement_patch",
            "draft_validation": draft.validation_status,
            "activation_eligible": draft.activation_eligible,
        },
    )

    # Non-generating / blocked drafts
    if op == "NO_ACTION":
        base.validation_status = "NO_ACTION"
        base.review_required = False
        base.scope_preserved = True
        base.unchanged_spans = _clauses(original)
        return base

    if op == "REVIEW_REQUIRED" or draft.validation_status in ("INVALID", "REVIEW_REQUIRED"):
        base.validation_status = "REVIEW_REQUIRED"
        base.review_required = True
        base.validation_issues = ["draft_not_eligible_for_patch"] + list(
            draft.validation_issues or []
        )
        base.unchanged_spans = _clauses(original)
        return base

    if op == "LINK":
        # Do not rewrite requirement prose — record link metadata only
        base.patched_requirement = original
        base.changed_spans = [
            f"LINK:{draft.atomic_change_id}->{doc}:{rid}:{fld}"
        ]
        base.unchanged_spans = _clauses(original)
        base.scope_preserved = True
        base.validation_status = "VALID"
        base.review_required = False
        base.provenance["link_instruction"] = draft_text
        return validate_requirement_patch(base)

    if not draft_text and op != "DELETE":
        base.validation_status = "REVIEW_REQUIRED"
        base.review_required = True
        base.validation_issues = ["empty_draft_text"]
        base.unchanged_spans = _clauses(original)
        return base

    clauses = _clauses(original)

    if op == "REPLACE":
        # Replace only the target field content with draft
        base.patched_requirement = draft_text
        base.changed_spans, base.unchanged_spans = _compute_spans(original, draft_text)
        if not original.strip():
            base.unchanged_spans = []
            base.changed_spans = [f"+ {draft_text}"]
        return validate_requirement_patch(base)

    if op == "ADD":
        if _already_contains(original, draft_text):
            base.patched_requirement = original
            base.validation_issues = ["duplicate_responsibility_skipped"]
            base.unchanged_spans = clauses
            base.scope_preserved = True
            base.validation_status = "VALID_WITH_WARNINGS"
            base.review_required = False
            return base
        patched = (original.rstrip() + "\n" + draft_text).strip() if original.strip() else draft_text
        base.patched_requirement = patched
        base.changed_spans = [f"+ {draft_text}"]
        base.unchanged_spans = clauses
        return validate_requirement_patch(base)

    if op == "UPDATE":
        idx = _best_clause_index(clauses, draft_text)
        if idx is None:
            # No overlapping responsibility — append like ADD but mark as update-append
            if _already_contains(original, draft_text):
                base.patched_requirement = original
                base.unchanged_spans = clauses
                base.validation_issues = ["duplicate_responsibility_skipped"]
                base.validation_status = "VALID_WITH_WARNINGS"
                base.scope_preserved = True
                base.review_required = False
                return base
            patched = (original.rstrip() + "\n" + draft_text).strip() if original.strip() else draft_text
            base.patched_requirement = patched
            base.changed_spans = [f"+ {draft_text}"]
            base.unchanged_spans = clauses
            return validate_requirement_patch(base)
        old = clauses[idx]
        new_clauses = list(clauses)
        new_clauses[idx] = draft_text
        patched = _join_clauses(new_clauses)
        base.patched_requirement = patched
        base.changed_spans = [f"- {old}", f"+ {draft_text}"]
        base.unchanged_spans = [c for i, c in enumerate(clauses) if i != idx]
        return validate_requirement_patch(base)

    if op == "CONSTRAIN":
        idx = _best_clause_index(clauses, draft_text)
        if idx is None:
            # Append constraint sentence only
            if _already_contains(original, draft_text):
                base.patched_requirement = original
                base.unchanged_spans = clauses
                base.validation_issues = ["duplicate_constraint_skipped"]
                base.validation_status = "VALID_WITH_WARNINGS"
                base.scope_preserved = True
                base.review_required = False
                return base
            patched = (original.rstrip() + "\n" + draft_text).strip() if original.strip() else draft_text
            base.patched_requirement = patched
            base.changed_spans = [f"+ {draft_text}"]
            base.unchanged_spans = clauses
            return validate_requirement_patch(base)
        # Inject after matched clause (do not rewrite whole clause)
        old = clauses[idx]
        if _normalize_for_dup(draft_text) in _normalize_for_dup(old):
            base.patched_requirement = original
            base.unchanged_spans = clauses
            base.validation_issues = ["constraint_already_present"]
            base.validation_status = "VALID_WITH_WARNINGS"
            base.scope_preserved = True
            base.review_required = False
            return base
        new_clauses = list(clauses)
        new_clauses[idx] = f"{old.rstrip()} {draft_text}".strip()
        patched = _join_clauses(new_clauses)
        base.patched_requirement = patched
        base.changed_spans = [f"- {old}", f"+ {new_clauses[idx]}"]
        base.unchanged_spans = [c for i, c in enumerate(clauses) if i != idx]
        return validate_requirement_patch(base)

    if op == "DELETE":
        intent = getattr(draft, "semantic_intent", None) or {}
        bits: list[str] = []
        for key in ("action", "object", "affected_entity", "recipient", "output"):
            v = intent.get(key)
            if isinstance(v, list):
                bits.extend(str(x) for x in v if x)
            elif v:
                bits.append(str(v))
        probe = " ".join(bits).strip() or draft.source_span or draft_text
        idx = _best_clause_index(clauses, probe)
        if idx is None and draft_text:
            idx = _best_clause_index(clauses, draft_text)
        if idx is None:
            base.validation_status = "REVIEW_REQUIRED"
            base.review_required = True
            base.validation_issues = ["delete_target_clause_not_found"]
            base.unchanged_spans = clauses
            return base
        removed = clauses[idx]
        new_clauses = [c for i, c in enumerate(clauses) if i != idx]
        patched = _join_clauses(new_clauses)
        base.patched_requirement = patched
        base.changed_spans = [f"- {removed}"]
        base.unchanged_spans = new_clauses
        return validate_requirement_patch(base)

    base.validation_status = "REVIEW_REQUIRED"
    base.review_required = True
    base.validation_issues = [f"unsupported_operation:{op}"]
    base.unchanged_spans = clauses
    return base


def validate_requirement_patch(patch: RequirementPatch) -> RequirementPatch:
    """Validate patched requirement vs original + draft intent."""
    issues: list[str] = []
    warnings: list[str] = []
    op = normalize_patch_operation(patch.operation)
    original = patch.original_requirement or ""
    patched = patch.patched_requirement or ""
    draft = patch.semantic_draft or ""

    # Target preserved
    if not patch.requirement_id:
        warnings.append("missing_requirement_id")
    if not patch.field:
        warnings.append("missing_field")

    # Unrelated text preserved (except REPLACE which may replace whole field)
    if op != "REPLACE":
        orig_clauses = _clauses(original)
        new_norm = {_normalize_for_dup(c) for c in _clauses(patched)}
        for c in orig_clauses:
            # For UPDATE/DELETE/CONSTRAIN, unchanged clauses must remain
            if c in patch.unchanged_spans and _normalize_for_dup(c) not in new_norm:
                issues.append("unrelated_clause_lost")
                break
        # Scope: most original tokens that aren't in the changed clause should remain
        if orig_clauses and patch.unchanged_spans:
            for c in patch.unchanged_spans:
                if _normalize_for_dup(c) not in new_norm and op != "DELETE":
                    # DELETE removes one clause; unchanged should still be in patched
                    if op != "DELETE":
                        issues.append("unchanged_span_missing_in_patched")
                        break

    # Semantic intent preserved for draft-producing ops
    if op in ("ADD", "UPDATE", "CONSTRAIN", "REPLACE") and draft:
        if not any(t in patched for t in _tokens(draft) if len(t) >= 2) and draft not in patched:
            # At least some draft tokens should appear
            draft_toks = [t for t in _tokens(draft) if len(t) >= 3]
            if draft_toks and not any(t in patched.lower() for t in draft_toks):
                issues.append("semantic_intent_not_in_patched")

    # No duplicate responsibility (exact draft twice)
    if draft and patched.count(draft) > 1:
        issues.append("duplicate_responsibility")

    # Operation satisfied
    if op == "ADD" and draft and draft not in patched and not _already_contains(patched, draft):
        # may have been skipped as duplicate against original — ok if warning set
        if "duplicate_responsibility_skipped" not in patch.validation_issues:
            issues.append("add_not_applied")
    if op == "DELETE" and patch.changed_spans and all(
        not s.startswith("- ") for s in patch.changed_spans
    ):
        issues.append("delete_not_applied")
    if op == "LINK" and patched != original:
        issues.append("link_rewrote_prose")

    # Unrelated insertion: large token set in patched not in original∪draft
    if op != "REPLACE":
        allowed = _tokens(original) | _tokens(draft)
        extra = _tokens(patched) - allowed
        # Allow small connective noise
        noisy = {t for t in extra if len(t) >= 4}
        if len(noisy) >= 5:
            warnings.append("possible_unrelated_insertion")

    patch.scope_preserved = "unrelated_clause_lost" not in issues and (
        "unchanged_span_missing_in_patched" not in issues
    )

    if issues:
        patch.validation_status = "INVALID"
        patch.review_required = True
    elif warnings or patch.validation_issues:
        # keep prior warnings
        prev = [x for x in patch.validation_issues if x.endswith("_skipped") or "already" in x]
        patch.validation_status = "VALID_WITH_WARNINGS" if (warnings or prev) else "VALID"
        patch.review_required = False
    else:
        patch.validation_status = "VALID"
        patch.review_required = False

    patch.validation_issues = list(
        dict.fromkeys(list(patch.validation_issues) + issues + [f"warn:{w}" for w in warnings])
    )
    return patch


def apply_requirement_patches(
    *,
    drafts: list[SemanticDraft],
    requirement_texts: dict[str, str],
    default_field: str = "description",
) -> list[RequirementPatch]:
    """Apply each draft independently to its target requirement text.

    requirement_texts keyed by requirement_id (optionally 'id::field').
    """
    patches: list[RequirementPatch] = []
    for d in drafts:
        rid = (d.target or {}).get("requirement_id")
        fld = (d.target or {}).get("field") or default_field
        doc = (d.target or {}).get("document") or ""
        key = f"{rid}::{fld}" if rid else ""
        original = ""
        if key and key in requirement_texts:
            original = requirement_texts[key]
        elif rid and rid in requirement_texts:
            original = requirement_texts[rid]
        patches.append(
            apply_requirement_patch(
                original_requirement=original,
                draft=d,
                requirement_id=rid,
                document=doc,
                field=fld,
            )
        )
    return patches


def validate_requirement_patches(patches: list[RequirementPatch]) -> dict[str, Any]:
    counts = {
        "VALID": 0,
        "VALID_WITH_WARNINGS": 0,
        "INVALID": 0,
        "REVIEW_REQUIRED": 0,
        "NO_ACTION": 0,
    }
    for p in patches:
        st = str(p.validation_status)
        if st in counts:
            counts[st] += 1
        else:
            counts["REVIEW_REQUIRED"] += 1
    return {
        "stage": "requirement_patch_validation",
        "total": len(patches),
        **{k.lower(): v for k, v in counts.items()},
        "scope_preserved_count": sum(1 for p in patches if p.scope_preserved),
        "entries": [
            {
                "patch_id": p.patch_id,
                "draft_id": p.draft_id,
                "atomic_change_id": p.atomic_change_id,
                "requirement_id": p.requirement_id,
                "operation": p.operation,
                "validation_status": p.validation_status,
                "validation_issues": list(p.validation_issues),
                "scope_preserved": p.scope_preserved,
                "review_required": p.review_required,
            }
            for p in patches
        ],
        "note": "Shadow requirement patch validation — does not affect DOCX.",
    }


def compare_legacy_vs_requirement_patches(
    *,
    patches: list[RequirementPatch],
    legacy_generation_texts: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "stage": "legacy_vs_requirement_patch",
        "legacy_generation_texts": list(legacy_generation_texts or []),
        "requirement_patches": [p.to_dict() for p in patches],
        "patched_count": sum(
            1
            for p in patches
            if p.patched_requirement != p.original_requirement and p.operation not in ("LINK", "NO_ACTION")
        ),
        "scope_preserved_count": sum(1 for p in patches if p.scope_preserved),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": (
            "Shadow requirement patches vs legacy whole-CR generation. "
            "Legacy DOCX path remains actual."
        ),
    }


def requirement_patches_to_trace_payload(patches: list[RequirementPatch]) -> dict[str, Any]:
    return {
        "stage": "requirement_patches_shadow",
        "schema_version": "requirement_patch_v1",
        "patch_count": len(patches),
        "patches": [p.to_dict() for p in patches],
        "note": (
            "PR-11 shadow requirement-level patch application. "
            "No DOCX editing; structured text only."
        ),
    }
