# -*- coding: utf-8 -*-
"""B4v2: Domain-independent semantic consistency gate (pre-patch).

Question answered here:
  Can this CR be reflected into this existing Requirement by modify/extend
  without breaking the requirement's responsibility and meaning?

B3 selects IMPACTED candidates; B4 does not re-rank relevance.
B5 applies patches; B4 does not invent patch text beyond gate flags.

Does not read expected_impact.*.
Does not hard-code scenario Req IDs or scenario-specific keywords.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.semantic_index import RequirementBlock

ConsistencyStatus = Literal["CONSISTENT", "CONFLICT", "NEEDS_REVIEW"]

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")

STOPWORDS = {
    "그리고",
    "또는",
    "및",
    "등",
    "위해",
    "위한",
    "대한",
    "통해",
    "있는",
    "없는",
    "한다",
    "해야",
    "하도록",
    "경우",
    "관련",
    "기능",
    "요구",
    "사항",
    "설명",
    "목적",
    "기준",
    "설계",
    "구현",
    "제공",
    "수행",
    "사용",
    "가능",
    "있도록",
    "대하여",
    "에서는",
    "에서",
    "으로",
    "로서",
    "based",
    "the",
    "and",
    "for",
    "with",
    "변경",
    "요청",
    "반영",
}

# Generic software/requirements language — not auth/lockout decision bags.
ACTOR_MARKERS = (
    "사용자",
    "관리자",
    "운영자",
    "고객",
    "직원",
    "서버",
    "시스템",
    "클라이언트",
    "애플리케이션",
    "의료진",
    "환자",
    "개발자",
)

ACTION_MARKERS = (
    "조회",
    "표시",
    "안내",
    "알림",
    "메시지",
    "분류",
    "식별",
    "갱신",
    "생성",
    "삭제",
    "등록",
    "저장",
    "관리",
    "제한",
    "차단",
    "잠금",
    "해제",
    "승인",
    "검증",
    "기록",
    "추적",
    "감사",
    "전송",
    "동기화",
    "모니터링",
    "평가",
    "분석",
    "검색",
    "필터",
    "예약",
    "취소",
    "결제",
    "보고",
    "보충",
)

# Primary responsibility families (cross-domain). Used for compatibility / conflict,
# not as auth/lockout theme matchers.
FAMILY_MARKERS: dict[str, tuple[str, ...]] = {
    "inform": ("안내", "메시지", "오류", "에러", "표시", "알림", "clarity", "안내한다"),
    "enforce": ("제한", "차단", "잠금", "해제", "승인", "정책", "임계", "취소", "강제"),
    "audit": ("감사", "로그", "이벤트", "이력", "감사기록"),
    "observe": ("조회", "모니터링", "분석", "평가", "검색", "리포트", "보고", "현황"),
    "mutate": ("등록", "생성", "삭제", "저장", "갱신", "분류", "식별", "발급", "수정"),
    "manage": ("관리", "목록", "담당"),
}

# Families that may extend one another without contradiction.
COMPATIBLE_FAMILY_PAIRS: set[tuple[str, str]] = {
    ("enforce", "enforce"),
    ("audit", "audit"),
    ("observe", "observe"),
    ("mutate", "mutate"),
    ("manage", "manage"),
    ("inform", "inform"),
    ("observe", "mutate"),
    ("mutate", "observe"),
    ("observe", "manage"),
    ("manage", "observe"),
    ("manage", "mutate"),
    ("mutate", "manage"),
    ("enforce", "audit"),  # policy change often extends audit scope via CR clause
    ("audit", "enforce"),
    ("observe", "inform"),  # display/status surfacing
    ("inform", "observe"),
}

# Hard conflicts when CR primary family vs requirement title/purpose primary family.
CONFLICT_FAMILY_PAIRS: set[tuple[str, str]] = {
    ("enforce", "inform"),
    ("inform", "enforce"),
    ("mutate", "inform"),  # structural mutate vs message-only ownership (weak; gated by scores)
}


@dataclass
class FieldSnapshot:
    req_id: str
    document: str
    title: str
    description: str = ""
    purpose: str = ""
    criteria: str = ""
    constraints: str = ""
    traceability: list[str] = field(default_factory=list)
    body_full: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConsistencyEvidence:
    compatible_facets: list[str] = field(default_factory=list)
    conflicting_facets: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    cr_spans: list[str] = field(default_factory=list)
    candidate_spans: list[str] = field(default_factory=list)
    facet_detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible_facets": list(self.compatible_facets),
            "conflicting_facets": list(self.conflicting_facets),
            "missing_information": list(self.missing_information),
            "cr_spans": list(self.cr_spans),
            "candidate_spans": list(self.candidate_spans),
            "facet_detail": dict(self.facet_detail),
        }


@dataclass
class ConsistencyDecision:
    req_id: str
    document: str
    status: ConsistencyStatus
    reason: str
    conflict_evidence_spans: list[dict[str, str]] = field(default_factory=list)
    proposed_resolution_direction: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    cr_themes: dict[str, list[str]] = field(default_factory=dict)
    allow_auto_patch: bool = False
    b3_judgment: str = ""
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    b3_prior: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Harness / report shape
        d["candidate"] = self.req_id
        d["consistency"] = self.status
        return d


def parse_requirement_fields(block: RequirementBlock) -> FieldSnapshot:
    """Split MDSR-style 설명/목적/기준 from indexed body text."""
    body = block.body_text or ""
    title = block.title or ""
    parts = {"설명": "", "목적": "", "기준": ""}
    text = body
    if title and text.startswith(title):
        text = text[len(title) :].lstrip("\n")

    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in ("설명", "목적", "기준"):
            current = stripped
            continue
        if current:
            parts[current] = (parts[current] + "\n" + stripped).strip() if parts[current] else stripped

    if not any(parts.values()):
        parts["설명"] = body

    return FieldSnapshot(
        req_id=block.req_id,
        document=block.document_type,
        title=title,
        description=parts["설명"],
        purpose=parts["목적"],
        criteria=parts["기준"],
        constraints=parts["기준"],
        traceability=list(block.trace_security_ids or []),
        body_full=body,
    )


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]


def _token_set(text: str) -> set[str]:
    return set(_tokens(text))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _hits(text: str, markers: tuple[str, ...]) -> list[str]:
    return [m for m in markers if m in (text or "")]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[.\n。]+", text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 6]


def _spans_for(text: str, concepts: list[str], *, limit: int = 3) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for sent in _sentences(text):
        if not concepts or any(c in sent for c in concepts if len(c) >= 2):
            out.append(sent[:180])
        if len(out) >= limit:
            break
    if not out:
        out.append((text or "")[:180].replace("\n", " "))
    return out


def _family_scores(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for name, markers in FAMILY_MARKERS.items():
        hits = _hits(text, markers)
        if hits:
            scores[name] = float(len(hits))
    return scores


def _primary_family(scores: dict[str, float]) -> str | None:
    if not scores:
        return None
    return max(scores.items(), key=lambda kv: kv[1])[0]


def _extract_b3_prior(b3_decision: dict[str, Any] | None) -> dict[str, Any]:
    if not b3_decision:
        return {}
    raw_ev = b3_decision.get("evidence")
    ev: dict[str, Any] = raw_ev if isinstance(raw_ev, dict) else {}
    concepts = ev.get("matched_concepts")
    if not isinstance(concepts, list):
        concepts = raw_ev if isinstance(raw_ev, list) else []
    overlap = ev.get("behavioral_overlap") if isinstance(ev.get("behavioral_overlap"), dict) else {}
    return {
        "judgment": b3_decision.get("judgment") or b3_decision.get("b3_judgment") or "",
        "change_type": b3_decision.get("change_type") or "",
        "reason": b3_decision.get("reason") or "",
        "confidence": float(b3_decision.get("confidence") or 0.0),
        "cr_spans": list(ev.get("cr_spans") or []),
        "candidate_spans": list(ev.get("candidate_spans") or []),
        "matched_concepts": [c for c in concepts if isinstance(c, str)],
        "behavioral_overlap": dict(overlap),
    }


def _facet_sets(cr: str, req_core: str, req_full: str) -> dict[str, Any]:
    cr_actors = set(_hits(cr, ACTOR_MARKERS))
    req_actors = set(_hits(req_full, ACTOR_MARKERS))
    cr_actions = set(_hits(cr, ACTION_MARKERS))
    req_actions = set(_hits(req_full, ACTION_MARKERS))
    cr_toks = _token_set(cr)
    req_toks = _token_set(req_full)
    shared_toks = sorted(cr_toks & req_toks)
    # Objects ≈ content tokens minus actors/actions markers as tokens
    marker_toks = {m.lower() for m in ACTOR_MARKERS + ACTION_MARKERS}
    cr_obj = {t for t in cr_toks if t not in marker_toks and len(t) >= 2}
    req_obj = {t for t in req_toks if t not in marker_toks and len(t) >= 2}

    cr_cond = set(_hits(cr, ("경우", "때", "동안", "이후", "이상", "이하", "기준", "없으면")))
    req_cond = set(_hits(req_full, ("경우", "때", "동안", "이후", "이상", "이하", "기준", "없으면")))

    return {
        "actor_shared": sorted(cr_actors & req_actors),
        "actor_cr": sorted(cr_actors),
        "actor_req": sorted(req_actors),
        "action_shared": sorted(cr_actions & req_actions),
        "action_cr": sorted(cr_actions),
        "action_req": sorted(req_actions),
        "object_shared": sorted(cr_obj & req_obj)[:24],
        "object_jaccard": _jaccard(cr_obj, req_obj),
        "token_jaccard": _jaccard(cr_toks, req_toks),
        "shared_tokens": shared_toks[:24],
        "condition_shared": sorted(cr_cond & req_cond),
        "cr_families": _family_scores(cr),
        "req_core_families": _family_scores(req_core),
        "req_full_families": _family_scores(req_full),
    }


def check_consistency(
    cr_text: str,
    block: RequirementBlock,
    *,
    b3_judgment: str = "",
    b3_decision: dict[str, Any] | None = None,
) -> ConsistencyDecision:
    """Gate one IMPACTED candidate with domain-independent facet evidence."""
    fields = parse_requirement_fields(block)
    b3_prior = _extract_b3_prior(b3_decision)
    if b3_judgment and not b3_prior.get("judgment"):
        b3_prior["judgment"] = b3_judgment

    req_core = f"{fields.title}\n{fields.purpose}"
    req_full = f"{fields.title}\n{fields.description}\n{fields.purpose}\n{fields.criteria}"
    facets = _facet_sets(cr_text, req_core, req_full)

    cr_primary = _primary_family(facets["cr_families"])
    req_primary = _primary_family(facets["req_core_families"]) or _primary_family(facets["req_full_families"])

    compatible: list[str] = []
    conflicting: list[str] = []
    missing: list[str] = []

    # --- Actor ---
    if facets["actor_shared"]:
        compatible.append("actor")
    elif facets["actor_cr"] and facets["actor_req"]:
        conflicting.append("actor")
    elif facets["actor_cr"] and not facets["actor_req"]:
        missing.append("actor_in_requirement")

    # --- Action ---
    if facets["action_shared"]:
        compatible.append("action")
    elif facets["action_cr"] and facets["action_req"] and cr_primary and req_primary:
        if (cr_primary, req_primary) in CONFLICT_FAMILY_PAIRS:
            conflicting.append("action")
        elif (cr_primary, req_primary) in COMPATIBLE_FAMILY_PAIRS:
            compatible.append("action")
        else:
            missing.append("action_alignment")

    # --- Object / scope ---
    obj_j = float(facets["object_jaccard"])
    tok_j = float(facets["token_jaccard"])
    if obj_j >= 0.06 or len(facets["object_shared"]) >= 1:
        compatible.append("object")
    elif obj_j < 0.02 and tok_j < 0.04 and facets["shared_tokens"] and not facets["action_shared"]:
        # Weak lexical bleed without shared actions/objects → thematic neighbor risk
        conflicting.append("object")
    elif obj_j < 0.03 and not facets["object_shared"] and not facets["action_shared"]:
        missing.append("object_overlap")

    # --- Condition ---
    if facets["condition_shared"]:
        compatible.append("condition")
    elif any(k in (cr_text or "") for k in ("경우", "때", "동안", "기준")) and not facets["condition_shared"]:
        if "condition" not in compatible:
            missing.append("condition_mapping")

    # --- Constraint / contradiction from criteria silence vs CR novelty ---
    cr_novel = sorted(_token_set(cr_text) - _token_set(req_full))
    if fields.criteria and cr_novel and "constraint" not in conflicting:
        # Criteria exist; novelty alone is extension, not conflict
        compatible.append("constraint")
    elif not (fields.criteria or fields.description):
        missing.append("requirement_fields")

    # --- Responsibility / family ---
    responsibility_conflict = False
    responsibility_compatible = False
    if cr_primary and req_primary:
        if (cr_primary, req_primary) in CONFLICT_FAMILY_PAIRS:
            # Title/purpose inform vs CR enforce is the classic inconsistent ownership pattern
            if req_primary == "inform" and cr_primary == "enforce":
                responsibility_conflict = True
                conflicting.append("responsibility")
            elif req_primary == "enforce" and cr_primary == "inform":
                # CR only adds guidance under policy req — usually extendable; not hard conflict
                responsibility_compatible = True
                compatible.append("responsibility")
            else:
                responsibility_conflict = True
                conflicting.append("responsibility")
        elif (cr_primary, req_primary) in COMPATIBLE_FAMILY_PAIRS or cr_primary == req_primary:
            responsibility_compatible = True
            compatible.append("responsibility")
        else:
            missing.append("responsibility_clarity")
    else:
        missing.append("responsibility_signals")

    # --- B3 prior as supporting (never decisive alone) ---
    b3_concepts = [c for c in (b3_prior.get("matched_concepts") or []) if isinstance(c, str)]
    b3_overlap = b3_prior.get("behavioral_overlap") or {}
    if isinstance(b3_overlap, dict) and b3_overlap:
        for k in ("actor", "action", "object", "output", "condition"):
            if b3_overlap.get(k) and k not in compatible and k not in conflicting:
                compatible.append(f"b3_prior_{k}")

    # Spans: prefer B3 spans when present; else derive
    cr_spans = list(b3_prior.get("cr_spans") or []) or _spans_for(cr_text, b3_concepts or facets["shared_tokens"])
    cand_spans = list(b3_prior.get("candidate_spans") or []) or _spans_for(
        req_full, b3_concepts or facets["shared_tokens"]
    )

    # Evidence strength (informational confidence — not sole CONSISTENT trigger)
    strength = 0.0
    strength += 0.18 * len([f for f in compatible if not f.startswith("b3_prior_")])
    strength += 0.08 * min(3, len(b3_concepts))
    strength += 0.25 * min(1.0, obj_j / 0.15)
    strength += 0.15 * min(1.0, tok_j / 0.12)
    if responsibility_compatible:
        strength += 0.2
    if responsibility_conflict:
        strength -= 0.35
    strength -= 0.12 * len([f for f in conflicting if f != "responsibility"])
    confidence = max(0.0, min(0.99, strength))

    evidence = ConsistencyEvidence(
        compatible_facets=sorted(set(compatible)),
        conflicting_facets=sorted(set(conflicting)),
        missing_information=sorted(set(missing)),
        cr_spans=cr_spans[:4],
        candidate_spans=cand_spans[:4],
        facet_detail={
            "cr_primary_family": cr_primary,
            "req_primary_family": req_primary,
            "object_jaccard": round(obj_j, 4),
            "token_jaccard": round(tok_j, 4),
            "shared_tokens": facets["shared_tokens"][:12],
            "actor_shared": facets["actor_shared"],
            "action_shared": facets["action_shared"],
            "object_shared": facets["object_shared"][:12],
        },
    )

    legacy_spans: list[dict[str, str]] = []
    for label, span in (("change_request", (cr_spans[0] if cr_spans else cr_text[:160])),):
        legacy_spans.append({"field": label, "span": span[:200], "note": "CR span used in consistency check"})
    for span in cand_spans[:2]:
        legacy_spans.append({"field": "requirement", "span": span[:200], "note": "Candidate span"})

    core_compatible = [f for f in evidence.compatible_facets if not f.startswith("b3_prior_")]
    hard_conflict = "responsibility" in evidence.conflicting_facets or (
        "action" in evidence.conflicting_facets and "object" in evidence.conflicting_facets
    )
    thematic_neighbor = (
        not responsibility_compatible
        and "responsibility" not in core_compatible
        and obj_j < 0.05
        and tok_j < 0.08
        and (
            "object" in evidence.conflicting_facets
            or "object_overlap" in evidence.missing_information
            or (not facets["action_shared"] and not facets["actor_shared"])
        )
    )

    # Decision (evidence-first; confidence never sole CONSISTENT trigger)
    if hard_conflict or (
        responsibility_conflict and ("action" in evidence.conflicting_facets or req_primary == "inform")
    ):
        status: ConsistencyStatus = "CONFLICT"
        reason = (
            f"Responsibility/action conflict: CR primary={cr_primary}, requirement primary={req_primary}; "
            f"conflicting_facets={evidence.conflicting_facets}. "
            f"Applying CR would break existing ownership/meaning."
        )
        resolution = (
            "Do not auto-patch. Keep existing responsibility owner; route CR to a compatible "
            "requirement or open NEW_REQUIREMENT / human review."
        )
        allow = False
    elif thematic_neighbor and "responsibility" not in core_compatible:
        # Sparse / vague CR → review; stronger neighbor bleed → conflict (B3 FP defense)
        cr_tok_n = len(_tokens(cr_text))
        if cr_tok_n < 6 or "responsibility_signals" in evidence.missing_information:
            status = "NEEDS_REVIEW"
            reason = (
                "Insufficient information to confirm modify/extend applicability; "
                f"compatible={evidence.compatible_facets}, missing={evidence.missing_information}."
            )
            resolution = "Human review before any patch."
            allow = False
        else:
            status = "CONFLICT"
            reason = (
                "Thematic neighbor / responsibility mismatch: shared lexical bleed without compatible "
                f"object/responsibility facets (object_j={obj_j:.3f}, token_j={tok_j:.3f})."
            )
            resolution = (
                "Treat as false-positive IMPACTED for patching; human review or different owner Req."
            )
            allow = False
    elif (
        responsibility_compatible
        and len(core_compatible) >= 2
        and "responsibility" in core_compatible
        and not evidence.conflicting_facets
        and len(evidence.missing_information) <= 2
        and (obj_j >= 0.04 or tok_j >= 0.06 or len(facets["object_shared"]) >= 1 or facets["action_shared"])
    ):
        status = "CONSISTENT"
        reason = (
            f"Compatible modify/extend: primary families CR={cr_primary}/Req={req_primary}; "
            f"compatible_facets={core_compatible}; no conflicting facets."
        )
        resolution = "Auto-patch may proceed subject to B5 design alignment."
        allow = True
    elif (
        responsibility_compatible
        and not evidence.conflicting_facets
        and len(core_compatible) >= 1
        and (obj_j >= 0.06 or tok_j >= 0.08 or facets["action_shared"] or facets["actor_shared"])
    ):
        # Natural extension with thinner overlap — still CONSISTENT when responsibility aligns
        status = "CONSISTENT"
        reason = (
            f"Scope extension compatible with existing responsibility ({req_primary}); "
            f"compatible_facets={core_compatible}."
        )
        resolution = "Extend description/criteria carefully; B5 applies patch text."
        allow = True
    else:
        status = "NEEDS_REVIEW"
        reason = (
            "Insufficient facet evidence to prove safe modify/extend or a hard conflict; "
            f"compatible={evidence.compatible_facets}, conflicting={evidence.conflicting_facets}, "
            f"missing={evidence.missing_information}."
        )
        resolution = "Human review before any patch."
        allow = False

    # Defensive: never CONSISTENT on confidence alone / empty evidence
    if status == "CONSISTENT" and not core_compatible:
        status = "NEEDS_REVIEW"
        allow = False
        reason = "Rejected CONSISTENT without core compatible facets (confidence alone insufficient)."
        resolution = "Human review before any patch."

    themes = {
        "cr_primary": [cr_primary] if cr_primary else [],
        "req_primary": [req_primary] if req_primary else [],
        "compatible": core_compatible,
        "conflicting": list(evidence.conflicting_facets),
    }

    return ConsistencyDecision(
        req_id=block.req_id,
        document=block.document_type,
        status=status,
        reason=reason,
        conflict_evidence_spans=legacy_spans,
        proposed_resolution_direction=resolution,
        fields=fields.to_dict(),
        cr_themes=themes,
        allow_auto_patch=allow and status == "CONSISTENT",
        b3_judgment=str(b3_prior.get("judgment") or b3_judgment or ""),
        confidence=confidence,
        evidence=evidence.to_dict(),
        b3_prior=b3_prior,
    )


def gate_impacted_decisions(
    cr_text: str,
    blocks: list[RequirementBlock],
    b3_decisions: list[dict[str, Any]],
    *,
    focus_ids: set[str] | None = None,
) -> list[ConsistencyDecision]:
    """Run B4 on B3 IMPACTED items, forwarding B3 evidence as prior."""
    by_key = {(b.req_id, b.document_type): b for b in blocks}
    out: list[ConsistencyDecision] = []
    seen: set[tuple[str, str]] = set()

    for d in b3_decisions:
        if d.get("judgment") != "IMPACTED":
            continue
        rid = d.get("candidate_id") or d.get("candidate")
        doc = d.get("document")
        if not rid or not doc:
            continue
        if doc != "MDSR":
            continue
        block = by_key.get((rid, doc))
        if not block:
            out.append(
                ConsistencyDecision(
                    req_id=rid,
                    document=doc,
                    status="NEEDS_REVIEW",
                    reason="Block missing from index; cannot validate consistency.",
                    allow_auto_patch=False,
                    b3_judgment="IMPACTED",
                    evidence={
                        "compatible_facets": [],
                        "conflicting_facets": [],
                        "missing_information": ["indexed_block"],
                        "cr_spans": [],
                        "candidate_spans": [],
                    },
                    b3_prior=_extract_b3_prior(d),
                )
            )
            seen.add((rid, doc))
            continue
        out.append(
            check_consistency(
                cr_text,
                block,
                b3_judgment="IMPACTED",
                b3_decision=d,
            )
        )
        seen.add((rid, doc))

    if focus_ids:
        for rid in sorted(focus_ids):
            if (rid, "MDSR") in seen:
                continue
            block = by_key.get((rid, "MDSR"))
            if block:
                out.append(
                    check_consistency(
                        cr_text,
                        block,
                        b3_judgment="(focus_complement)",
                        b3_decision={"judgment": "(focus_complement)"},
                    )
                )
    return out


# ---------------------------------------------------------------------------
# Legacy lockout theme helpers — ISOLATED, not used by B4v2 core decisions.
# Kept only for reference / optional diagnostics; must not dominate gating.
# ---------------------------------------------------------------------------

_LEGACY_POLICY_TERMS = (
    "계정 잠금",
    "잠금",
    "자동 해제",
    "관리자 승인",
    "임계",
    "연속 로그인 실패",
    "로그인 시도 제한",
)
_LEGACY_UX_TERMS = ("사용자", "안내", "알림", "재시도", "에러", "오류", "메시지")
_LEGACY_AUDIT_TERMS = ("감사", "감사 기록", "감사기록", "이벤트")


def legacy_lockout_theme_hits(cr_text: str) -> dict[str, list[str]]:
    """Diagnostic-only lockout theme bag (not part of B4v2 decision path)."""
    return {
        "policy": [t for t in _LEGACY_POLICY_TERMS if t in (cr_text or "")],
        "ux": [t for t in _LEGACY_UX_TERMS if t in (cr_text or "")],
        "audit": [t for t in _LEGACY_AUDIT_TERMS if t in (cr_text or "")],
    }
