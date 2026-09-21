# -*- coding: utf-8 -*-
"""PR-10: Shadow Semantic Generation from Patch Contract.

Deterministic rule/template drafts for comparison only.
Does NOT replace legacy whole-CR generation or mutate DOCX.
Does NOT accept full Change Request text as generator input.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.patch_contract import (
    DocumentTarget,
    PatchContract,
    normalize_patch_operation,
)

GenerationMode = Literal[
    "RULE_BASED_SHADOW",
    "TEMPLATE_BASED_SHADOW",
    "REVIEW_REQUIRED",
    "NO_ACTION",
]

DraftValidationStatus = Literal[
    "VALID",
    "VALID_WITH_WARNINGS",
    "INVALID",
    "REVIEW_REQUIRED",
]

# Grammatical / obligation terms allowed even if not in contract facets.
_ALLOWED_FUNCTION_WORDS = frozenset(
    {
        "시스템",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "에",
        "에게",
        "에서",
        "으로",
        "로",
        "와",
        "과",
        "또는",
        "및",
        "경우",
        "때",
        "후",
        "전",
        "중",
        "하나",
        "해당",
        "사실",
        "내용",
        "해야",
        "한다",
        "수",
        "있다",
        "있도록",
        "제공",
        "기록",
        "지원",
        "유지",
        "변경",
        "상태",
        "대상",
        "기간",
        "동안",
        "이후",
        "이상",
        "이하",
        "자동",
        "삭제",
        "보관",
        "생성",
        "알림",
        "안내",
        "조회",
        "다운로드",
        "연결",
        "삭제",
        "명시",
        "의도",
        "필드",
        "요구사항",
        "설계",
        "문서",
        "traceability",
        "link",
    }
)

# Canonical action → Korean verb phrase fragment (domain-independent stems).
_ACTION_VERB: dict[str, str] = {
    "알림": "알림을 제공",
    "안내": "안내를 제공",
    "통지": "통지를 제공",
    "전송": "전송",
    "조회": "조회",
    "표시": "표시",
    "생성": "생성",
    "삭제": "삭제",
    "등록": "등록",
    "저장": "저장",
    "기록": "기록으로 남기",
    "감사": "감사 기록으로 남기",
    "잠금": "잠그",
    "해제": "해제",
    "갱신": "갱신",
    "변경": "변경",
    "취소": "취소",
    "승인": "승인",
    "검증": "검증",
    "제한": "제한",
    "차단": "차단",
    "다운로드": "다운로드할 수 있도록 하",
    "지원": "지원",
    "보관": "보관",
    "관리": "관리",
    "식별": "식별",
    "분류": "분류",
    "검색": "검색",
    "필터": "필터링",
    "모니터링": "모니터링",
    "평가": "평가",
    "분석": "분석",
    "동기화": "동기화",
    "보충": "보충",
    "예약": "예약",
    "결제": "결제",
    "보고": "보고",
    "강화": "강화",
}

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")


@dataclass
class SemanticDraft:
    draft_id: str
    contract_id: str
    atomic_change_id: str
    target: dict[str, Any]
    operation: str
    draft_text: str
    generation_mode: GenerationMode | str
    used_inputs: list[str] = field(default_factory=list)
    omitted_inputs: list[str] = field(default_factory=list)
    source_span: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    validation_status: DraftValidationStatus | str = "REVIEW_REQUIRED"
    validation_issues: list[str] = field(default_factory=list)
    review_required: bool = True
    concept_coverage: dict[str, Any] = field(default_factory=dict)
    semantic_intent: dict[str, Any] = field(default_factory=dict)
    activation_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _render_actor(actor: str | None) -> str:
    if not actor or actor == "implicit_system":
        return "시스템"
    return actor


def _action_phrase(action: str | None) -> str:
    if not action:
        return "반영"
    return _ACTION_VERB.get(action, action)


def _join_or(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} 또는 {parts[1]}"
    return " 또는 ".join(parts[:-1]) + f" 또는 {parts[-1]}"


def _join_and(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f" 및 {parts[-1]}"


def _has_alternative_constraint(constraints: list[str], condition: list[str]) -> bool:
    blob = " ".join(constraints + condition)
    return any(x in blob for x in ("또는", "중 하나", "하나", "OR", "or"))


def _contract_concepts(intent: dict[str, Any], source_span: str) -> set[str]:
    """Normalized facet concepts from the contract (not the full CR)."""
    concepts: set[str] = set()
    for key in (
        "action",
        "actor",
        "recipient",
        "condition",
        "responsibility_type",
    ):
        for v in _as_list(intent.get(key)):
            if v and v != "implicit_system":
                concepts.add(v.lower())
    for key in ("object", "constraint", "output", "affected_entity"):
        for v in _as_list(intent.get(key)):
            if v:
                concepts.add(v.lower())
    # Tokens from source_span that match known intent surfaces
    span_toks = {t.lower() for t in TOKEN_RE.findall(source_span or "")}
    for c in list(concepts):
        # keep multi-char concepts from span too
        pass
    concepts |= {t for t in span_toks if len(t) >= 2}
    return concepts


def _draft_tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "") if len(t) >= 2}


def _build_core_statement(intent: dict[str, Any]) -> str:
    actors = _as_list(intent.get("actor"))
    actor = _render_actor(actors[0] if actors else None)

    actions = _as_list(intent.get("action"))
    action = actions[0] if actions else None
    verb = _action_phrase(action)

    recipients = _as_list(intent.get("recipient"))
    objects = _as_list(intent.get("object"))
    affected = _as_list(intent.get("affected_entity"))
    outputs = _as_list(intent.get("output"))
    conditions = _as_list(intent.get("condition"))
    constraints = _as_list(intent.get("constraint"))

    obj_parts = objects or affected
    obj_phrase = _join_and(obj_parts)

    # Alternative constraints → OR phrasing
    if _has_alternative_constraint(constraints, conditions) and (constraints or conditions):
        alt_bits = [c for c in constraints if c not in ("또는", "중 하나", "자동")]
        alt_core = _join_or(alt_bits) if alt_bits else _join_or(constraints)
        cond = _join_and(conditions)
        subject = obj_phrase or "대상"
        if cond:
            return f"{cond}인 경우 {subject}은 {alt_core}에 따라 {verb}될 수 있어야 한다."
        return f"{subject}은 {alt_core}에 따라 {verb}될 수 있어야 한다."

    cond_phrase = _join_and(conditions)
    recipient_phrase = recipients[0] if recipients else None

    # Notification / display with recipient
    if recipient_phrase and action in ("알림", "안내", "통지", "전송", "메시지"):
        about = obj_phrase or _join_and(outputs) or "해당 내용"
        if cond_phrase:
            return (
                f"{cond_phrase}인 경우 {actor}은 {recipient_phrase}에게 "
                f"{about}에 대한 {verb}해야 한다."
            )
        return f"{actor}은 {recipient_phrase}에게 {about}에 대한 {verb}해야 한다."

    # Record / audit
    if action in ("기록", "감사", "추적"):
        about = obj_phrase or _join_and(outputs) or "해당 이벤트"
        out = _join_and(outputs) or "기록"
        if cond_phrase:
            return f"{cond_phrase}인 경우 {actor}은 {about}을 {out}으로 남겨야 한다."
        return f"{actor}은 {about}을 {out}으로 남겨야 한다."

    # State change on affected entity
    if affected or action in ("잠금", "해제", "갱신", "변경", "취소", "차단", "제한"):
        target = _join_and(affected) or obj_phrase or "대상"
        if cond_phrase:
            return f"{cond_phrase}인 경우 {actor}은 {target}을 {verb}해야 한다."
        return f"{actor}은 {target}을 {verb}해야 한다."

    # Generic create/provide
    focus = obj_phrase or _join_and(outputs)
    if cond_phrase and focus:
        return f"{cond_phrase}인 경우 {actor}은 {focus}을 {verb}해야 한다."
    if focus:
        return f"{actor}은 {focus}을 {verb}해야 한다."
    if cond_phrase:
        return f"{cond_phrase}인 경우 {actor}은 {verb}해야 한다."
    return f"{actor}은 {verb}해야 한다."


def _build_constrain_statement(intent: dict[str, Any]) -> str:
    conditions = _as_list(intent.get("condition"))
    constraints = _as_list(intent.get("constraint"))
    bits = conditions + [c for c in constraints if c]
    if _has_alternative_constraint(constraints, conditions):
        return f"다음 제약 중 하나를 지원해야 한다: {_join_or(bits)}."
    if bits:
        return f"다음 제약을 적용해야 한다: {_join_and(bits)}."
    return "명시된 제약을 적용해야 한다."


def _build_link_statement(contract: PatchContract) -> str:
    target = contract.target or {}
    rid = target.get("requirement_id") or contract.owner_requirement_id or ""
    field = target.get("field") or contract.target_field or ""
    doc = target.get("document") or ""
    return (
        f"{doc} {rid}의 {field} 필드에 대해 "
        f"ACU {contract.atomic_change_id} traceability 연결을 유지해야 한다."
    )


def _build_delete_statement(contract: PatchContract) -> str:
    target = contract.target or {}
    rid = target.get("requirement_id") or ""
    field = target.get("field") or ""
    return f"삭제 의도: {rid}.{field} (자동 대체 문구 없음)."


def _reuse_target_terms(draft: str, owner_target_text: str | None) -> tuple[str, list[str]]:
    """Optionally prefer terminology present in owner target context (style only)."""
    if not owner_target_text:
        return draft, []
    reused: list[str] = []
    # If draft mentions a short term and target has a longer synonymous surface, keep draft;
    # record overlapping tokens as target-context-derived.
    draft_toks = _draft_tokens(draft)
    target_toks = _draft_tokens(owner_target_text)
    overlap = sorted(draft_toks & target_toks)
    for t in overlap:
        if len(t) >= 2:
            reused.append(t)
    return draft, reused[:20]


def generate_semantic_draft(
    contract: PatchContract,
    *,
    owner_target_text: str | None = None,
    # Explicitly forbidden — accept only to fail loudly in tests if passed via kwargs abuse
    change_request_text: str | None = None,
    full_cr: str | None = None,
    cr_text: str | None = None,
) -> SemanticDraft:
    """Generate one shadow draft from a single PatchContract.

    Must not receive full Change Request. Pass change_request_text/full_cr/cr_text
    only in tests expecting rejection.
    """
    omitted = [
        "full_change_request",
        "unrelated_acus",
        "whole_b3_b4",
        "unrelated_owners",
        "docx_body_outside_target",
    ]
    used = [
        "patch_contract",
        "semantic_intent",
        "document_target",
        "source_span",
        "provenance",
    ]
    if owner_target_text:
        used.append("owner_target_text")

    draft_id = f"SD-{contract.contract_id}"
    target = dict(contract.target or {})
    op = normalize_patch_operation(str(contract.patch_operation))
    intent = dict(contract.semantic_intent or {})

    # Reject forbidden full-CR inputs
    if change_request_text or full_cr or cr_text:
        return SemanticDraft(
            draft_id=draft_id,
            contract_id=contract.contract_id,
            atomic_change_id=contract.atomic_change_id,
            target=target,
            operation=op,
            draft_text="",
            generation_mode="REVIEW_REQUIRED",
            used_inputs=used,
            omitted_inputs=omitted,
            source_span=contract.source_span,
            provenance={
                "error": "full_cr_input_forbidden",
                "contract_provenance": dict(contract.provenance or {}),
            },
            validation_status="INVALID",
            validation_issues=["full_cr_input_forbidden"],
            review_required=True,
            semantic_intent=intent,
            activation_eligible=False,
        )

    # Contract validation dependency — only OK contracts get automatic prose
    if contract.validation_status != "OK" or (
        contract.review_required and normalize_patch_operation(str(contract.patch_operation))
        not in ("NO_ACTION", "DELETE", "REVIEW_REQUIRED")
    ):
        if contract.validation_status != "OK":
            return SemanticDraft(
                draft_id=draft_id,
                contract_id=contract.contract_id,
                atomic_change_id=contract.atomic_change_id,
                target=target,
                operation=op,
                draft_text="",
                generation_mode="REVIEW_REQUIRED",
                used_inputs=used,
                omitted_inputs=omitted,
                source_span=contract.source_span,
                provenance={
                    "contract_validation": contract.validation_status,
                    **dict(contract.provenance or {}),
                },
                validation_status="REVIEW_REQUIRED",
                validation_issues=["contract_not_valid_for_generation"]
                + list(contract.validation_issues or []),
                review_required=True,
                semantic_intent=intent,
                activation_eligible=False,
            )

    if op == "NO_ACTION":
        return SemanticDraft(
            draft_id=draft_id,
            contract_id=contract.contract_id,
            atomic_change_id=contract.atomic_change_id,
            target=target,
            operation=op,
            draft_text="",
            generation_mode="NO_ACTION",
            used_inputs=used,
            omitted_inputs=omitted,
            source_span=contract.source_span,
            provenance=dict(contract.provenance or {}),
            validation_status="VALID",
            validation_issues=[],
            review_required=False,
            semantic_intent=intent,
            activation_eligible=False,
        )

    if op == "REVIEW_REQUIRED":
        return SemanticDraft(
            draft_id=draft_id,
            contract_id=contract.contract_id,
            atomic_change_id=contract.atomic_change_id,
            target=target,
            operation=op,
            draft_text="",
            generation_mode="REVIEW_REQUIRED",
            used_inputs=used,
            omitted_inputs=omitted,
            source_span=contract.source_span,
            provenance=dict(contract.provenance or {}),
            validation_status="REVIEW_REQUIRED",
            validation_issues=["operation_review_required"],
            review_required=True,
            semantic_intent=intent,
            activation_eligible=False,
        )

    if op == "DELETE":
        text = _build_delete_statement(contract)
        mode: GenerationMode = "RULE_BASED_SHADOW"
    elif op == "LINK":
        text = _build_link_statement(contract)
        mode = "TEMPLATE_BASED_SHADOW"
    elif op == "CONSTRAIN":
        text = _build_constrain_statement(intent)
        mode = "RULE_BASED_SHADOW"
    elif op in ("ADD", "UPDATE", "REPLACE"):
        text = _build_core_statement(intent)
        mode = "RULE_BASED_SHADOW"
    else:
        return SemanticDraft(
            draft_id=draft_id,
            contract_id=contract.contract_id,
            atomic_change_id=contract.atomic_change_id,
            target=target,
            operation=op,
            draft_text="",
            generation_mode="REVIEW_REQUIRED",
            used_inputs=used,
            omitted_inputs=omitted,
            source_span=contract.source_span,
            provenance=dict(contract.provenance or {}),
            validation_status="REVIEW_REQUIRED",
            validation_issues=["unsupported_operation"],
            review_required=True,
            semantic_intent=intent,
            activation_eligible=False,
        )

    text, reused = _reuse_target_terms(text, owner_target_text)
    # Normalize awkward particles slightly
    text = text.replace("은(는)", "은").replace("을(를)", "을").replace("이(가)", "이")
    # Fix 은 after vowel-ending clumsily kept simple
    text = re.sub(r"시스템은", "시스템은", text)

    draft = SemanticDraft(
        draft_id=draft_id,
        contract_id=contract.contract_id,
        atomic_change_id=contract.atomic_change_id,
        target=target,
        operation=op,
        draft_text=text,
        generation_mode=mode,
        used_inputs=used,
        omitted_inputs=omitted,
        source_span=contract.source_span,
        provenance={
            "contract_provenance": dict(contract.provenance or {}),
            "contract_derived": sorted(_contract_concepts(intent, contract.source_span)),
            "target_context_terms": reused,
            "connective_language": ["시스템은", "해야 한다", "인 경우"],
            "path": "shadow_semantic_generation",
        },
        semantic_intent=intent,
    )
    return validate_semantic_draft(draft, contract=contract)


def validate_semantic_draft(
    draft: SemanticDraft,
    *,
    contract: PatchContract,
    other_acu_concepts: set[str] | None = None,
) -> SemanticDraft:
    """Lightweight shadow validation of a semantic draft."""
    issues: list[str] = []
    warnings: list[str] = []
    op = normalize_patch_operation(draft.operation)
    intent = draft.semantic_intent or contract.semantic_intent or {}

    # A/B identity
    if draft.contract_id != contract.contract_id:
        issues.append("contract_id_mismatch")
    if draft.atomic_change_id != contract.atomic_change_id:
        issues.append("atomic_change_id_mismatch")
    if (draft.target or {}).get("requirement_id") != (contract.target or {}).get("requirement_id"):
        warnings.append("target_requirement_drift")

    # C operation
    if op != normalize_patch_operation(str(contract.patch_operation)):
        issues.append("operation_mismatch")

    # Policy ops
    if op in ("NO_ACTION", "REVIEW_REQUIRED"):
        if draft.draft_text.strip():
            issues.append("unexpected_draft_for_non_generating_op")
        draft.validation_status = "REVIEW_REQUIRED" if op == "REVIEW_REQUIRED" else "VALID"
        draft.validation_issues = issues
        draft.review_required = op == "REVIEW_REQUIRED"
        draft.activation_eligible = False
        return draft

    if op == "DELETE":
        if not draft.draft_text.strip():
            issues.append("empty_delete_metadata")
        # DELETE drafts are metadata, not activation-eligible prose
        draft.validation_status = "VALID" if not issues else "INVALID"
        draft.validation_issues = issues
        draft.review_required = bool(issues)
        draft.activation_eligible = False
        draft.concept_coverage = {"mode": "delete_metadata"}
        return draft

    # I non-empty
    if not (draft.draft_text or "").strip():
        issues.append("empty_draft")

    # D primary action
    actions = _as_list(intent.get("action"))
    if actions and not any(a in draft.draft_text for a in actions):
        # verb mapping may paraphrase — check verb fragment
        if not any(_action_phrase(a)[:2] in draft.draft_text for a in actions):
            warnings.append("primary_action_not_surface_matched")

    # E object/recipient
    for r in _as_list(intent.get("recipient")):
        if r and r not in draft.draft_text:
            issues.append(f"missing_recipient:{r}")
    # Actor must not be rendered as recipient performer for notify
    for r in _as_list(intent.get("recipient")):
        if r and f"{r}가" in draft.draft_text and "알림" in draft.draft_text:
            issues.append("recipient_misrendered_as_actor")

    # F condition/constraint
    for c in _as_list(intent.get("condition")):
        # allow partial overlap of condition tokens
        toks = [t for t in TOKEN_RE.findall(c) if len(t) >= 2]
        if toks and not any(t in draft.draft_text for t in toks):
            warnings.append("condition_weakly_represented")
    if _has_alternative_constraint(_as_list(intent.get("constraint")), _as_list(intent.get("condition"))):
        if "또는" not in draft.draft_text and "중 하나" not in draft.draft_text:
            warnings.append("alternative_or_not_explicit")

    # G/H scope + full-CR leakage
    allowed = _contract_concepts(intent, contract.source_span) | {
        w.lower() for w in _ALLOWED_FUNCTION_WORDS
    }
    draft_toks = _draft_tokens(draft.draft_text)
    # Drop pure obligation endings
    suspicious = {
        t
        for t in draft_toks
        if t not in allowed
        and t not in {a.lower() for a in actions}
        and len(t) >= 2
    }
    # Filter very common Korean verbs from action map values
    for frag in _ACTION_VERB.values():
        for t in TOKEN_RE.findall(frag):
            suspicious.discard(t.lower())

    other = {c.lower() for c in (other_acu_concepts or set())}
    leaked = sorted(suspicious & other)
    if leaked:
        issues.append(f"cross_acu_leakage:{','.join(leaked[:8])}")

    # Whole-CR copy: draft equals source_span is OK; equals huge multi-clause CR is not —
    # we never receive CR, so detect multi-sentence with many uncovered tokens
    if draft.draft_text.strip() == (contract.source_span or "").strip() and len(draft.draft_text) > 200:
        warnings.append("draft_equals_long_source_span")

    coverage = {
        "contract_concepts": sorted(allowed)[:40],
        "draft_tokens": sorted(draft_toks)[:40],
        "suspicious_tokens": sorted(suspicious)[:20],
        "cross_acu_leaks": leaked,
    }
    draft.concept_coverage = coverage

    # Score
    if actions:
        hit = sum(1 for a in actions if a in draft.draft_text or _action_phrase(a)[:2] in draft.draft_text)
        coverage["action_hit_ratio"] = hit / max(1, len(actions))

    if issues:
        draft.validation_status = "INVALID"
        draft.review_required = True
        draft.activation_eligible = False
    elif warnings:
        draft.validation_status = "VALID_WITH_WARNINGS"
        draft.review_required = False
        draft.activation_eligible = True
    else:
        draft.validation_status = "VALID"
        draft.review_required = False
        draft.activation_eligible = True
    draft.validation_issues = issues + [f"warn:{w}" for w in warnings]
    return draft


def generate_semantic_drafts(
    contracts: list[PatchContract],
    *,
    owner_target_texts: dict[str, str] | None = None,
) -> list[SemanticDraft]:
    """One draft attempt per contract; isolated (no cross-contract merge)."""
    owner_target_texts = owner_target_texts or {}
    # Build other-ACU concept sets for leakage checks
    concepts_by_acu: dict[str, set[str]] = {}
    for c in contracts:
        concepts_by_acu[c.atomic_change_id] = _contract_concepts(
            c.semantic_intent or {}, c.source_span
        )

    drafts: list[SemanticDraft] = []
    for c in contracts:
        owner_text = None
        rid = (c.target or {}).get("requirement_id") or c.owner_requirement_id
        if rid and rid in owner_target_texts:
            owner_text = owner_target_texts[rid]
        other: set[str] = set()
        for aid, concepts in concepts_by_acu.items():
            if aid != c.atomic_change_id:
                other |= concepts
        # Remove shared concepts that also appear in this contract
        other -= concepts_by_acu.get(c.atomic_change_id, set())
        d = generate_semantic_draft(c, owner_target_text=owner_text)
        d = validate_semantic_draft(d, contract=c, other_acu_concepts=other)
        drafts.append(d)
    return drafts


def validate_semantic_drafts(drafts: list[SemanticDraft]) -> dict[str, Any]:
    counts = {
        "VALID": 0,
        "VALID_WITH_WARNINGS": 0,
        "INVALID": 0,
        "REVIEW_REQUIRED": 0,
    }
    for d in drafts:
        st = d.validation_status
        if st in counts:
            counts[st] += 1
        else:
            counts["REVIEW_REQUIRED"] += 1
    return {
        "stage": "semantic_draft_validation",
        "total": len(drafts),
        **{k.lower(): v for k, v in counts.items()},
        "activation_eligible": sum(1 for d in drafts if d.activation_eligible),
        "entries": [
            {
                "draft_id": d.draft_id,
                "contract_id": d.contract_id,
                "atomic_change_id": d.atomic_change_id,
                "validation_status": d.validation_status,
                "validation_issues": list(d.validation_issues),
                "activation_eligible": d.activation_eligible,
                "generation_mode": d.generation_mode,
            }
            for d in drafts
        ],
        "note": "Shadow validation only — does not affect DOCX / legacy generation.",
    }


def compare_legacy_vs_semantic_drafts(
    *,
    legacy_generation_texts: list[str],
    drafts: list[SemanticDraft],
    whole_cr: str | None = None,
) -> dict[str, Any]:
    """Compare legacy whole-CR append texts vs shadow drafts (observational)."""
    legacy_blob = "\n".join(legacy_generation_texts)
    shadow_blob = "\n".join(d.draft_text for d in drafts if d.draft_text)
    whole_cr_used_by_legacy = bool(whole_cr and whole_cr.strip() and whole_cr.strip()[:40] in legacy_blob)
    whole_cr_used_by_shadow = bool(whole_cr and whole_cr.strip() and whole_cr.strip() == shadow_blob.strip())
    if whole_cr and any(d.draft_text.strip() == whole_cr.strip() for d in drafts):
        whole_cr_used_by_shadow = True

    return {
        "stage": "legacy_vs_semantic_draft",
        "legacy_generation_text": legacy_generation_texts,
        "shadow_semantic_drafts": [d.to_dict() for d in drafts],
        "whole_cr_used_by_legacy": whole_cr_used_by_legacy,
        "whole_cr_used_by_shadow": whole_cr_used_by_shadow,
        "target_ids": sorted(
            {
                str((d.target or {}).get("requirement_id") or "")
                for d in drafts
                if (d.target or {}).get("requirement_id")
            }
        ),
        "acu_coverage": sorted({d.atomic_change_id for d in drafts}),
        "activation_eligible": sum(1 for d in drafts if d.activation_eligible),
        "actual_generation_changed": False,
        "docx_changed": False,
        "note": "Shadow comparison only. Legacy whole-CR generation remains active.",
    }


def semantic_generation_summary(
    *,
    contracts: list[PatchContract],
    drafts: list[SemanticDraft],
) -> dict[str, Any]:
    return {
        "stage": "semantic_generation_summary",
        "contracts_total": len(contracts),
        "drafts_generated": sum(1 for d in drafts if d.draft_text),
        "valid": sum(1 for d in drafts if d.validation_status == "VALID"),
        "valid_with_warnings": sum(
            1 for d in drafts if d.validation_status == "VALID_WITH_WARNINGS"
        ),
        "invalid": sum(1 for d in drafts if d.validation_status == "INVALID"),
        "review_required": sum(
            1 for d in drafts if d.validation_status == "REVIEW_REQUIRED" or d.review_required
        ),
        "activation_eligible": sum(1 for d in drafts if d.activation_eligible),
        "actual_generation_changed": False,
        "docx_changed": False,
        "generation_modes": sorted({str(d.generation_mode) for d in drafts}),
        "note": "PR-10 shadow semantic generation — DOCX/legacy unchanged.",
    }


def semantic_drafts_to_trace_payload(drafts: list[SemanticDraft]) -> dict[str, Any]:
    return {
        "stage": "semantic_drafts_shadow",
        "schema_version": "semantic_draft_v1",
        "draft_count": len(drafts),
        "drafts": [d.to_dict() for d in drafts],
        "note": (
            "PR-10 shadow semantic drafts from Patch Contract. "
            "Not applied to DOCX; full CR is not a generator input."
        ),
    }
