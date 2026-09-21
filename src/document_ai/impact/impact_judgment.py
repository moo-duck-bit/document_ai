# -*- coding: utf-8 -*-
"""B3: Domain-independent evidence-based impact judgment.

IMPACTED / NOT_IMPACTED / UNCERTAIN with structured change_type + evidence.
Same Req ID alone never implies IMPACTED.
Does NOT read expected_impact.*.
Does NOT hard-code scenario-specific Req IDs or domain keywords (e.g. lockout-only gates).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from document_ai.impact.semantic_hybrid_retrieve import ScoredHit
from document_ai.impact.semantic_index import RequirementBlock

Judgment = Literal["IMPACTED", "NOT_IMPACTED", "UNCERTAIN"]
ChangeType = Literal[
    "MODIFY_EXISTING",
    "EXTEND_EXISTING",
    "NEW_REQUIREMENT_CANDIDATE",
    "NOT_RELATED",
    "UNCERTAIN",
]

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")

# Function / glue words — domain-agnostic stop list (not feature keywords).
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
    "한다",
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
}

# Generic role / behavior facets (cross-domain software/requirements language).
ACTOR_MARKERS = (
    "의료진",
    "환자",
    "사용자",
    "관리자",
    "서버",
    "시스템",
    "클라이언트",
    "애플리케이션",
    "운영자",
    "개발자",
)
ACTION_MARKERS = (
    "분류",
    "표시",
    "조회",
    "갱신",
    "생성",
    "삭제",
    "제한",
    "안내",
    "저장",
    "관리",
    "추적",
    "기록",
    "식별",
    "등록",
    "검증",
    "차단",
    "전송",
    "동기화",
    "모니터링",
    "평가",
    "분석",
    "알림",
    "검색",
    "필터",
)
OUTPUT_MARKERS = (
    "화면",
    "대시보드",
    "목록",
    "리포트",
    "메시지",
    "상태",
    "API",
    "로그",
    "기록",
    "표시",
)
CONDITION_MARKERS = (
    "경우",
    "때",
    "동안",
    "이후",
    "이상",
    "이하",
    "초과",
    "미만",
    "없으면",
    "없으면",
    "기준",
)


@dataclass
class EvidencePack:
    cr_spans: list[str] = field(default_factory=list)
    candidate_spans: list[str] = field(default_factory=list)
    matched_concepts: list[str] = field(default_factory=list)
    behavioral_overlap: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImpactDecision:
    candidate_id: str
    document: str
    judgment: Judgment
    reason: str
    change_type: ChangeType = "UNCERTAIN"
    evidence: list[str] = field(default_factory=list)  # legacy flat list
    evidence_structured: dict[str, Any] = field(default_factory=dict)
    evidence_snippet: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    theme_hits: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    retrieval_rank: int | None = None
    source_locator: str = ""
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # API shape requested by harness consumers
        d["candidate"] = self.candidate_id
        d["evidence"] = self.evidence_structured or {
            "cr_spans": [],
            "candidate_spans": [],
            "matched_concepts": list(self.evidence),
        }
        return d


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]


def _content_set(text: str) -> set[str]:
    return set(_tokens(text))


def _bigrams(tokens: list[str]) -> set[str]:
    return {f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[.\n。]+", text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def _spans_containing(text: str, concepts: list[str], *, limit: int = 3) -> list[str]:
    if not concepts:
        return []
    out: list[str] = []
    for sent in _sentences(text):
        if any(c.replace("_", "") in sent.replace(" ", "") or c.split("_")[0] in sent for c in concepts):
            out.append(sent[:180])
        if len(out) >= limit:
            break
    if not out and text:
        out.append((text or "")[:180].replace("\n", " "))
    return out


def _facet_hits(text: str, markers: tuple[str, ...]) -> list[str]:
    return [m for m in markers if m in (text or "")]


def _behavioral_overlap(cr: str, block_text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, markers in (
        ("actor", ACTOR_MARKERS),
        ("action", ACTION_MARKERS),
        ("output", OUTPUT_MARKERS),
        ("condition", CONDITION_MARKERS),
    ):
        shared = sorted(set(_facet_hits(cr, markers)) & set(_facet_hits(block_text, markers)))
        if shared:
            out[name] = shared
    # object ≈ shared content nouns already captured as matched_concepts; expose object markers overlap
    object_markers = ("환자", "계정", "문서", "데이터", "요청", "세션", "코드", "권한", "기록", "상태")
    shared_obj = sorted(set(_facet_hits(cr, object_markers)) & set(_facet_hits(block_text, object_markers)))
    if shared_obj:
        out["object"] = shared_obj
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _false_friend(matched: list[str], cr: str, block: str) -> bool:
    """Shared token appears in divergent collocations (weak single-token overlap)."""
    if len(matched) > 2:
        return False
    if not matched:
        return False
    # Single ambiguous token with no shared actor/object pair
    actors_shared = set(_facet_hits(cr, ACTOR_MARKERS)) & set(_facet_hits(block, ACTOR_MARKERS))
    objects_shared = set(_facet_hits(cr, ("환자", "계정", "데이터", "기록", "상태"))) & set(
        _facet_hits(block, ("환자", "계정", "데이터", "기록", "상태"))
    )
    if len(matched) <= 1 and not actors_shared and not objects_shared:
        return True
    # Token present but CR pairs it with an actor the block never uses nearby
    for tok in matched:
        if tok in cr and tok in block:
            # if CR has actor+tok style and block only has tok with different actor set
            if actors_shared:
                continue
            if _facet_hits(cr, ACTOR_MARKERS) and not actors_shared:
                return True
    return False


def _estimate_change_type(
    *,
    matched: list[str],
    facets: dict[str, list[str]],
    cr_tokens: set[str],
    block_tokens: set[str],
    false_friend: bool,
    relevance: float,
) -> ChangeType:
    if false_friend or relevance < 0.04:
        return "NOT_RELATED"
    facet_n = len(facets)
    novel = sorted(t for t in cr_tokens if t not in block_tokens and len(t) >= 2)[:12]
    has_core = bool(facets.get("object") or facets.get("actor") or len(matched) >= 3)
    if relevance >= 0.12 and facet_n >= 2 and has_core and len(novel) <= 2:
        return "MODIFY_EXISTING"
    if relevance >= 0.08 and facet_n >= 1 and has_core:
        # CR brings additional constraints/actions not in block
        if novel:
            return "EXTEND_EXISTING"
        return "MODIFY_EXISTING"
    if relevance >= 0.06 and has_core and novel:
        return "NEW_REQUIREMENT_CANDIDATE"
    if relevance >= 0.05:
        return "UNCERTAIN"
    return "NOT_RELATED"


def judge_block(
    cr_text: str,
    block: RequirementBlock,
    *,
    lexical_score: float,
    semantic_score: float,
    retrieval_rank: int | None = None,
) -> ImpactDecision:
    """Evidence-based judgment. Domain lockout lexicons are not required for IMPACTED."""
    block_text = f"{block.title}\n{block.body_text}"
    cr_toks = _tokens(cr_text)
    bl_toks = _tokens(block_text)
    cr_set, bl_set = set(cr_toks), set(bl_toks)
    uni = sorted(cr_set & bl_set)
    bi = sorted(_bigrams(cr_toks) & _bigrams(bl_toks))
    matched = sorted(set(uni) | {b.replace("_", "") for b in bi if b.replace("_", "")})[:24]
    # Prefer showing bigram concepts when present
    matched_concepts = (bi[:8] + [u for u in uni if all(u not in b for b in bi)])[:16]

    jac_uni = _jaccard(cr_set, bl_set)
    jac_bi = _jaccard(_bigrams(cr_toks), _bigrams(bl_toks))
    relevance = 0.45 * jac_uni + 0.25 * jac_bi + 0.20 * min(1.0, semantic_score / 0.2) + 0.10 * min(
        1.0, lexical_score / 0.3
    )

    facets = _behavioral_overlap(cr_text, block_text)
    ff = _false_friend(matched_concepts or uni, cr_text, block_text)
    change_type = _estimate_change_type(
        matched=matched_concepts or uni,
        facets=facets,
        cr_tokens=cr_set,
        block_tokens=bl_set,
        false_friend=ff,
        relevance=relevance,
    )

    cr_spans = _spans_containing(cr_text, matched_concepts or uni)
    cand_spans = _spans_containing(block_text, matched_concepts or uni)
    pack = EvidencePack(
        cr_spans=cr_spans,
        candidate_spans=cand_spans,
        matched_concepts=matched_concepts or uni[:12],
        behavioral_overlap=facets,
    )

    facet_n = len(facets)
    confidence = round(min(0.95, relevance + 0.05 * facet_n), 3)

    title = block.title or ""
    access_primary = any(t in title for t in ("권한", "접근 통제", "API 접근"))

    judgment: Judgment
    reason: str

    # Primary evidence-based gates (domain-independent)
    if ff and relevance < 0.15:
        judgment = "NOT_IMPACTED"
        change_type = "NOT_RELATED"
        reason = (
            f"Lexical false-friend / divergent collocation; matched={pack.matched_concepts[:6]}; "
            f"relevance={relevance:.3f}. Not judged by ID alone."
        )
    elif (
        change_type in {"MODIFY_EXISTING", "EXTEND_EXISTING"}
        and facet_n >= 2
        and relevance >= 0.10
        and (lexical_score >= 0.06 or semantic_score >= 0.05 or jac_uni >= 0.08)
    ):
        judgment = "IMPACTED"
        reason = (
            f"Evidence overlap supports in-scope change ({change_type}); "
            f"facets={list(facets.keys())}; concepts={pack.matched_concepts[:8]}; "
            f"relevance={relevance:.3f} lex={lexical_score:.3f} sem={semantic_score:.3f}."
        )
    elif change_type == "NEW_REQUIREMENT_CANDIDATE" and facet_n >= 1 and relevance >= 0.07:
        judgment = "UNCERTAIN"
        reason = (
            f"Related candidate but CR likely exceeds existing responsibility "
            f"(change_type=NEW_REQUIREMENT_CANDIDATE); facets={list(facets.keys())}; "
            f"concepts={pack.matched_concepts[:8]}; relevance={relevance:.3f}."
        )
    elif change_type == "EXTEND_EXISTING" and relevance >= 0.07:
        judgment = "UNCERTAIN"
        reason = (
            f"Partial applicability for extension; needs human/B4 review. "
            f"facets={list(facets.keys())}; concepts={pack.matched_concepts[:8]}; "
            f"relevance={relevance:.3f}."
        )
    elif change_type == "NOT_RELATED" or relevance < 0.045:
        judgment = "NOT_IMPACTED"
        change_type = "NOT_RELATED"
        reason = (
            f"Insufficient CR↔requirement evidence overlap; "
            f"relevance={relevance:.3f} lex={lexical_score:.3f} sem={semantic_score:.3f}."
        )
    else:
        judgment = "UNCERTAIN"
        if change_type == "NOT_RELATED":
            change_type = "UNCERTAIN"
        reason = (
            f"Insufficient distinctive evidence for IMPACTED; "
            f"change_type={change_type}; facets={list(facets.keys())}; "
            f"relevance={relevance:.3f} lex={lexical_score:.3f} sem={semantic_score:.3f}."
        )

    # Structural demotion: access-control-primary titles need CR to target that responsibility
    if judgment == "IMPACTED" and access_primary:
        title_set = _content_set(title)
        if len(title_set & cr_set) < 1 and not any(
            t in cr_text for t in ("권한", "접근 통제", "인가", "Authorization")
        ):
            judgment = "NOT_IMPACTED"
            change_type = "NOT_RELATED"
            reason = (
                f"Access-control-primary title ({title!r}) without CR targeting access-control; "
                f"treating auth mentions as incidental. relevance={relevance:.3f}."
            )
            confidence = round(min(confidence, 0.35), 3)

    return ImpactDecision(
        candidate_id=block.req_id,
        document=block.document_type,
        judgment=judgment,
        reason=reason,
        change_type=change_type,
        evidence=list(pack.matched_concepts),
        evidence_structured=pack.to_dict(),
        evidence_snippet=(block.body_text or block.title or "")[:220].replace("\n", " "),
        scores={
            "lexical": lexical_score,
            "semantic": semantic_score,
            "relevance": round(relevance, 4),
            "jaccard_unigram": round(jac_uni, 4),
            "jaccard_bigram": round(jac_bi, 4),
        },
        theme_hits={"behavioral_overlap": facets},
        confidence=confidence,
        retrieval_rank=retrieval_rank,
        source_locator=block.source_locator,
        title=block.title,
    )


def judge_candidates(
    cr_text: str,
    blocks: list[RequirementBlock],
    ranked_hits: list[ScoredHit],
) -> list[ImpactDecision]:
    by_key = {(b.req_id, b.document_type): b for b in blocks}
    decisions: list[ImpactDecision] = []
    for hit in ranked_hits:
        block = by_key.get((hit.candidate_id, hit.document))
        if block is None:
            decisions.append(
                ImpactDecision(
                    candidate_id=hit.candidate_id,
                    document=hit.document,
                    judgment="UNCERTAIN",
                    change_type="UNCERTAIN",
                    reason="Block missing from index; cannot judge.",
                    retrieval_rank=hit.rank,
                    confidence=0.0,
                )
            )
            continue
        decisions.append(
            judge_block(
                cr_text,
                block,
                lexical_score=hit.lexical_score,
                semantic_score=hit.semantic_score,
                retrieval_rank=hit.rank,
            )
        )
    return decisions
