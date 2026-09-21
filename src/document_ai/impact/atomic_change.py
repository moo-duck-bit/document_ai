# -*- coding: utf-8 -*-
"""Atomic Change Unit (ACU) decomposition — PR-4 MV + PR-7 semantic integrity.

PR-4: observational / trace layer (shadow-ready).
PR-7: ACU Semantic Integrity & Scope Isolation (still shadow-only for owner/DOCX).

- Does NOT feed actual B3/B4/B5 decisions
- Does NOT change whole-CR patch text generation
- Facets for semantic_intent come from ACU_DIRECT span only
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.evidence_provenance import (
    independent_group_for_span,
    make_evidence_id,
)

DecompositionStatus = Literal["EXTRACTED", "AMBIGUOUS", "NEEDS_REVIEW"]
FacetOrigin = Literal["ACU_DIRECT", "CR_CONTEXT", "DERIVED_PRIOR"]

# Domain-independent role markers (not Scenario keyword ownership lists).
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
    "대기자",
    "구독자",
)

# (surface_stem, canonical_action) — stems catch conjugations
ACTION_STEMS: tuple[tuple[str, str], ...] = (
    ("조회", "조회"),
    ("표시", "표시"),
    ("안내", "안내"),
    ("알림", "알림"),
    ("알린", "알림"),
    ("알리", "알림"),
    ("메시지", "메시지"),
    ("분류", "분류"),
    ("식별", "식별"),
    ("갱신", "갱신"),
    ("바꾸", "갱신"),
    ("바꾼", "갱신"),
    ("바꿨", "갱신"),
    ("바꿉", "갱신"),
    ("변경", "갱신"),
    ("생성", "생성"),
    ("삭제", "삭제"),
    ("등록", "등록"),
    ("저장", "저장"),
    ("관리", "관리"),
    ("제한", "제한"),
    ("차단", "차단"),
    ("잠그", "잠금"),  # 잠그고 / 잠근다
    ("잠금", "잠금"),
    ("해제", "해제"),
    ("승인", "승인"),
    ("검증", "검증"),
    ("남기", "기록"),  # 남겨야 / 남긴다
    ("기록", "기록"),
    ("추적", "추적"),
    ("감사", "감사"),
    ("전송", "전송"),
    ("보내", "전송"),
    ("동기화", "동기화"),
    ("모니터링", "모니터링"),
    ("평가", "평가"),
    ("분석", "분석"),
    ("검색", "검색"),
    ("필터", "필터"),
    ("예약", "예약"),
    ("취소", "취소"),
    ("결제", "결제"),
    ("보고", "보고"),
    ("보충", "보충"),
    ("다운로드", "다운로드"),
    ("통지", "알림"),
    ("공지", "알림"),
    ("지원", "지원"),
    ("강화", "강화"),
)

# Noun-compound continuations: stem is an object mention, not a verbal action.
ACTION_NOUN_COMPOUND_SUFFIXES: dict[str, tuple[str, ...]] = {
    "잠금": ("상태", "해제", "이벤트", "여부", "시각", "시간", "정책"),
    "해제": ("이벤트", "시각", "시간", "정책", "절차"),
    "보고": ("서",),  # 보고서
}

OUTPUT_MARKERS = (
    "화면",
    "목록",
    "리포트",
    "보고서",
    "메시지",
    "상태",
    "API",
    "로그",
    "요청",
    "감사 기록",
    "감사기록",
)

# Markers that must not match as a prefix of a longer token (로그인 ⊃ 로그).
OUTPUT_PREFIX_BLOCK: dict[str, tuple[str, ...]] = {
    "로그": ("인", "오프"),
}

CONDITION_CUES = (
    "이면",
    "경우",
    "때",
    "동안",
    "이후",
    "이상",
    "이하",
    "초과",
    "미만",
    "없으면",
    "시 ",
    "시,",
    " 시 ",
)

CONSTRAINT_CUES = (
    "자동",
    "필수",
    "금지",
    "허용",
    "제한",
    "최대",
    "최소",
    "또는",
    "중 하나",
)

OBJECT_HINTS = (
    "재고",
    "요청",
    "좌석",
    "예약",
    "보고서",
    "상태",
    "대상",
    "계정",
    "데이터",
    "문서",
    "코드",
    "권한",
    "기록",
    "환자",
    "이벤트",
    "알림",
    "발주",
    "보고서",
)

AFFECTED_ENTITY_HINTS = (
    "계정",
    "좌석",
    "재고",
    "예약",
    "상태",
    "권한",
    "세션",
    "사용자",
)

NOTIFY_ACTIONS = frozenset({"알림", "안내", "전송", "메시지", "통지", "공지"})
STATE_ACTIONS = frozenset({"잠금", "해제", "갱신", "취소", "차단", "제한", "승인"})
RECORD_ACTIONS = frozenset({"기록", "감사", "추적"})

RESPONSIBILITY_BY_ACTION: dict[str, str] = {
    "분류": "classify",
    "식별": "classify",
    "표시": "display",
    "안내": "display",
    "조회": "display",
    "다운로드": "display",
    "갱신": "update",
    "동기화": "update",
    "제한": "enforce",
    "차단": "enforce",
    "잠금": "enforce",
    "해제": "enforce",
    "승인": "enforce",
    "검증": "enforce",
    "지원": "enforce",
    "기록": "audit",
    "추적": "audit",
    "감사": "audit",
    "생성": "other",
    "삭제": "other",
    "등록": "other",
    "저장": "other",
    "전송": "other",
    "알림": "other",
    "메시지": "other",
    "관리": "other",
    "보충": "other",
    "취소": "other",
    "결제": "other",
    "보고": "other",
    "예약": "other",
    "검색": "other",
    "필터": "other",
    "모니터링": "other",
    "평가": "other",
    "분석": "other",
    "강화": "other",
}

CLAUSE_SPLIT_RE = re.compile(
    r"(?:하고|하며|고(?=\s)|그리고|,|\s및\s)"
)
# Also split soft sentence joins that keep independent responsibilities
SOFT_SENTENCE_JOIN_RE = re.compile(r"(?<=며),\s*|(?<=고),\s*")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.\n。])\s*|\n+")

RECIPIENT_CASE_RE = re.compile(
    r"(" + "|".join(re.escape(a) for a in ACTOR_MARKERS) + r")(?:에게는|한테는|에게|한테|께)"
)
SUBJECT_CASE_RE = re.compile(
    r"(" + "|".join(re.escape(a) for a in ACTOR_MARKERS) + r")(?:께서는|께서|이|가|은|는)"
)

IMPLICIT_SYSTEM = "implicit_system"


@dataclass
class FacetValue:
    """Scoped facet with origin — ACU_DIRECT is the only default for semantic_intent."""

    value: str
    origin: FacetOrigin | str = "ACU_DIRECT"
    source_span: str = ""
    evidence_id: str | None = None
    role: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AtomicResponsibility:
    """Optional sub-responsibility (backward-compatible companion to flat ACU lists)."""

    responsibility_id: str
    actor: str | None
    action: str
    object: list[str] = field(default_factory=list)
    recipient: str | None = None
    affected_entity: list[str] = field(default_factory=list)
    condition: str | None = None
    output: list[str] = field(default_factory=list)
    source_span: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AtomicChangeUnit:
    change_id: str
    source_span: str
    actor: list[str] = field(default_factory=list)
    action: list[str] = field(default_factory=list)
    object: list[str] = field(default_factory=list)
    condition: list[str] = field(default_factory=list)
    constraint: list[str] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    # PR-7 role fields (lists for multi-value; empty = unset)
    recipient: list[str] = field(default_factory=list)
    affected_entity: list[str] = field(default_factory=list)
    responsibility_type: str = "other"
    provenance: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    decomposition_status: DecompositionStatus | str = "EXTRACTED"
    # PR-7: facet origins + optional responsibility groups
    facet_origins: list[dict[str, Any]] = field(default_factory=list)
    responsibilities: list[dict[str, Any]] = field(default_factory=list)
    split_parent_id: str | None = None
    ambiguity_reason: str | None = None
    supporting_context: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def direct_facet_values(self, role: str) -> list[str]:
        vals = [
            f["value"]
            for f in self.facet_origins
            if f.get("role") == role and f.get("origin") == "ACU_DIRECT"
        ]
        if vals:
            return vals
        # Fallback to flat fields (already span-scoped by construction)
        return list(getattr(self, role, []) or [])


def _cr_hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


def _hits(text: str, markers: tuple[str, ...]) -> list[str]:
    return [m for m in markers if m in (text or "")]


def _output_hits(text: str) -> list[str]:
    out: list[str] = []
    t = text or ""
    for m in OUTPUT_MARKERS:
        start = 0
        while True:
            idx = t.find(m, start)
            if idx < 0:
                break
            blocked = False
            for suffix in OUTPUT_PREFIX_BLOCK.get(m, ()):
                if t[idx + len(m) :].startswith(suffix):
                    blocked = True
                    break
            if not blocked and m not in out:
                out.append(m)
            start = idx + len(m)
    return out


# Stems that are often noun objects when followed by 을/를 + another verb
OBJECTISH_ACTION_CANONICALS = frozenset(
    {"예약", "요청", "보고", "결제", "검색", "필터", "평가", "분석"}
)


def _is_noun_compound_action(text: str, idx: int, stem: str, canonical: str) -> bool:
    """True when stem is part of a noun compound (e.g. 잠금 상태), not a verbal action."""
    rest = (text or "")[idx + len(stem) :]
    rest_stripped = rest.lstrip()
    for suf in ACTION_NOUN_COMPOUND_SUFFIXES.get(canonical, ()):
        if rest_stripped.startswith(suf):
            return True
    # Object particle after object-ish stem: "예약을 취소" — 예약 is object
    if (
        canonical in OBJECTISH_ACTION_CANONICALS
        and rest_stripped.startswith(("을", "를"))
    ):
        after = (text or "")[idx + len(stem) :]
        if _action_hits_raw(after, skip_idx=None, skip_stem=None):
            return True
    # Event enumeration: "계정 잠금·잠금 해제 이벤트"
    if canonical in ("잠금", "해제") and "이벤트" in (text or "")[max(0, idx - 12) : idx + 24]:
        return True
    return False


def _action_hits_raw(
    text: str, *, skip_idx: int | None = None, skip_stem: str | None = None
) -> list[str]:
    """Internal action scan without noun-compound demotion (cycle-safe helper)."""
    found: list[str] = []
    t = text or ""
    for stem, canonical in ACTION_STEMS:
        start = 0
        while True:
            idx = t.find(stem, start)
            if idx < 0:
                break
            if skip_idx is not None and idx == skip_idx and stem == skip_stem:
                start = idx + len(stem)
                continue
            if any(
                t.startswith(actor, idx) and len(actor) > len(stem)
                for actor in ACTOR_MARKERS
            ):
                start = idx + len(stem)
                continue
            # light compound suffix check only (no recursion into object-particle)
            rest = t[idx + len(stem) :].lstrip()
            if any(rest.startswith(suf) for suf in ACTION_NOUN_COMPOUND_SUFFIXES.get(canonical, ())):
                start = idx + len(stem)
                continue
            if canonical not in found:
                found.append(canonical)
            start = idx + len(stem)
    return found


def _action_hits(text: str, *, allow_noun_compound: bool = False) -> list[str]:
    """Return canonical actions in left-to-right order (deduped)."""
    found: list[tuple[int, str]] = []
    t = text or ""
    for stem, canonical in ACTION_STEMS:
        start = 0
        while True:
            idx = t.find(stem, start)
            if idx < 0:
                break
            # Skip action stem embedded in a longer actor mention (관리 ⊂ 관리자)
            if any(
                t.startswith(actor, idx) and len(actor) > len(stem)
                for actor in ACTOR_MARKERS
            ):
                start = idx + len(stem)
                continue
            if not allow_noun_compound and _is_noun_compound_action(t, idx, stem, canonical):
                start = idx + len(stem)
                continue
            found.append((idx, canonical))
            start = idx + len(stem)
    found.sort(key=lambda x: x[0])
    out: list[str] = []
    for _, canonical in found:
        if canonical not in out:
            out.append(canonical)
    return out


def _primary_actions(text: str) -> list[str]:
    """Prefer verbal / responsibility actions; drop meta wrappers when others exist."""
    actions = _action_hits(text)
    if not actions:
        return []
    # Drop meta "강화" when other concrete actions exist
    if "강화" in actions and len(actions) > 1:
        actions = [a for a in actions if a != "강화"]
    # Prefer record over embedded lock/unlock nouns if 기록/감사 present
    if any(a in RECORD_ACTIONS for a in actions):
        filtered = [a for a in actions if a in RECORD_ACTIONS or a not in STATE_ACTIONS]
        if filtered:
            actions = filtered
    # Prefer notify stem over bare 전송 when 알림 surface present
    if "알림" in (text or "") and "전송" in actions and "알림" in actions:
        actions = [a for a in actions if a != "전송"]
    elif "알림" in (text or "") and "전송" in actions and "알림" not in actions:
        actions = [("알림" if a == "전송" else a) for a in actions]
    return actions


def _responsibility_type(actions: list[str]) -> str:
    types = [RESPONSIBILITY_BY_ACTION.get(a, "other") for a in actions]
    if not types:
        return "other"
    for t in types:
        if t != "other":
            return t
    return types[0]


def _extract_condition_phrases(text: str) -> list[str]:
    out: list[str] = []
    for cue in CONDITION_CUES:
        if cue not in (text or ""):
            continue
        idx = text.find(cue)
        start = max(0, idx - 24)
        phrase = text[start : idx + len(cue)].strip()
        if phrase and phrase not in out:
            out.append(phrase[:80])
    return out


def _extract_objects(text: str) -> list[str]:
    return _hits(text, OBJECT_HINTS)


def _extract_affected(text: str, actions: list[str]) -> list[str]:
    if not any(a in STATE_ACTIONS or a in RECORD_ACTIONS for a in actions):
        # Still allow explicit entity hints in span for notify-about-X
        if any(a in NOTIFY_ACTIONS for a in actions):
            return [h for h in AFFECTED_ENTITY_HINTS if h in (text or "") and h != "사용자"]
        return []
    return [h for h in AFFECTED_ENTITY_HINTS if h in (text or "")]


def _extract_constraints(text: str) -> list[str]:
    return _hits(text, CONSTRAINT_CUES)


def _extract_recipients(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(1) for m in RECIPIENT_CASE_RE.finditer(text or "")))


def _extract_subject_actors(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(1) for m in SUBJECT_CASE_RE.finditer(text or "")))


def _resolve_roles(
    text: str,
    actions: list[str],
    *,
    carry_actors: list[str] | None = None,
) -> tuple[list[str], list[str], str | None]:
    """Return (actors, recipients, actor_note).

    Recipient case markers never become actors.
    Missing subject + software-like action → implicit_system (not AMBIGUOUS alone).
    """
    recipients = _extract_recipients(text)
    subjects = _extract_subject_actors(text)
    # Bare markers that are neither subject nor recipient
    bare = [
        m
        for m in _hits(text, ACTOR_MARKERS)
        if m not in recipients and m not in subjects
    ]
    actors: list[str] = list(subjects)
    note: str | None = None

    # Notify/inform: bare person markers near notify tend to be recipients
    if any(a in NOTIFY_ACTIONS for a in actions):
        for b in bare:
            if b not in recipients and b != "시스템":
                recipients.append(b)
        bare = [b for b in bare if b == "시스템"]

    for b in bare:
        if b == "시스템" and b not in actors:
            actors.append(b)

    if not actors:
        if carry_actors:
            # Only inherit when prior was an explicit subject actor, not a recipient
            inherited = [a for a in carry_actors if a != IMPLICIT_SYSTEM]
            if inherited and not recipients:
                actors = list(inherited)
                note = "inherited_from_prior_acu"
            else:
                actors = [IMPLICIT_SYSTEM]
                note = "implicit_system"
        else:
            actors = [IMPLICIT_SYSTEM]
            note = "implicit_system"

    # Never keep recipient in actor list
    actors = [a for a in actors if a not in recipients]
    if not actors:
        actors = [IMPLICIT_SYSTEM]
        note = note or "implicit_system"

    return actors, list(dict.fromkeys(recipients)), note


def _split_sentences(cr_text: str) -> list[str]:
    raw = (cr_text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in SENTENCE_SPLIT_RE.split(raw) if p and p.strip()]
    # Further split soft joins that glue independent responsibilities
    expanded: list[str] = []
    for p in parts if parts else [raw]:
        soft = [s.strip() for s in SOFT_SENTENCE_JOIN_RE.split(p) if s and s.strip()]
        expanded.extend(soft if soft else [p])
    return expanded if expanded else [raw]


def _split_clauses(sentence: str) -> list[str]:
    parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(sentence) if p and p.strip()]
    return parts if parts else [sentence.strip()]


def _span_offsets(full: str, span: str) -> tuple[int, int]:
    idx = (full or "").find(span)
    if idx < 0:
        # try whitespace-normalized search
        norm_full = " ".join((full or "").split())
        norm_span = " ".join((span or "").split())
        idx2 = norm_full.find(norm_span)
        if idx2 >= 0:
            return idx2, idx2 + len(norm_span)
        return 0, min(len(full or ""), len(span or ""))
    return idx, idx + len(span)


def _facet(
    role: str,
    value: str,
    span: str,
    *,
    origin: FacetOrigin = "ACU_DIRECT",
    evidence_id: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "origin": origin,
        "source_span": span,
        "evidence_id": evidence_id,
        "role": role,
    }


def _build_facet_origins(
    *,
    span: str,
    eid: str,
    actors: list[str],
    actions: list[str],
    objects: list[str],
    recipients: list[str],
    affected: list[str],
    conditions: list[str],
    constraints: list[str],
    outputs: list[str],
    inherit_actors: list[str] | None = None,
) -> list[dict[str, Any]]:
    facets: list[dict[str, Any]] = []
    inherited = set(inherit_actors or [])
    for role, values in (
        ("actor", actors),
        ("action", actions),
        ("object", objects),
        ("recipient", recipients),
        ("affected_entity", affected),
        ("condition", conditions),
        ("constraint", constraints),
        ("output", outputs),
    ):
        for v in values:
            origin: FacetOrigin = "ACU_DIRECT"
            if role == "actor" and v in inherited and v not in (span or ""):
                # Discourse carry from prior clause — not cross-ACU leakage
                origin = "CR_CONTEXT"
            elif v != IMPLICIT_SYSTEM and role != "action":
                if v not in span and v not in inherited:
                    continue
            if role == "action":
                if not _action_justified_in_span(span, v):
                    continue
            facets.append(
                _facet(role, v, span, origin=origin, evidence_id=eid)
            )
    return facets


def _action_justified_in_span(span: str, canonical: str) -> bool:
    for stem, can in ACTION_STEMS:
        if can == canonical and stem in (span or ""):
            if not _is_noun_compound_action(span, span.find(stem), stem, canonical):
                return True
            # allow if primary_actions still kept it
    return canonical in _primary_actions(span)


def _filter_to_span(
    values: list[str],
    span: str,
    *,
    allow_synthetic: tuple[str, ...] = (),
    allow_extra: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    allowed = set(allow_synthetic) | set(allow_extra or ())
    out: list[str] = []
    for v in values:
        if v in allowed or v in (span or ""):
            out.append(v)
    return out


def _build_unit(
    *,
    change_id: str,
    span: str,
    full_cr: str,
    actors: list[str],
    actions: list[str],
    recipients: list[str] | None = None,
    status: DecompositionStatus,
    confidence: float,
    method: str,
    carry_note: str | None = None,
    split_parent_id: str | None = None,
    ambiguity_reason: str | None = None,
    parent_sentence: str | None = None,
    pending_conditions: list[str] | None = None,
) -> AtomicChangeUnit:
    gid = independent_group_for_span(span)
    eid = make_evidence_id(
        source_type="CR_DIRECT",
        facet="acu",
        concept=change_id,
        independent_group=gid,
        stage="ACU",
    )
    start, end = _span_offsets(full_cr, span)
    recipients = list(recipients or [])
    objects = _filter_to_span(_extract_objects(span), span)
    affected = _filter_to_span(_extract_affected(span, actions), span)
    conditions = list(dict.fromkeys((pending_conditions or []) + _extract_condition_phrases(span)))
    # Keep pending conditions from same parent sentence even if window text differs slightly
    constraints = _extract_constraints(span)
    outputs = _output_hits(span)

    inherit_extra = (
        tuple(a for a in actors if a != IMPLICIT_SYSTEM)
        if carry_note == "inherited_from_prior_acu"
        else ()
    )
    actors = _filter_to_span(
        actors, span, allow_synthetic=(IMPLICIT_SYSTEM,), allow_extra=inherit_extra
    )
    recipients = _filter_to_span(recipients, span)

    facets = _build_facet_origins(
        span=span,
        eid=eid,
        actors=actors,
        actions=actions,
        objects=objects,
        recipients=recipients,
        affected=affected,
        conditions=[c for c in conditions if c in span or c in (parent_sentence or "")],
        constraints=constraints,
        outputs=outputs,
        inherit_actors=list(inherit_extra),
    )
    # Re-sync flat lists from ACU_DIRECT facets primarily
    def _from_facets(role: str, fallback: list[str]) -> list[str]:
        vals = [f["value"] for f in facets if f["role"] == role]
        return vals if vals else fallback

    actors_f = _from_facets("actor", actors)
    actions_f = _from_facets("action", actions)
    objects_f = _from_facets("object", objects)
    recipients_f = _from_facets("recipient", recipients)
    affected_f = _from_facets("affected_entity", affected)
    conditions_f = _from_facets("condition", [c for c in conditions if c in span])
    constraints_f = _from_facets("constraint", constraints)
    outputs_f = _from_facets("output", outputs)

    # Supporting CR_CONTEXT (not used in semantic_intent): markers in full CR absent from span
    supporting: list[dict[str, Any]] = []
    for m in _output_hits(full_cr):
        if m not in span:
            supporting.append(
                _facet("output", m, full_cr, origin="CR_CONTEXT", evidence_id=eid)
            )

    resp = AtomicResponsibility(
        responsibility_id=f"{change_id}-R1",
        actor=actors_f[0] if actors_f else None,
        action=actions_f[0] if actions_f else "",
        object=list(objects_f),
        recipient=recipients_f[0] if recipients_f else None,
        affected_entity=list(affected_f),
        condition=conditions_f[0] if conditions_f else None,
        output=list(outputs_f),
        source_span=span,
    )

    prov: dict[str, Any] = {
        "cr_hash": _cr_hash(full_cr),
        "span_start": start,
        "span_end": end,
        "source_start": start,
        "source_end": end,
        "source_offsets": {"start": start, "end": end},
        "decomposition_method": method,
        "independent_group": gid,
        "evidence_ids": [eid],
        "parent_sentence_id": hashlib.sha1(
            (parent_sentence or span).encode("utf-8")
        ).hexdigest()[:12],
        "parent_change_request_id": _cr_hash(full_cr),
        "split_parent_id": split_parent_id,
        "path": "shadow_trace_only",
        "schema_version": "acu_v2",
        "note": (
            "PR-7 ACU semantic integrity — still does not replace whole-CR patching."
        ),
    }
    if carry_note:
        prov["actor_carry_over"] = carry_note
    if ambiguity_reason:
        prov["ambiguity_reason"] = ambiguity_reason

    return AtomicChangeUnit(
        change_id=change_id,
        source_span=span,
        actor=actors_f,
        action=actions_f,
        object=objects_f,
        condition=conditions_f,
        constraint=constraints_f,
        output=outputs_f,
        recipient=recipients_f,
        affected_entity=affected_f,
        responsibility_type=_responsibility_type(actions_f),
        provenance=prov,
        confidence=confidence,
        decomposition_status=status,
        facet_origins=facets,
        responsibilities=[resp.to_dict()],
        split_parent_id=split_parent_id,
        ambiguity_reason=ambiguity_reason,
        supporting_context=supporting,
    )


def _clause_is_condition_only(clause: str, actions: list[str]) -> bool:
    return bool(_extract_condition_phrases(clause)) and not actions


def _should_split_responsibilities(
    actions: list[str],
    clause_action_map: list[tuple[str, list[str]]],
) -> bool:
    """Split when distinct actions imply different owners/artifacts — not mere 하고."""
    if len(actions) < 2:
        return False
    actionable = [(c, a) for c, a in clause_action_map if a]
    if len(actionable) >= 2:
        return True
    rtypes = {_responsibility_by_canonical(a) for a in actions}
    if len(rtypes) >= 2:
        return True
    # notify + state change in same span → compound responsibility
    if any(a in NOTIFY_ACTIONS for a in actions) and any(a in STATE_ACTIONS for a in actions):
        return True
    if any(a in RECORD_ACTIONS for a in actions) and any(
        a not in RECORD_ACTIONS for a in actions
    ):
        return True
    return False


def _same_action_parallel_objects(span: str, actions: list[str]) -> bool:
    """True for '이름과 이메일을 저장한다' style — do not over-split."""
    if len(actions) != 1:
        return False
    return bool(re.search(r".+(와|과|및|,).+을?\s*" + re.escape(actions[0][:2]), span)) or (
        ("와" in span or "과" in span or " 및 " in span) and len(actions) == 1
    )


def _split_compound_by_action_spans(
    sentence: str,
    actions: list[str],
) -> list[tuple[str, list[str]]] | None:
    """Heuristic split of a sentence into per-primary-action spans when clauses fail."""
    if len(actions) < 2:
        return None
    # Find earliest stem position per canonical action
    positions: list[tuple[int, str]] = []
    for canonical in actions:
        best = None
        for stem, can in ACTION_STEMS:
            if can != canonical:
                continue
            idx = sentence.find(stem)
            while idx >= 0:
                if not _is_noun_compound_action(sentence, idx, stem, canonical):
                    best = idx if best is None else min(best, idx)
                idx = sentence.find(stem, idx + len(stem))
        if best is not None:
            positions.append((best, canonical))
    positions.sort()
    if len(positions) < 2:
        return None
    spans: list[tuple[str, list[str]]] = []
    for i, (pos, canonical) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(sentence)
        # extend start a bit left for objects/conditions
        start = 0 if i == 0 else pos
        # include shared leading condition in first span only; for later spans start at action neighborhood
        if i > 0:
            start = max(0, pos - 0)
            # pull recipient/object words immediately before action (e.g. 관리자에게 알림)
            window = sentence[max(0, pos - 12) : end]
            # prefer clause-ish cut at 하고/하며
            cut = None
            for sep in ("하고", "하며", "고 "):
                j = sentence.rfind(sep, 0, pos)
                if j >= 0:
                    cut = j + len(sep)
                    break
            if cut is not None:
                start = cut
            chunk = sentence[start:end].strip(" ,.")
            if not chunk:
                chunk = window.strip(" ,.")
        else:
            chunk = sentence[start:end].strip(" ,.")
        if chunk:
            spans.append((chunk, [canonical]))
    return spans if len(spans) >= 2 else None


def _is_alternative_constraint_bundle(sentence: str, actions: list[str]) -> bool:
    """승인 또는 자동 해제 — one responsibility with alternatives, not unsafe multi-action."""
    if "또는" not in sentence and "중 하나" not in sentence:
        return False
    rtypes = {_responsibility_by_canonical(a) for a in actions}
    return len(rtypes) == 1


def decompose_change_request(cr_text: str) -> list[AtomicChangeUnit]:
    """Decompose CR into Atomic Change Units (PR-7 semantic integrity).

    Meaning-complete units → EXTRACTED (implicit_system allowed).
    True multi-interpretation → AMBIGUOUS.
    Unsafe split → NEEDS_REVIEW.
    """
    full = " ".join((cr_text or "").split()).strip()
    if not full:
        return []

    sentences = _split_sentences(cr_text)
    units: list[AtomicChangeUnit] = []
    carry_actors: list[str] = []
    pending_conditions: list[str] = []
    seq = 0

    def _next_id() -> str:
        nonlocal seq
        seq += 1
        return f"ACU-{seq:03d}"

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        actions_in_sent = _primary_actions(sent)
        clauses = _split_clauses(sent)
        clause_action_map = [(c, _primary_actions(c)) for c in clauses]
        distinct_actions = actions_in_sent

        if not actions_in_sent:
            if not units:
                actors, recipients, note = _resolve_roles(sent, [], carry_actors=carry_actors)
                units.append(
                    _build_unit(
                        change_id=_next_id(),
                        span=sent,
                        full_cr=full,
                        actors=actors,
                        actions=[],
                        recipients=recipients,
                        status="NEEDS_REVIEW",
                        confidence=0.25,
                        method="FALLBACK_WHOLE_CR",
                        carry_note=note,
                        parent_sentence=sent,
                    )
                )
            else:
                last = units[-1]
                last.provenance.setdefault("orphan_spans", []).append(sent)
                # Trailing fragment without action does not force AMBIGUOUS on prior EXTRACTED
                # unless it clearly alters responsibility boundary
                if last.decomposition_status == "EXTRACTED" and _primary_actions(sent):
                    last.decomposition_status = "AMBIGUOUS"
                    last.ambiguity_reason = "orphan_action_fragment"
                    last.confidence = min(last.confidence, 0.4)
            continue

        # Parallel objects, single action → one ACU (do not over-split)
        if _same_action_parallel_objects(sent, distinct_actions):
            actors, recipients, note = _resolve_roles(
                sent, distinct_actions, carry_actors=carry_actors
            )
            unit = _build_unit(
                change_id=_next_id(),
                span=sent,
                full_cr=full,
                actors=actors,
                actions=distinct_actions,
                recipients=recipients,
                status="EXTRACTED",
                confidence=0.75,
                method="rule_v2",
                carry_note=note,
                parent_sentence=sent,
                pending_conditions=pending_conditions or None,
            )
            pending_conditions = []
            units.append(unit)
            if actors and actors != [IMPLICIT_SYSTEM]:
                carry_actors = [a for a in actors if a != IMPLICIT_SYSTEM]
            continue

        # Alternative constraints bundle (또는 / 중 하나) → single EXTRACTED
        if _is_alternative_constraint_bundle(sent, distinct_actions):
            actors, recipients, note = _resolve_roles(
                sent, distinct_actions, carry_actors=carry_actors
            )
            unit = _build_unit(
                change_id=_next_id(),
                span=sent,
                full_cr=full,
                actors=actors,
                actions=distinct_actions,
                recipients=recipients,
                status="EXTRACTED",
                confidence=0.7,
                method="rule_v2",
                carry_note=note,
                parent_sentence=sent,
                pending_conditions=pending_conditions or None,
            )
            pending_conditions = []
            units.append(unit)
            continue

        # Single primary action → EXTRACTED (implicit system OK)
        if len(distinct_actions) == 1:
            actors, recipients, note = _resolve_roles(
                sent, distinct_actions, carry_actors=carry_actors
            )
            unit = _build_unit(
                change_id=_next_id(),
                span=sent,
                full_cr=full,
                actors=actors,
                actions=distinct_actions,
                recipients=recipients,
                status="EXTRACTED",
                confidence=0.78 if note != "implicit_system" else 0.7,
                method="rule_v2",
                carry_note=note,
                parent_sentence=sent,
                pending_conditions=pending_conditions or None,
            )
            pending_conditions = []
            units.append(unit)
            if actors and IMPLICIT_SYSTEM not in actors:
                carry_actors = actors
            continue

        # Multiple actions — try clause split
        if _should_split_responsibilities(distinct_actions, clause_action_map):
            actionable_clauses = [(c, a) for c, a in clause_action_map if a]
            # Synthetic parent id for provenance (does not consume ACU sequence)
            split_parent = f"ACU-SPLIT-{seq + 1:03d}"
            produced: list[AtomicChangeUnit] = []
            local_carry = list(carry_actors)

            if len(actionable_clauses) >= 2:
                for clause, clause_actions in clause_action_map:
                    if _clause_is_condition_only(clause, clause_actions):
                        pending_conditions.extend(_extract_condition_phrases(clause))
                        continue
                    if not clause_actions:
                        if _extract_condition_phrases(clause):
                            pending_conditions.extend(_extract_condition_phrases(clause))
                        continue
                    actors, recipients, note = _resolve_roles(
                        clause, clause_actions, carry_actors=local_carry
                    )
                    cid = _next_id()
                    unit = _build_unit(
                        change_id=cid,
                        span=clause,
                        full_cr=full,
                        actors=actors,
                        actions=clause_actions,
                        recipients=recipients,
                        status="EXTRACTED",
                        confidence=0.72,
                        method="rule_v2",
                        carry_note=note,
                        split_parent_id=split_parent,
                        parent_sentence=sent,
                        pending_conditions=pending_conditions or None,
                    )
                    pending_conditions = []
                    if not produced:
                        sent_conds = _extract_condition_phrases(sent)
                        if sent_conds:
                            # only attach conditions that appear in parent sentence and relate
                            unit.condition = list(
                                dict.fromkeys(
                                    [c for c in sent_conds if c in clause or c in sent]
                                    + unit.condition
                                )
                            )
                    produced.append(unit)
                    if actors and IMPLICIT_SYSTEM not in actors:
                        local_carry = actors
                        carry_actors = actors
                if len(produced) >= 2:
                    units.extend(produced)
                    continue

            # Action-span heuristic split (e.g. 잠그고 … 알림)
            heur = _split_compound_by_action_spans(sent, distinct_actions)
            if heur and len(heur) >= 2:
                produced = []
                local_carry = list(carry_actors)
                for chunk, chunk_actions in heur:
                    actors, recipients, note = _resolve_roles(
                        chunk, chunk_actions, carry_actors=local_carry
                    )
                    unit = _build_unit(
                        change_id=_next_id(),
                        span=chunk,
                        full_cr=full,
                        actors=actors,
                        actions=chunk_actions,
                        recipients=recipients,
                        status="EXTRACTED",
                        confidence=0.68,
                        method="rule_v2_span_split",
                        carry_note=note,
                        split_parent_id=split_parent,
                        parent_sentence=sent,
                        pending_conditions=pending_conditions or None,
                    )
                    pending_conditions = []
                    produced.append(unit)
                if len(produced) >= 2:
                    # Attach sentence-level condition to first child only
                    sent_conds = _extract_condition_phrases(sent)
                    if sent_conds:
                        produced[0].condition = list(
                            dict.fromkeys(sent_conds + produced[0].condition)
                        )
                    units.extend(produced)
                    continue

            # Could not split safely
            actors, recipients, note = _resolve_roles(
                sent, distinct_actions, carry_actors=carry_actors
            )
            unit = _build_unit(
                change_id=_next_id(),
                span=sent,
                full_cr=full,
                actors=actors,
                actions=distinct_actions,
                recipients=recipients,
                status="NEEDS_REVIEW",
                confidence=0.4,
                method="rule_v2",
                carry_note=note,
                ambiguity_reason="unsafe_multi_action_split",
                parent_sentence=sent,
            )
            units.append(unit)
            continue

        # Multiple same-type actions without clear split
        rtypes = {_responsibility_by_canonical(a) for a in distinct_actions}
        actors, recipients, note = _resolve_roles(
            sent, distinct_actions, carry_actors=carry_actors
        )
        # Co-hyponym record verbs (감사+기록) or display synonyms → EXTRACTED
        if len(rtypes) == 1 and (
            set(distinct_actions) <= RECORD_ACTIONS
            or set(distinct_actions) <= NOTIFY_ACTIONS
        ):
            unit = _build_unit(
                change_id=_next_id(),
                span=sent,
                full_cr=full,
                actors=actors,
                actions=distinct_actions,
                recipients=recipients,
                status="EXTRACTED",
                confidence=0.72,
                method="rule_v2",
                carry_note=note,
                parent_sentence=sent,
                pending_conditions=pending_conditions or None,
            )
            pending_conditions = []
            units.append(unit)
            continue

        unit = _build_unit(
            change_id=_next_id(),
            span=sent,
            full_cr=full,
            actors=actors,
            actions=distinct_actions,
            recipients=recipients,
            status="AMBIGUOUS",
            confidence=0.45,
            method="rule_v2",
            carry_note=note,
            ambiguity_reason="multiple_actions_same_responsibility_type",
            parent_sentence=sent,
            pending_conditions=pending_conditions or None,
        )
        pending_conditions = []
        units.append(unit)

    if not units:
        actors, recipients, note = _resolve_roles(full, _primary_actions(full))
        units.append(
            _build_unit(
                change_id="ACU-001",
                span=full,
                full_cr=full,
                actors=actors,
                actions=_primary_actions(full),
                recipients=recipients,
                status="NEEDS_REVIEW",
                confidence=0.2,
                method="FALLBACK_WHOLE_CR",
                carry_note=note,
            )
        )

    return units


def decompose_change_request_v1(cr_text: str) -> list[AtomicChangeUnit]:
    """Legacy PR-4-ish decomposition retained for before/after comparison only."""
    # Minimal reimplementation of v0 behavior for comparison traces.
    full = " ".join((cr_text or "").split()).strip()
    if not full:
        return []
    sentences = [p.strip() for p in SENTENCE_SPLIT_RE.split(cr_text) if p and p.strip()]
    units: list[AtomicChangeUnit] = []
    seq = 0

    def _nid() -> str:
        nonlocal seq
        seq += 1
        return f"ACU-{seq:03d}"

    for sent in sentences or [full]:
        actions = _action_hits(sent, allow_noun_compound=True)
        # Strip v2 filters — approximate v1 by raw hits without role split
        actors = _hits(sent, ACTOR_MARKERS)
        status: DecompositionStatus = "EXTRACTED"
        if len(actions) > 1:
            clauses = _split_clauses(sent)
            amap = [(c, _action_hits(c, allow_noun_compound=True)) for c in clauses]
            if sum(1 for _, a in amap if a) >= 2:
                for c, a in amap:
                    if not a:
                        continue
                    units.append(
                        _build_unit(
                            change_id=_nid(),
                            span=c,
                            full_cr=full,
                            actors=_hits(c, ACTOR_MARKERS) or actors,
                            actions=a,
                            status="EXTRACTED",
                            confidence=0.55,
                            method="rule_v1_compare",
                            parent_sentence=sent,
                        )
                    )
                continue
            status = "AMBIGUOUS"
        units.append(
            _build_unit(
                change_id=_nid(),
                span=sent,
                full_cr=full,
                actors=actors or [IMPLICIT_SYSTEM],
                actions=actions,
                status=status if actions else "NEEDS_REVIEW",
                confidence=0.5,
                method="rule_v1_compare",
                ambiguity_reason="v1_compare" if status == "AMBIGUOUS" else None,
                parent_sentence=sent,
            )
        )
    return units


def _responsibility_by_canonical(action: str) -> str:
    return RESPONSIBILITY_BY_ACTION.get(action, "other")


# ---------------------------------------------------------------------------
# Scope isolation / comparison traces
# ---------------------------------------------------------------------------


def build_acu_scope_isolation(
    cr_text: str, units: list[AtomicChangeUnit]
) -> dict[str, Any]:
    """Report direct vs context facets and rejected cross-ACU leakage."""
    full = " ".join((cr_text or "").split())
    entries: list[dict[str, Any]] = []
    all_spans = {u.change_id: u.source_span for u in units}
    for u in units:
        rejected: list[dict[str, Any]] = []
        # Any output/object from other units' distinctive tokens
        for other in units:
            if other.change_id == u.change_id:
                continue
            for role in ("output", "action", "object", "recipient"):
                for val in getattr(other, role, []) or []:
                    if not val or val == IMPLICIT_SYSTEM:
                        continue
                    if val in u.source_span:
                        continue
                    # Present on this unit incorrectly?
                    if val in (getattr(u, role, []) or []):
                        rejected.append(
                            {
                                "value": val,
                                "role": role,
                                "reason": "outside_acu_span",
                                "from_acu": other.change_id,
                            }
                        )
        # Whole-CR outputs not in span
        for m in _output_hits(full):
            if m not in u.source_span and m in (u.output or []):
                rejected.append(
                    {"value": m, "role": "output", "reason": "outside_acu_span"}
                )
        entries.append(
            {
                "atomic_change_id": u.change_id,
                "source_span": u.source_span,
                "direct_facets": [
                    f for f in u.facet_origins if f.get("origin") == "ACU_DIRECT"
                ],
                "context_facets": list(u.supporting_context),
                "rejected_cross_acu_facets": rejected,
            }
        )
    return {
        "stage": "acu_scope_isolation",
        "schema_version": "acu_v2",
        "entries": entries,
        "span_index": all_spans,
    }


def compare_acu_v1_vs_v2(cr_text: str) -> dict[str, Any]:
    v1 = decompose_change_request_v1(cr_text)
    v2 = decompose_change_request(cr_text)
    return {
        "stage": "acu_v1_vs_v2_shadow",
        "v1": {
            "unit_count": len(v1),
            "statuses": {u.change_id: u.decomposition_status for u in v1},
            "units": [
                {
                    "id": u.change_id,
                    "status": u.decomposition_status,
                    "action": u.action,
                    "actor": u.actor,
                    "recipient": u.recipient,
                    "output": u.output,
                    "span": u.source_span,
                }
                for u in v1
            ],
        },
        "v2": {
            "unit_count": len(v2),
            "statuses": {u.change_id: u.decomposition_status for u in v2},
            "units": [
                {
                    "id": u.change_id,
                    "status": u.decomposition_status,
                    "action": u.action,
                    "actor": u.actor,
                    "recipient": u.recipient,
                    "affected_entity": u.affected_entity,
                    "output": u.output,
                    "span": u.source_span,
                    "split_parent_id": u.split_parent_id,
                }
                for u in v2
            ],
        },
        "delta": {
            "unit_count_v1": len(v1),
            "unit_count_v2": len(v2),
            "extracted_v1": sum(1 for u in v1 if u.decomposition_status == "EXTRACTED"),
            "extracted_v2": sum(1 for u in v2 if u.decomposition_status == "EXTRACTED"),
            "ambiguous_v1": sum(1 for u in v1 if u.decomposition_status == "AMBIGUOUS"),
            "ambiguous_v2": sum(1 for u in v2 if u.decomposition_status == "AMBIGUOUS"),
        },
    }


def acus_to_trace_payload_v2(cr_text: str, units: list[AtomicChangeUnit]) -> dict[str, Any]:
    return {
        "source_cr": cr_text,
        "decomposition_method": "rule_v2",
        "schema_version": "acu_v2",
        "note": (
            "PR-7 ACU semantic integrity & scope isolation. "
            "PR-4 introduces ACU decomposition but does not yet replace whole-CR patching. "
            "Actual B3/B4/B5 still consume whole CR."
        ),
        "unit_count": len(units),
        "units": [
            {
                "atomic_change_id": u.change_id,
                "split_parent_id": u.split_parent_id,
                "source_span": u.source_span,
                "source_offsets": (u.provenance or {}).get("source_offsets"),
                "status": u.decomposition_status,
                "actor": u.actor,
                "recipient": u.recipient,
                "affected_entity": u.affected_entity,
                "action": u.action,
                "object": u.object,
                "condition": u.condition,
                "constraint": u.constraint,
                "output": u.output,
                "responsibility_type": u.responsibility_type,
                "facet_origins": u.facet_origins,
                "provenance": u.provenance,
                "ambiguity_reason": u.ambiguity_reason,
                "responsibilities": u.responsibilities,
                "supporting_context": u.supporting_context,
            }
            for u in units
        ],
    }


# ---------------------------------------------------------------------------
# Shadow / future discovery hooks (read-only metadata; not wired into actual B3/B5)
# ---------------------------------------------------------------------------


def acu_as_requirement_discovery_input(acu: AtomicChangeUnit) -> dict[str, Any]:
    """Shadow-ready B3 input shape for a single ACU (not used by actual path yet)."""
    return {
        "atomic_change_id": acu.change_id,
        "query_text": acu.source_span,
        "facets": {
            "actor": list(acu.actor),
            "action": list(acu.action),
            "object": list(acu.object),
            "recipient": list(acu.recipient),
            "affected_entity": list(acu.affected_entity),
            "condition": list(acu.condition),
            "constraint": list(acu.constraint),
            "output": list(acu.output),
        },
        "responsibility_type": acu.responsibility_type,
        "decomposition_status": acu.decomposition_status,
        "path": "shadow_ready",
        "note": "Not fed into actual B3.",
    }


def acu_as_design_discovery_input(acu: AtomicChangeUnit) -> dict[str, Any]:
    """Shadow-ready B5a input shape for a single ACU (not used by actual path yet)."""
    return {
        "atomic_change_id": acu.change_id,
        "query_text": acu.source_span,
        "facets": {
            "actor": list(acu.actor),
            "action": list(acu.action),
            "object": list(acu.object),
            "recipient": list(acu.recipient),
            "affected_entity": list(acu.affected_entity),
            "output": list(acu.output),
        },
        "responsibility_type": acu.responsibility_type,
        "decomposition_status": acu.decomposition_status,
        "path": "shadow_ready",
        "note": "Not fed into actual B5a.",
    }


def acus_to_trace_payload(cr_text: str, units: list[AtomicChangeUnit]) -> dict[str, Any]:
    base = acus_to_trace_payload_v2(cr_text, units)
    base["shadow_hooks"] = {
        "requirement_discovery_inputs": [
            acu_as_requirement_discovery_input(u) for u in units
        ],
        "design_discovery_inputs": [acu_as_design_discovery_input(u) for u in units],
    }
    return base
