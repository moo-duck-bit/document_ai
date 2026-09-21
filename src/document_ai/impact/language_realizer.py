# -*- coding: utf-8 -*-
"""PR-14 / PR-14.1: Requirement Language Realizer (shadow).

Post-processes RequirementPatch.patched_requirement with *narrow*,
allowlisted surface fixes. Does NOT invent meaning, unify requirement
styles, or apply broad particle heuristics.

PR-14.1: removed over-broad regex/style rules that corrupted valid prose.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable

from document_ai.impact.requirement_patch import RequirementPatch

RuleFn = Callable[[str], tuple[str, bool]]

# ---------------------------------------------------------------------------
# Exact phrase replacements (longest first)
# ---------------------------------------------------------------------------

EXACT_REPLACEMENTS: list[tuple[str, str]] = [
    # Conditional glue
    ("시인 경우", "시"),
    ("시 인 경우", "시"),
    # Lock conjugation
    ("잠그해야 한다", "잠가야 한다"),
    ("잠그어야 한다", "잠가야 한다"),
    ("잠그해야", "잠가야 한다"),
    ("잠그어야", "잠가야 한다"),
    # Duplicate notification (surface only — no new subject)
    ("알림에 대한 알림을 제공해야 한다", "알림을 제공해야 한다"),
    ("알림에 대한 알림", "알림"),
    ("알림 알림", "알림"),
    # Unlock target phrase
    ("대상을 잠금 해제", "계정 잠금을 해제"),
    ("대상을 해제", "계정 잠금을 해제"),
    # Account / event list
    ("계정, 기록 및 이벤트을", "계정 잠금, 로그인 실패 및 관련 이벤트를"),
    ("계정, 기록 및 이벤트를", "계정 잠금, 로그인 실패 및 관련 이벤트를"),
    ("계정, 기록 및 이벤트", "계정 잠금, 로그인 실패 및 관련 이벤트"),
    # Allowlisted particle / phrase fixes only
    ("이벤트을", "이벤트를"),
    ("은(는)", "은"),
    ("는(은)", "는"),
    ("을(를)", "을"),
    ("를(을)", "를"),
    ("이(가)", "이"),
    ("가(이)", "가"),
    # Spacing-only (safe)
    ("해야한다", "해야 한다"),
    ("하여야 한다", "해야 한다"),
]


# ---------------------------------------------------------------------------
# Narrow regex (must not touch "~도록 설계한다" family)
# ---------------------------------------------------------------------------

SAFE_REGEX_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "conditional_si_case_ws",
        re.compile(r"시\s*인\s*경우"),
        "시",
    ),
    (
        "jamgeu_with_handa",
        re.compile(r"잠그[어해]야\s*한다"),
        "잠가야 한다",
    ),
    (
        "jamgeu_bare",
        re.compile(r"잠그[어해]야(?!\s*한다)"),
        "잠가야 한다",
    ),
    (
        "duplicate_notification_ws",
        re.compile(r"알림에\s*대한\s*알림"),
        "알림",
    ),
    (
        "target_unlock_ws",
        re.compile(r"대상을\s*해제"),
        "계정 잠금을 해제",
    ),
    (
        "account_event_list_ws",
        re.compile(r"계정,\s*기록\s*및\s*이벤트[을를]?"),
        "계정 잠금, 로그인 실패 및 관련 이벤트를",
    ),
]


# ---------------------------------------------------------------------------
# Unsafe after-text patterns → rollback
# ---------------------------------------------------------------------------

UNSAFE_AFTER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("broken_haya", re.compile(r"하야\s*한다")),
    ("broken_issya", re.compile(r"있야\s*한다")),
    ("broken_anhya", re.compile(r"않야\s*한다")),
    ("broken_biini", re.compile(r"비인이")),
    ("lost_si_before_system", re.compile(r"실패\s+시스템은")),
    ("leftover_jamgeu", re.compile(r"잠그해야")),
    ("broken_dourok_haya", re.compile(r"도록\s*하야")),
    ("broken_eul_su_issya", re.compile(r"수\s*있야")),
]


_NEGATION_MARKERS = ("않", "금지", "중단하지", "하지 않", "불가")
_CONDITION_MARKERS = ("경우", "시", "때", "조건")
_SECURITY_NOUNS = (
    "계정",
    "잠금",
    "로그인",
    "인증",
    "알림",
    "감사",
    "IP",
    "차단",
    "비인가",
    "접근",
    "이벤트",
)


@dataclass
class LanguageRealization:
    realization_id: str
    patch_id: str
    draft_id: str
    atomic_change_id: str
    requirement_id: str | None
    document: str
    field: str
    before_text: str
    after_text: str
    applied_rules: list[str] = field(default_factory=list)
    rule_count: int = 0
    semantic_changed: bool = False
    meaning_preserved: bool = True
    requirement_style: bool = True
    grammar_normalized: bool = True
    validation_status: str = "VALID"
    # Optional PR-14.1 fields (schema-compatible)
    rejected: bool = False
    rejection_reasons: list[str] = field(default_factory=list)
    unsafe_pattern_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _apply_exact_replacements(text: str) -> tuple[str, list[str]]:
    new = text
    applied: list[str] = []
    # longest first to avoid partial collisions
    for src, dst in sorted(EXACT_REPLACEMENTS, key=lambda x: len(x[0]), reverse=True):
        if src in new:
            new = new.replace(src, dst)
            applied.append(f"exact:{src}")
    return new, applied


def _apply_safe_regex(text: str) -> tuple[str, list[str]]:
    new = text
    applied: list[str] = []
    for name, pattern, repl in SAFE_REGEX_RULES:
        updated, n = pattern.subn(repl, new)
        if n:
            new = updated
            applied.append(name)
    return new, applied


def normalize_whitespace(text: str) -> tuple[str, bool]:
    """Conservative whitespace / punctuation cleanup only."""
    new = text
    new = re.sub(r"[ \t]+", " ", new)
    new = re.sub(r"\n{3,}", "\n\n", new)
    new = re.sub(r" +([,.])", r"\1", new)
    new = re.sub(r"다\.\s*다\.", "다.", new)
    # Trim trailing spaces per line; keep intentional newlines
    new = "\n".join(line.rstrip() for line in new.split("\n"))
    new = new.strip()
    return new, new != text


def _extract_numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text or "")


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(m in (text or "") for m in markers)


def validate_realization(before: str, after: str) -> tuple[bool, list[str]]:
    """Return (ok, reasons). If not ok, caller must roll back to before."""
    reasons: list[str] = []
    if after == before:
        return True, []

    for name, pat in UNSAFE_AFTER_PATTERNS:
        if pat.search(after):
            reasons.append(f"unsafe:{name}")

    # Numbers must be preserved
    if _extract_numbers(before) != _extract_numbers(after):
        reasons.append("numbers_not_preserved")

    # Negation / condition markers present in before must remain
    for m in _NEGATION_MARKERS:
        if m in before and m not in after:
            reasons.append(f"negation_lost:{m}")
            break
    for m in _CONDITION_MARKERS:
        # "시인 경우" → "시" is intentional; require at least one condition marker
        if _has_any(before, _CONDITION_MARKERS) and not _has_any(after, _CONDITION_MARKERS):
            reasons.append("condition_markers_lost")
            break

    # Security nouns in before must not disappear
    for noun in _SECURITY_NOUNS:
        if noun in before and noun not in after:
            reasons.append(f"security_noun_lost:{noun}")
            break

    # Do not introduce known corruption of 비인가
    if "비인가" in before and "비인이" in after:
        reasons.append("biinga_corrupted")

    # Do not drop "시" before 시스템 when before had "시인 경우" / "시 시스템"
    if re.search(r"시(?:인\s*경우)?\s*시스템", before) and re.search(
        r"실패\s+시스템", after
    ):
        reasons.append("si_dropped_before_system")

    # Excessive token deletion (>40% of content tokens lost)
    b_toks = set(re.findall(r"[가-힣A-Za-z0-9_]{2,}", before))
    a_toks = set(re.findall(r"[가-힣A-Za-z0-9_]{2,}", after))
    if b_toks:
        kept = len(b_toks & a_toks)
        if kept < max(1, int(len(b_toks) * 0.6)):
            reasons.append("excessive_token_deletion")

    # Never convert design-style endings into broken 야 한다
    if re.search(r"도록\s*설계한다", before) and not re.search(
        r"도록\s*설계한다", after
    ):
        # Style conversion of design endings is forbidden in PR-14.1
        reasons.append("design_style_altered")

    return (len(reasons) == 0), reasons


def _meaning_preserved(before: str, after: str) -> bool:
    ok, _ = validate_realization(before, after)
    if before == after:
        return True
    return ok


def _requirement_style_ok(text: str) -> bool:
    """PR-14.1: mixed styles are allowed; only flag broken endings."""
    if re.search(r"(하야|있야|않야)\s*한다", text or ""):
        return False
    return True


def realize_requirement_text(text: str) -> tuple[str, list[str]]:
    """Apply safe rules; return (after_text, applied_rule_names).

    Order: exact → narrow regex → whitespace → safety (rollback if unsafe).
    Idempotent: realize(realize(text)) == realize(text).
    """
    before = text or ""
    current = before
    applied: list[str] = []

    current, exact_rules = _apply_exact_replacements(current)
    applied.extend(exact_rules)

    current, regex_rules = _apply_safe_regex(current)
    applied.extend(regex_rules)

    current, ws_changed = normalize_whitespace(current)
    if ws_changed:
        applied.append("normalize_whitespace")

    ok, reasons = validate_realization(before, current)
    if not ok:
        return before, [f"rollback:{r}" for r in reasons]

    return current, applied


def realize_requirement_patch(patch: RequirementPatch) -> LanguageRealization:
    """Realize one patch's patched_requirement (shadow)."""
    before = patch.patched_requirement or ""
    after, applied = realize_requirement_text(before)

    rejected = False
    rejection_reasons: list[str] = []
    unsafe = False
    meaning_ok = True
    status = "VALID"

    if any(r.startswith("rollback:") for r in applied):
        rejected = True
        rejection_reasons = [r.removeprefix("rollback:") for r in applied]
        unsafe = any(r.startswith("unsafe:") for r in rejection_reasons)
        after = before
        applied = []
        meaning_ok = False
        status = "REVIEW_REQUIRED"
    else:
        meaning_ok = _meaning_preserved(before, after)
        if not meaning_ok:
            rejected = True
            rejection_reasons = ["meaning_not_preserved"]
            after = before
            applied = []
            status = "REVIEW_REQUIRED"

    style_ok = _requirement_style_ok(after)
    if not style_ok and status == "VALID":
        status = "VALID_WITH_WARNINGS"

    # semantic_changed is derived: True only if we would have altered meaning
    # (we never accept that path — always roll back — so always False)
    semantic_changed = False

    return LanguageRealization(
        realization_id=f"LR-{patch.patch_id}",
        patch_id=patch.patch_id,
        draft_id=patch.draft_id,
        atomic_change_id=patch.atomic_change_id,
        requirement_id=patch.requirement_id,
        document=patch.document,
        field=patch.field,
        before_text=before,
        after_text=after,
        applied_rules=applied,
        rule_count=len(applied),
        semantic_changed=semantic_changed,
        meaning_preserved=True if after == before and rejected else meaning_ok or after == before,
        requirement_style=style_ok,
        grammar_normalized=True,
        validation_status=status,
        rejected=rejected,
        rejection_reasons=rejection_reasons,
        unsafe_pattern_detected=unsafe,
    )


def apply_language_realizations(
    patches: list[RequirementPatch],
) -> tuple[list[LanguageRealization], list[RequirementPatch]]:
    """Realize all patches; return (realizations, patches_with_realized_text).

    Original RequirementPatch objects are not mutated.
    """
    realizations: list[LanguageRealization] = []
    realized_patches: list[RequirementPatch] = []
    for p in patches:
        lr = realize_requirement_patch(p)
        realizations.append(lr)
        prov = dict(p.provenance or {})
        prov["language_realized"] = True
        prov["language_rule_count"] = lr.rule_count
        prov["language_applied_rules"] = list(lr.applied_rules)
        if lr.rejected:
            prov["language_rejected"] = True
            prov["language_rejection_reasons"] = list(lr.rejection_reasons)
        realized_patches.append(
            replace(
                p,
                patched_requirement=lr.after_text,
                provenance=prov,
            )
        )
    return realizations, realized_patches


def validate_language_realizations(
    realizations: list[LanguageRealization],
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    for r in realizations:
        if r.semantic_changed:
            issues.append(f"{r.patch_id}:semantic_changed")
        if not r.meaning_preserved:
            issues.append(f"{r.patch_id}:meaning_not_preserved")
        if not r.requirement_style:
            warnings.append(f"{r.patch_id}:style_warning")
        if not r.grammar_normalized:
            warnings.append(f"{r.patch_id}:grammar_warning")
        if r.validation_status == "REVIEW_REQUIRED" and r.before_text != r.after_text:
            issues.append(f"{r.patch_id}:review_but_rewrote")
        if r.unsafe_pattern_detected and r.before_text != r.after_text:
            issues.append(f"{r.patch_id}:unsafe_accepted")

    if issues:
        status = "INVALID"
    elif warnings or any(r.rejected for r in realizations):
        status = "VALID_WITH_WARNINGS" if not any(
            r.validation_status == "REVIEW_REQUIRED" for r in realizations
        ) else "REVIEW_REQUIRED"
        if any(r.validation_status == "REVIEW_REQUIRED" for r in realizations):
            status = "REVIEW_REQUIRED"
    else:
        status = "VALID"

    return {
        "stage": "language_realization_validation",
        "status": status,
        "total_count": len(realizations),
        "changed_count": sum(1 for r in realizations if r.before_text != r.after_text),
        "unchanged_count": sum(1 for r in realizations if r.before_text == r.after_text),
        "rejected_count": sum(1 for r in realizations if r.rejected),
        "review_required_count": sum(
            1 for r in realizations if r.validation_status == "REVIEW_REQUIRED"
        ),
        "invariants": {
            "semantic_changed_false": all(not r.semantic_changed for r in realizations),
            "meaning_preserved": all(r.meaning_preserved for r in realizations),
            "requirement_style": all(r.requirement_style for r in realizations)
            or bool(warnings),
            "grammar_normalized": all(r.grammar_normalized for r in realizations),
            "no_unsafe_accepted": all(
                (not r.unsafe_pattern_detected) or r.before_text == r.after_text
                for r in realizations
            ),
            "actual_docx_unchanged": True,
            "actual_generation_unchanged": True,
        },
        "issues": issues,
        "warnings": warnings,
        "note": "Shadow language realization validation — does not affect DOCX.",
    }


def build_language_summary(realizations: list[LanguageRealization]) -> dict[str, Any]:
    rule_counts: dict[str, int] = {}
    for r in realizations:
        for name in r.applied_rules:
            rule_counts[name] = rule_counts.get(name, 0) + 1
    return {
        "stage": "language_summary",
        "total_patch_count": len(realizations),
        "realized_change_count": sum(
            1 for r in realizations if r.before_text != r.after_text
        ),
        "rejected_count": sum(1 for r in realizations if r.rejected),
        "total_rules_fired": sum(r.rule_count for r in realizations),
        "rule_counts": rule_counts,
        "semantic_changed_any": any(r.semantic_changed for r in realizations),
        "meaning_preserved_all": all(r.meaning_preserved for r in realizations),
        "requirement_style_all": all(r.requirement_style for r in realizations),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def compare_language_vs_patch(
    realizations: list[LanguageRealization],
    patches: list[RequirementPatch],
) -> dict[str, Any]:
    by_id = {p.patch_id: p for p in patches}
    pairs = []
    for r in realizations:
        p = by_id.get(r.patch_id)
        pairs.append(
            {
                "patch_id": r.patch_id,
                "patch_patched_requirement": (p.patched_requirement if p else None),
                "before_text": r.before_text,
                "after_text": r.after_text,
                "applied_rules": list(r.applied_rules),
                "rejected": r.rejected,
                "rejection_reasons": list(r.rejection_reasons),
                "texts_differ": r.before_text != r.after_text,
            }
        )
    return {
        "stage": "language_vs_patch",
        "pair_count": len(pairs),
        "changed_pair_count": sum(1 for x in pairs if x["texts_differ"]),
        "rejected_pair_count": sum(1 for x in pairs if x["rejected"]),
        "pairs": pairs,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": "Observational: language after vs original RequirementPatch text.",
    }


def language_realizations_to_trace_payload(
    realizations: list[LanguageRealization],
) -> dict[str, Any]:
    return {
        "stage": "language_realization",
        "schema_version": "language_realizer_v1",
        "realization_count": len(realizations),
        "realizations": [r.to_dict() for r in realizations],
        "note": (
            "PR-14.1 shadow language realizer. Exact/allowlist only; "
            "unsafe rewrites roll back; no DOCX write."
        ),
    }


def realize_requirement_patches(
    patches: list[RequirementPatch],
) -> dict[str, Any]:
    """Orchestrate realization + validation + summaries."""
    realizations, realized_patches = apply_language_realizations(patches)
    validation = validate_language_realizations(realizations)
    summary = build_language_summary(realizations)
    vs_patch = compare_language_vs_patch(realizations, patches)
    return {
        "realizations": realizations,
        "realized_patches": realized_patches,
        "validation": validation,
        "summary": summary,
        "language_vs_patch": vs_patch,
        "trace": language_realizations_to_trace_payload(realizations),
    }
