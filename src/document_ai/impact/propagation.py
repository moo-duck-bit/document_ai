# -*- coding: utf-8 -*-
"""B5v2: Domain-independent design propagation / patch planning.

Question answered here:
  Which Design artifact should receive a consistent Requirement change, and
  can the existing Design be modified/extended safely?

Same Req ID alone is never sufficient for PATCH.
Theme/keyword bags (감사/잠금/로그인/…) must not decide ownership.
Consumes B3/B4 evidence as priors; does not copy their conclusions.

Does not read expected_impact.*.
Does not hard-code scenario Req IDs or scenario-specific keywords.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from document_ai.impact.consistency_gate import ConsistencyDecision, parse_requirement_fields
from document_ai.impact.evidence_provenance import (
    ProvenanceBundle,
    build_alignment_provenance,
    empty_provenance_summary,
)
from document_ai.impact.preserve_patch import patch_mdsr_description_only, sha256_file
from document_ai.impact.semantic_index import RequirementBlock
from document_ai.learn.docx_io import load_document
from document_ai.learn.mdsr_diff import extract_req_blocks
from document_ai.render.design_items import patch_mddr_design_items
from document_ai.render.patch import patch_document_file

PropagationOutcome = Literal["PATCHED", "SKIPPED_WITH_REASON", "NEEDS_REVIEW"]
PropagationDecision = Literal[
    "PATCH_EXISTING",
    "EXTEND_EXISTING",
    "NEW_DESIGN_CANDIDATE",
    "SKIP",
    "NEEDS_REVIEW",
]

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

# High-frequency boilerplate — alone never proves design ownership.
WEAK_TOKENS = {
    "서버",
    "시스템",
    "기능",
    "사용",
    "제공",
    "관리",
    "기록",
    "감사",
    "상태",
    "데이터",
    "사용자",
    "정보",
    "통해",
    "대한",
    "위한",
    "경우",
    "기준",
    "처리",
    "수행",
    "가능",
    "있도록",
    "해야",
    "한다",
    "설계",
    "구현",
    "인증",
}

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


@dataclass
class PropagationEvidence:
    requirement_spans: list[str] = field(default_factory=list)
    design_spans: list[str] = field(default_factory=list)
    matched_responsibilities: list[str] = field(default_factory=list)
    matched_facets: list[str] = field(default_factory=list)
    direct_traceability: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    facet_detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_spans": list(self.requirement_spans),
            "design_spans": list(self.design_spans),
            "matched_responsibilities": list(self.matched_responsibilities),
            "matched_facets": list(self.matched_facets),
            "direct_traceability": list(self.direct_traceability),
            "conflicts": list(self.conflicts),
            "missing_information": list(self.missing_information),
            "facet_detail": dict(self.facet_detail),
        }


@dataclass
class PropagationTrace:
    source_mdsr_req_id: str
    mdsr_consistency_status: str
    impacted_mddr_candidate: str
    propagation_reason: str
    outcome: PropagationOutcome
    evidence: list[str] = field(default_factory=list)
    design_responsibility_aligned: bool = False
    patch_applied: bool = False
    mdsr_patched: bool = False
    before_snippet: str = ""
    after_snippet: str = ""
    requirement: str = ""
    design_candidate: str = ""
    propagation_decision: PropagationDecision | str = ""
    structured_evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    allow_mdsr_patch: bool = False
    b3_prior: dict[str, Any] = field(default_factory=dict)
    b4_prior: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["requirement"] = self.requirement or self.source_mdsr_req_id
        d["design_candidate"] = self.design_candidate or self.impacted_mddr_candidate
        d["evidence_structured"] = self.structured_evidence
        return d


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]


def _token_set(text: str) -> set[str]:
    return set(_tokens(text))


def _content_set(text: str) -> set[str]:
    return {t for t in _token_set(text) if t not in WEAK_TOKENS and len(t) >= 2}


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


def _spans(text: str, concepts: list[str], *, limit: int = 3) -> list[str]:
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


def _extract_b3_prior(
    b3_decision: dict[str, Any] | None,
    decision: ConsistencyDecision,
) -> dict[str, Any]:
    if b3_decision:
        ev = b3_decision.get("evidence") if isinstance(b3_decision.get("evidence"), dict) else {}
        concepts = ev.get("matched_concepts") if isinstance(ev, dict) else None
        if not isinstance(concepts, list):
            concepts = []
        return {
            "judgment": b3_decision.get("judgment") or "",
            "change_type": b3_decision.get("change_type") or "",
            "reason": b3_decision.get("reason") or "",
            "confidence": float(b3_decision.get("confidence") or 0.0),
            "cr_spans": list((ev or {}).get("cr_spans") or []),
            "candidate_spans": list((ev or {}).get("candidate_spans") or []),
            "matched_concepts": [c for c in concepts if isinstance(c, str)],
            "behavioral_overlap": dict((ev or {}).get("behavioral_overlap") or {}),
        }
    prior = getattr(decision, "b3_prior", None) or {}
    return dict(prior) if isinstance(prior, dict) else {}


def _extract_b4_prior(decision: ConsistencyDecision) -> dict[str, Any]:
    ev = decision.evidence if isinstance(decision.evidence, dict) else {}
    return {
        "consistency": decision.status,
        "allow_auto_patch": decision.allow_auto_patch,
        "reason": decision.reason,
        "compatible_facets": list(ev.get("compatible_facets") or []),
        "conflicting_facets": list(ev.get("conflicting_facets") or []),
        "missing_information": list(ev.get("missing_information") or []),
        "confidence": float(getattr(decision, "confidence", 0.0) or 0.0),
    }


# ---------------------------------------------------------------------------
# B5 staged interfaces (PR-1): structural split; B5v2 semantics preserved.
# ---------------------------------------------------------------------------


@dataclass
class DesignCandidate:
    """B5a candidate. PR-1: same_id source only (parity; same_id ≠ ownership)."""

    requirement_id: str
    design_id: str
    document: str
    sources: list[str]
    retrieval_rank: int | None = None
    retrieval_evidence: dict[str, Any] = field(default_factory=dict)
    block: RequirementBlock | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "design_id": self.design_id,
            "document": self.document,
            "sources": list(self.sources),
            "retrieval_rank": self.retrieval_rank,
            "retrieval_evidence": dict(self.retrieval_evidence),
        }


@dataclass
class AlignmentResult:
    """B5b alignment package. PR-1: evidence computation only (no PATCH/EXTEND)."""

    requirement_id: str
    design_id: str
    alignment: str
    evidence: dict[str, Any]
    confidence: float
    reason: str
    # Internal parity signals for B5c (not part of public trace contract)
    _signals: dict[str, Any] = field(default_factory=dict, repr=False)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "design_id": self.design_id,
            "alignment": self.alignment,
            "evidence": dict(self.evidence),
            "confidence": self.confidence,
            "reason": self.reason,
            "matched_facets": list((self.evidence or {}).get("matched_facets") or []),
            "provenance_summary": dict((self.provenance or {}).get("summary") or {}),
        }


@dataclass
class PropagationDecisionResult:
    """B5c propagation decision. PR-1: identical semantics to B5v2 assess() returns."""

    requirement_id: str
    design_id: str
    decision: PropagationDecision
    confidence: float
    reason: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "design_id": self.design_id,
            "decision": self.decision,
            "propagation_decision": self.decision,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": dict(self.evidence),
        }


def discover_design_candidates(
    requirement_id: str,
    blocks_by_key: dict[tuple[str, str], RequirementBlock],
) -> list[DesignCandidate]:
    """B5a actual discovery (PR-1/PR-2): same-ID MDDR only.

    Cross-ID lives in discover_design_candidates_shadow — never here.
    Does not decide PATCH/EXTEND/SKIP.
    """
    mddr = blocks_by_key.get((requirement_id, "MDDR"))
    if not mddr:
        return []
    return [
        DesignCandidate(
            requirement_id=requirement_id,
            design_id=mddr.req_id,
            document=mddr.document_type or "MDDR",
            sources=["same_id"],
            retrieval_rank=None,
            retrieval_evidence={"note": "actual path: same_id only (parity)"},
            block=mddr,
        )
    ]


# Shadow discovery provenance (≠ ownership evidence).
SOURCE_SAME_ID = "same_id"
SOURCE_B3_IMPACTED_MDDR = "b3_impacted_mddr"
SOURCE_B3_UNCERTAIN_MDDR = "optional_b3_uncertain_mddr"

_SHADOW_SOURCE_PRIORITY: dict[str, int] = {
    SOURCE_SAME_ID: 0,
    SOURCE_B3_IMPACTED_MDDR: 1,
    SOURCE_B3_UNCERTAIN_MDDR: 2,
}

# Domain-independent cap (contract band 5–8). Not scenario-tuned.
SHADOW_CANDIDATE_CAP = 8


def _candidate_key(design_id: str, document: str) -> tuple[str, str]:
    return (design_id, document or "MDDR")


def _merge_sources(existing: list[str], added: list[str]) -> list[str]:
    merged = list(existing)
    for s in added:
        if s not in merged:
            merged.append(s)
    return sorted(merged, key=lambda s: (_SHADOW_SOURCE_PRIORITY.get(s, 99), s))


def _uncertain_mddr_has_retrieval_evidence(decision: dict[str, Any]) -> bool:
    """Conservative UNCERTAIN gate: must have been retrieved + some signal."""
    if decision.get("retrieval_rank") is None:
        return False
    conf = float(decision.get("confidence") or 0.0)
    ev = decision.get("evidence") if isinstance(decision.get("evidence"), dict) else {}
    concepts = [c for c in (ev.get("matched_concepts") or []) if isinstance(c, str)]
    return conf >= 0.25 or bool(concepts)


def _upsert_shadow_candidate(
    pool: dict[tuple[str, str], DesignCandidate],
    *,
    requirement_id: str,
    block: RequirementBlock,
    sources: list[str],
    retrieval_rank: int | None,
    retrieval_evidence: dict[str, Any],
) -> None:
    key = _candidate_key(block.req_id, block.document_type or "MDDR")
    if key in pool:
        cur = pool[key]
        cur.sources = _merge_sources(cur.sources, sources)
        if cur.retrieval_rank is None and retrieval_rank is not None:
            cur.retrieval_rank = retrieval_rank
        cur.retrieval_evidence = {**cur.retrieval_evidence, **retrieval_evidence}
        return
    pool[key] = DesignCandidate(
        requirement_id=requirement_id,
        design_id=block.req_id,
        document=block.document_type or "MDDR",
        sources=_merge_sources([], sources),
        retrieval_rank=retrieval_rank,
        retrieval_evidence=dict(retrieval_evidence),
        block=block,
    )


def apply_shadow_candidate_cap(
    candidates: list[DesignCandidate],
    *,
    max_candidates: int = SHADOW_CANDIDATE_CAP,
) -> list[DesignCandidate]:
    """Cap shadow pool: always keep same_id; fill by IMPACTED then UNCERTAIN rank.

    Rationale: same_id is the actual-path anchor (must remain observable);
    IMPACTED MDDR is the primary cross-ID expansion; UNCERTAIN is optional filler.
    Priority is source-class based — never Req-ID or domain keywords.
    """
    if max_candidates <= 0:
        return []
    same = [c for c in candidates if SOURCE_SAME_ID in c.sources]
    rest = [c for c in candidates if SOURCE_SAME_ID not in c.sources]

    def _sort_key(c: DesignCandidate) -> tuple[int, int, str]:
        pri = min((_SHADOW_SOURCE_PRIORITY.get(s, 99) for s in c.sources), default=99)
        rank = c.retrieval_rank if c.retrieval_rank is not None else 10_000
        return (pri, rank, c.design_id)

    rest_sorted = sorted(rest, key=_sort_key)
    remaining = max(0, max_candidates - len(same))
    return same + rest_sorted[:remaining]


def discover_design_candidates_shadow(
    requirement_id: str,
    blocks_by_key: dict[tuple[str, str], RequirementBlock],
    *,
    b3_decisions: list[dict[str, Any]] | None = None,
    max_candidates: int = SHADOW_CANDIDATE_CAP,
) -> list[DesignCandidate]:
    """B5a shadow discovery: same_id + B3 IMPACTED MDDR (+ optional UNCERTAIN).

    Observation only — must not feed actual B5c / patch.
    Shadow candidate comparison does not select a new owner.
    """
    pool: dict[tuple[str, str], DesignCandidate] = {}

    # 1) same_id
    for cand in discover_design_candidates(requirement_id, blocks_by_key):
        if cand.block is None:
            continue
        _upsert_shadow_candidate(
            pool,
            requirement_id=requirement_id,
            block=cand.block,
            sources=[SOURCE_SAME_ID],
            retrieval_rank=cand.retrieval_rank,
            retrieval_evidence=dict(cand.retrieval_evidence),
        )

    # 2–3) B3 MDDR judgments (no Req-ID hard-codes)
    for d in b3_decisions or []:
        doc = d.get("document")
        if doc != "MDDR":
            continue
        rid = d.get("candidate_id") or d.get("candidate")
        if not rid or not isinstance(rid, str):
            continue
        block = blocks_by_key.get((rid, "MDDR"))
        if not block:
            continue
        judgment = d.get("judgment") or ""
        rank = d.get("retrieval_rank")
        rank_i = int(rank) if isinstance(rank, int) else (int(rank) if isinstance(rank, float) else None)
        if judgment == "IMPACTED":
            _upsert_shadow_candidate(
                pool,
                requirement_id=requirement_id,
                block=block,
                sources=[SOURCE_B3_IMPACTED_MDDR],
                retrieval_rank=rank_i,
                retrieval_evidence={
                    "b3_judgment": "IMPACTED",
                    "b3_confidence": float(d.get("confidence") or 0.0),
                    "b3_reason": d.get("reason") or "",
                },
            )
        elif judgment == "UNCERTAIN" and _uncertain_mddr_has_retrieval_evidence(d):
            _upsert_shadow_candidate(
                pool,
                requirement_id=requirement_id,
                block=block,
                sources=[SOURCE_B3_UNCERTAIN_MDDR],
                retrieval_rank=rank_i,
                retrieval_evidence={
                    "b3_judgment": "UNCERTAIN",
                    "b3_confidence": float(d.get("confidence") or 0.0),
                    "b3_reason": d.get("reason") or "",
                    "note": "optional UNCERTAIN with retrieval evidence",
                },
            )

    return apply_shadow_candidate_cap(list(pool.values()), max_candidates=max_candidates)


def _shadow_evidence_buckets(evidence: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Split alignment evidence into direct / generic / conflicts for shadow comparison."""
    matched_facets = list(evidence.get("matched_facets") or [])
    direct = list(evidence.get("matched_responsibilities") or [])
    direct.extend(f for f in matched_facets if not str(f).startswith("b3_prior_"))
    direct.extend(list(evidence.get("direct_traceability") or []))
    generic = [f for f in matched_facets if str(f).startswith("b3_prior_")]
    detail = evidence.get("facet_detail") if isinstance(evidence.get("facet_detail"), dict) else {}
    for key in ("mdsr_mddr_content",):
        vals = detail.get(key) or []
        if isinstance(vals, list):
            generic.extend(str(v) for v in vals[:6])
    conflicts = list(evidence.get("conflicts") or [])
    # de-dupe preserving order
    def _uniq(xs: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return _uniq(direct), _uniq(generic), _uniq(conflicts)


def evaluate_shadow_candidates(
    *,
    cr_text: str,
    mdsr: RequirementBlock,
    decision: ConsistencyDecision,
    actual_design_id: str | None,
    shadow_candidates: list[DesignCandidate],
    b3_by_key: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Run B5b on shadow pool for observation only.

    Does not call B5c. Does not select a new owner.
    """
    alignments: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    for cand in shadow_candidates:
        # Prefer candidate's own B3 MDDR prior for observational alignment.
        b3_prior = _extract_b3_prior(b3_by_key.get((cand.design_id, "MDDR")), decision)
        align = align_design_candidate(
            cr_text,
            mdsr,
            cand.block,
            decision=decision,
            b3_prior=b3_prior,
        )
        is_actual = bool(actual_design_id) and cand.design_id == actual_design_id
        prov = align.provenance or {}
        prov_summary = dict(prov.get("summary") or empty_provenance_summary())
        row = {
            "source_requirement_id": mdsr.req_id,
            "design_id": cand.design_id,
            "document": cand.document,
            "sources": list(cand.sources),
            "is_actual_candidate": is_actual,
            "alignment": align.alignment,
            "confidence": align.confidence,
            "evidence": dict(align.evidence),
            "reason": align.reason,
            "matched_facets": list((align.evidence or {}).get("matched_facets") or []),
            "retrieval_rank": cand.retrieval_rank,
            "provenance_summary": prov_summary,
        }
        alignments.append(row)
        direct, generic, conflicts = _shadow_evidence_buckets(align.evidence)
        comparison_rows.append(
            {
                "design_id": cand.design_id,
                "document": cand.document,
                "sources": list(cand.sources),
                "is_actual_candidate": is_actual,
                "alignment": align.alignment,
                "confidence": align.confidence,
                "direct_evidence": direct,
                "generic_evidence": generic,
                "conflicts": conflicts,
                "reason": align.reason,
                "direct_independent_count": prov_summary.get("direct_independent_count", 0),
                "supporting_independent_count": prov_summary.get(
                    "supporting_independent_count", 0
                ),
                "generic_count": prov_summary.get("generic_count", 0),
                "derived_prior_count": prov_summary.get("derived_prior_count", 0),
                "conflicting_count": prov_summary.get("conflicting_count", 0),
                "unique_independent_groups": list(
                    prov_summary.get("unique_independent_groups") or []
                ),
                "evidence_lineage_summary": list(
                    prov_summary.get("evidence_lineage_summary") or []
                ),
                "note": "Shadow candidate comparison does not select a new owner.",
            }
        )

    return {
        "requirement_id": mdsr.req_id,
        "actual_candidate": actual_design_id,
        "note": "Shadow candidate comparison does not select a new owner.",
        "shadow_candidate_count": len(shadow_candidates),
        "candidates": [c.to_dict() for c in shadow_candidates],
        "alignments": alignments,
        "shadow_candidates": comparison_rows,
    }


def align_design_candidate(
    cr_text: str,
    mdsr: RequirementBlock,
    mddr: RequirementBlock | None,
    *,
    decision: ConsistencyDecision,
    b3_prior: dict[str, Any] | None = None,
) -> AlignmentResult:
    """B5b: compute responsibility evidence (B5v2 facet/jaccard logic, unchanged).

    Does not emit PATCH/EXTEND/SKIP/NEW_DESIGN — that is B5c.
    """
    b3 = b3_prior or {}
    b4 = _extract_b4_prior(decision)

    mdsr_text = f"{mdsr.title}\n{mdsr.body_text}"
    mddr_text = f"{mddr.title}\n{mddr.body_text}" if mddr else ""

    cr_toks = _token_set(cr_text)
    mddr_toks = _token_set(mddr_text) if mddr else set()
    cr_content = _content_set(cr_text)
    mdsr_content = _content_set(mdsr_text)
    mddr_content = _content_set(mddr_text) if mddr else set()

    cr_mddr = sorted(cr_content & mddr_content)
    mdsr_mddr = sorted(mdsr_content & mddr_content)
    cr_mdsr = sorted(cr_content & mdsr_content)
    cr_mddr_all = sorted((cr_toks & mddr_toks) - STOPWORDS)

    actors_cr = set(_hits(cr_text, ACTOR_MARKERS))
    actors_mddr = set(_hits(mddr_text, ACTOR_MARKERS)) if mddr else set()
    actors_mdsr = set(_hits(mdsr_text, ACTOR_MARKERS))
    actions_cr = set(_hits(cr_text, ACTION_MARKERS))
    actions_mddr = set(_hits(mddr_text, ACTION_MARKERS)) if mddr else set()
    actions_mdsr = set(_hits(mdsr_text, ACTION_MARKERS))

    actor_shared = sorted((actors_cr & actors_mddr) | (actors_mdsr & actors_mddr & actors_cr))
    action_shared = sorted((actions_cr & actions_mddr) | (actions_mdsr & actions_mddr & actions_cr))
    action_cr_mddr = sorted(actions_cr & actions_mddr)

    obj_j_cr_mddr = _jaccard(cr_content, mddr_content) if mddr else 0.0
    obj_j_mdsr_mddr = _jaccard(mdsr_content, mddr_content) if mddr else 0.0
    tok_j_cr_mddr = _jaccard(cr_toks, mddr_toks) if mddr else 0.0

    concepts = [c for c in (b3.get("matched_concepts") or []) if isinstance(c, str)]
    req_spans = list(b3.get("candidate_spans") or []) or _spans(mdsr_text, concepts or cr_mdsr)
    design_spans = _spans(mddr_text, concepts or cr_mddr) if mddr else []

    evidence = PropagationEvidence(
        requirement_spans=req_spans[:4],
        design_spans=design_spans[:4],
        facet_detail={
            "cr_mddr_content": cr_mddr[:16],
            "mdsr_mddr_content": mdsr_mddr[:16],
            "cr_mdsr_content": cr_mdsr[:16],
            "object_jaccard_cr_mddr": round(obj_j_cr_mddr, 4),
            "object_jaccard_mdsr_mddr": round(obj_j_mdsr_mddr, 4),
            "token_jaccard_cr_mddr": round(tok_j_cr_mddr, 4),
            "actor_shared": actor_shared,
            "action_cr_mddr": action_cr_mddr,
            "b4_compatible": b4.get("compatible_facets") or [],
            "b4_conflicting": b4.get("conflicting_facets") or [],
        },
    )

    if mdsr.req_id and mddr and mdsr.req_id == mddr.req_id:
        evidence.direct_traceability.append("same_req_id")
    elif mddr is None:
        evidence.missing_information.append("design_block")
    else:
        evidence.conflicts.append("req_id_mismatch")

    if actor_shared:
        evidence.matched_facets.append("actor")
    if action_cr_mddr or action_shared:
        evidence.matched_facets.append("action")
    if cr_mddr or obj_j_cr_mddr >= 0.06:
        evidence.matched_facets.append("object")
    if b3.get("behavioral_overlap"):
        for k, v in (b3.get("behavioral_overlap") or {}).items():
            if v and f"b3_prior_{k}" not in evidence.matched_facets:
                evidence.matched_facets.append(f"b3_prior_{k}")

    if cr_mddr:
        evidence.matched_responsibilities.extend(cr_mddr[:8])
    if action_cr_mddr:
        evidence.matched_responsibilities.extend(action_cr_mddr[:4])

    confidence = 0.0
    confidence += 0.2 * min(3, len([f for f in evidence.matched_facets if not f.startswith("b3_")]))
    confidence += 0.25 * min(1.0, obj_j_cr_mddr / 0.12)
    confidence += 0.15 * min(1.0, len(cr_mddr) / 3)
    confidence += 0.1 if evidence.direct_traceability else 0.0
    confidence += 0.1 if action_cr_mddr else 0.0
    confidence = max(0.0, min(0.99, confidence))

    design_id = mddr.req_id if mddr else ""
    # PR-3: provenance sidecar — does not alter confidence / decision inputs above
    prov_bundle: ProvenanceBundle = build_alignment_provenance(
        cr_text=cr_text,
        mdsr_text=mdsr_text,
        mddr_text=mddr_text,
        requirement_id=mdsr.req_id,
        design_id=design_id,
        b3_prior=b3,
        b4_prior=b4,
        matched_facets=list(evidence.matched_facets),
        matched_responsibilities=list(evidence.matched_responsibilities),
        direct_traceability=list(evidence.direct_traceability),
        conflicts=list(evidence.conflicts),
        actor_shared=list(actor_shared),
        action_cr_mddr=list(action_cr_mddr),
        cr_mddr_content=list(cr_mddr),
        weak_tokens=WEAK_TOKENS,
        actor_markers=ACTOR_MARKERS,
    )
    evidence_dict = evidence.to_dict()
    evidence_dict["provenance"] = prov_bundle.to_dict()

    return AlignmentResult(
        requirement_id=mdsr.req_id,
        design_id=design_id,
        alignment="EVIDENCE_COMPUTED",
        evidence=evidence_dict,
        confidence=confidence,
        reason="B5b evidence computed (PR-1 parity; decision deferred to B5c).",
        provenance=prov_bundle.to_dict(),
        _signals={
            "propagation_evidence": evidence,
            "cr_mddr": cr_mddr,
            "mdsr_mddr": mdsr_mddr,
            "cr_mdsr": cr_mdsr,
            "cr_mddr_all": cr_mddr_all,
            "action_cr_mddr": action_cr_mddr,
            "actor_shared": actor_shared,
            "obj_j_cr_mddr": obj_j_cr_mddr,
            "obj_j_mdsr_mddr": obj_j_mdsr_mddr,
            "tok_j_cr_mddr": tok_j_cr_mddr,
            "cr_content": cr_content,
            "mddr_content": mddr_content,
            "mddr_is_none": mddr is None,
            "provenance": prov_bundle,
        },
    )


def decide_propagation(
    *,
    requirement_id: str,
    design_id: str,
    alignment: AlignmentResult,
    decision: ConsistencyDecision,
) -> PropagationDecisionResult:
    """B5c: map alignment evidence → propagation decision (B5v2 semantics unchanged)."""
    sig = alignment._signals or {}
    evidence: PropagationEvidence = sig.get("propagation_evidence") or PropagationEvidence()
    # Ensure we mutate the same evidence object used for structured_evidence parity
    if not isinstance(evidence, PropagationEvidence):
        evidence = PropagationEvidence()

    cr_mddr = list(sig.get("cr_mddr") or [])
    mdsr_mddr = list(sig.get("mdsr_mddr") or [])
    cr_mdsr = list(sig.get("cr_mdsr") or [])
    cr_mddr_all = list(sig.get("cr_mddr_all") or [])
    action_cr_mddr = list(sig.get("action_cr_mddr") or [])
    actor_shared = list(sig.get("actor_shared") or [])
    obj_j_cr_mddr = float(sig.get("obj_j_cr_mddr") or 0.0)
    obj_j_mdsr_mddr = float(sig.get("obj_j_mdsr_mddr") or 0.0)
    tok_j_cr_mddr = float(sig.get("tok_j_cr_mddr") or 0.0)
    cr_content: set[str] = set(sig.get("cr_content") or [])
    mddr_content: set[str] = set(sig.get("mddr_content") or [])
    mddr_is_none = bool(sig.get("mddr_is_none"))

    if mddr_is_none:
        return PropagationDecisionResult(
            requirement_id=requirement_id,
            design_id=design_id,
            decision="NEW_DESIGN_CANDIDATE",
            confidence=0.35,
            reason=(
                "No indexed MDDR block for this requirement; do not invent a design ID — "
                "propose NEW_DESIGN."
            ),
            evidence=evidence.to_dict(),
        )

    if decision.status == "CONFLICT":
        evidence.conflicts.append("b4_conflict")
        return PropagationDecisionResult(
            requirement_id=requirement_id,
            design_id=design_id,
            decision="SKIP",
            confidence=0.9,
            reason="B4 CONFLICT — refuse silent design propagation.",
            evidence=evidence.to_dict(),
        )

    boilerplate_only = (
        len(mdsr_mddr) >= 1
        and len(cr_mddr) == 0
        and not action_cr_mddr
        and obj_j_cr_mddr < 0.04
    )
    object_mismatch = (
        len(cr_content) >= 3
        and len(mddr_content) >= 3
        and obj_j_cr_mddr < 0.03
        and len(cr_mddr) == 0
        and bool(evidence.direct_traceability)
    )
    if boilerplate_only or object_mismatch:
        evidence.conflicts.append("responsibility_mismatch")
        if boilerplate_only:
            evidence.conflicts.append("boilerplate_overlap_without_cr")
        reason = (
            "Design ownership not evidenced for this CR: same-ID/theme-like overlap without "
            f"CR↔design object/action alignment (cr_mddr={cr_mddr[:6]}, mdsr_mddr={mdsr_mddr[:6]})."
        )
        return PropagationDecisionResult(
            requirement_id=requirement_id,
            design_id=design_id,
            decision="SKIP",
            confidence=0.75,
            reason=reason,
            evidence=evidence.to_dict(),
        )

    if decision.status == "NEEDS_REVIEW" or not decision.allow_auto_patch:
        evidence.missing_information.append("b4_not_auto_eligible")
        return PropagationDecisionResult(
            requirement_id=requirement_id,
            design_id=design_id,
            decision="NEEDS_REVIEW",
            confidence=0.4,
            reason=f"B4 not auto-patch eligible ({decision.status}); design deferred.",
            evidence=evidence.to_dict(),
        )

    strong_align = (
        len(cr_mddr) >= 2
        or (len(cr_mddr) >= 1 and (action_cr_mddr or actor_shared))
        or (obj_j_cr_mddr >= 0.08 and action_cr_mddr)
        or (tok_j_cr_mddr >= 0.1 and len(cr_mddr_all) >= 3 and action_cr_mddr)
    )
    extend_align = (
        not strong_align
        and (
            (len(cr_mddr) >= 1 and obj_j_mdsr_mddr >= 0.05)
            or (action_cr_mddr and obj_j_mdsr_mddr >= 0.04)
            or (len(cr_mdsr) >= 2 and len(mdsr_mddr) >= 2 and len(cr_mddr_all) >= 2)
        )
    )

    cr_novel = sorted(cr_content - mddr_content)
    if strong_align and len(cr_novel) >= 4 and len(cr_mddr) < 2:
        extend_align = True
        strong_align = False
        evidence.missing_information.append("design_scope_extension_needed")
    elif not strong_align and len(cr_novel) >= 3 and extend_align:
        evidence.missing_information.append("design_scope_extension_needed")

    confidence = float(alignment.confidence)

    if strong_align and not evidence.conflicts:
        evidence.matched_responsibilities = sorted(set(evidence.matched_responsibilities))[:12]
        return PropagationDecisionResult(
            requirement_id=requirement_id,
            design_id=design_id,
            decision="PATCH_EXISTING",
            confidence=confidence,
            reason=(
                f"CR↔design responsibility aligned (facets={evidence.matched_facets}, "
                f"cr_mddr={cr_mddr[:8]}); existing design may receive patch."
            ),
            evidence=evidence.to_dict(),
        )

    if extend_align and not evidence.conflicts:
        evidence.matched_responsibilities = sorted(set(evidence.matched_responsibilities))[:12]
        return PropagationDecisionResult(
            requirement_id=requirement_id,
            design_id=design_id,
            decision="EXTEND_EXISTING",
            confidence=confidence,
            reason=(
                f"Related design present; CR requires scope extension "
                f"(novel={cr_novel[:8]}, facets={evidence.matched_facets})."
            ),
            evidence=evidence.to_dict(),
        )

    if evidence.direct_traceability and (len(mdsr_mddr) >= 1 or obj_j_mdsr_mddr >= 0.05):
        evidence.missing_information.append("cr_design_alignment_unclear")
        return PropagationDecisionResult(
            requirement_id=requirement_id,
            design_id=design_id,
            decision="NEEDS_REVIEW",
            confidence=confidence,
            reason=(
                "Same-ID design present but insufficient CR↔design responsibility "
                "evidence for auto-patch."
            ),
            evidence=evidence.to_dict(),
        )

    evidence.missing_information.append("no_safe_design_owner")
    return PropagationDecisionResult(
        requirement_id=requirement_id,
        design_id=design_id,
        decision="NEW_DESIGN_CANDIDATE",
        confidence=confidence,
        reason="No safe existing design owner for this CR; propose NEW_DESIGN (no auto insert).",
        evidence=evidence.to_dict(),
    )


def assess_design_propagation(
    cr_text: str,
    mdsr: RequirementBlock,
    mddr: RequirementBlock | None,
    *,
    decision: ConsistencyDecision,
    b3_prior: dict[str, Any] | None = None,
) -> tuple[PropagationDecision, PropagationEvidence, float, str]:
    """Legacy façade: B5b + B5c (B5v2-compatible return tuple).

    Prefer explicit discover/align/decide in new code; this API is preserved.
    """
    align = align_design_candidate(
        cr_text, mdsr, mddr, decision=decision, b3_prior=b3_prior
    )
    decided = decide_propagation(
        requirement_id=mdsr.req_id,
        design_id=(mddr.req_id if mddr else ""),
        alignment=align,
        decision=decision,
    )
    pev = align._signals.get("propagation_evidence")
    if not isinstance(pev, PropagationEvidence):
        pev = PropagationEvidence()
        # Rebuild from decided evidence dict for safety
        ed = decided.evidence or {}
        pev = PropagationEvidence(
            requirement_spans=list(ed.get("requirement_spans") or []),
            design_spans=list(ed.get("design_spans") or []),
            matched_responsibilities=list(ed.get("matched_responsibilities") or []),
            matched_facets=list(ed.get("matched_facets") or []),
            direct_traceability=list(ed.get("direct_traceability") or []),
            conflicts=list(ed.get("conflicts") or []),
            missing_information=list(ed.get("missing_information") or []),
            facet_detail=dict(ed.get("facet_detail") or {}),
        )
    else:
        # Keep pev mutations from decide_propagation (conflicts/missing appended on same object)
        pass
    # Prefer decided.evidence as source of truth for structured fields after decide mutations
    ed = decided.evidence or {}
    pev.matched_responsibilities = list(ed.get("matched_responsibilities") or pev.matched_responsibilities)
    pev.matched_facets = list(ed.get("matched_facets") or pev.matched_facets)
    pev.conflicts = list(ed.get("conflicts") or pev.conflicts)
    pev.missing_information = list(ed.get("missing_information") or pev.missing_information)
    return decided.decision, pev, decided.confidence, decided.reason


def _decision_to_outcome(prop: PropagationDecision) -> PropagationOutcome:
    if prop in ("PATCH_EXISTING", "EXTEND_EXISTING"):
        return "PATCHED"
    if prop == "SKIP":
        return "SKIPPED_WITH_REASON"
    return "NEEDS_REVIEW"


def _allows_document_patch(prop: PropagationDecision) -> bool:
    return prop in ("PATCH_EXISTING", "EXTEND_EXISTING")


def proposed_mdsr_description(decision: ConsistencyDecision, cr_text: str) -> str | None:
    """Conservative description append from CR text (no Req-ID hardcoding).

    apply_b4_b5_patches additionally requires B5 allow_mdsr_patch so B4 CONSISTENT
    alone does not force MDSR append.
    """
    if not decision.allow_auto_patch or decision.status != "CONSISTENT":
        return None
    fields = decision.fields
    base = (fields.get("description") or "").strip()
    addition = _cr_append_sentence(cr_text, prefix="변경 요청 반영")
    if not addition:
        return None
    probe = addition.split(":", 1)[-1].strip()[:40]
    if probe and probe in base:
        return None
    return f"{base.rstrip()} {addition}".strip() if base else addition


def proposed_mddr_design_description(mddr: RequirementBlock, cr_text: str) -> str | None:
    """Append CR-aligned design note; never wipe existing design body."""
    base = (mddr.body_text or "").strip()
    if not base:
        base = (mddr.title or "").strip()
    addition = _cr_append_sentence(cr_text, prefix="설계 반영")
    if not addition:
        return None
    probe = addition.split(":", 1)[-1].strip()[:40]
    if probe and probe in base:
        return None
    if addition in base:
        return None
    return f"{base.rstrip()}\n{addition}".strip()


def _cr_append_sentence(cr_text: str, *, prefix: str, max_len: int = 280) -> str:
    cleaned = " ".join((cr_text or "").split())
    if len(cleaned) < 12:
        return ""
    snippet = cleaned if len(cleaned) <= max_len else cleaned[: max_len - 1].rstrip() + "…"
    return f"{prefix}: {snippet}"


def build_propagation_plan(
    cr_text: str,
    consistency: list[ConsistencyDecision],
    blocks: list[RequirementBlock],
    *,
    b3_decisions: list[dict[str, Any]] | None = None,
    return_stages: bool = False,
    acus: list[Any] | None = None,
    owner_selection_mode: Literal["auto", "acu", "legacy"] = "legacy",
) -> list[PropagationTrace] | tuple[list[PropagationTrace], dict[str, Any]]:
    """Orchestrator: B5a → B5b → B5c.

    PR-8: pass owner_selection_mode='auto' (or 'acu') to select owners via ACU v2 spans.
    Default remains 'legacy' for call-site compatibility / parity tests.
    Scenario runner activates ACU mode explicitly.
    Generation / apply still consume whole-CR text helpers (unchanged).
    """
    from document_ai.impact.atomic_change import AtomicChangeUnit, decompose_change_request
    from document_ai.impact.owner_activation import (
        build_owner_activation_diff,
        build_owner_activation_summary,
        resolve_owner_selection_mode,
        select_owners_via_acu,
    )

    units: list[AtomicChangeUnit]
    if acus is None:
        units = decompose_change_request(cr_text)
    else:
        units = list(acus)

    legacy_out = _build_propagation_plan_legacy(
        cr_text,
        consistency,
        blocks,
        b3_decisions=b3_decisions,
        return_stages=True,
    )
    assert isinstance(legacy_out, tuple)
    legacy_traces, staged = legacy_out

    effective, reason = resolve_owner_selection_mode(owner_selection_mode, units)

    if effective == "legacy":
        staged["owner_activation_summary"] = build_owner_activation_summary(
            effective_mode="legacy",
            mode_reason=reason,
            acus=units,
            legacy_traces=legacy_traces,
            active_traces=legacy_traces,
        )
        staged["owner_activation_diff"] = build_owner_activation_diff(
            legacy_traces=legacy_traces,
            acu_traces=legacy_traces,
        )
        staged["acu_owner_mapping"] = {
            "stage": "acu_owner_mapping",
            "mode": "legacy",
            "entries": [],
            "note": "Legacy CR-level owner selection; no ACU mapping.",
        }
        if return_stages:
            return legacy_traces, staged
        return legacy_traces

    acu_payload = select_owners_via_acu(
        cr_text=cr_text,
        acus=units,
        consistency=consistency,
        blocks=blocks,
        b3_decisions=b3_decisions,
    )
    acu_traces: list[PropagationTrace] = list(acu_payload["traces"])

    # Actual staged discovery/alignment/decision records from ACU path
    staged["design_candidates"] = acu_payload.get("stage_candidates") or []
    staged["responsibility_alignment"] = acu_payload.get("stage_alignments") or []
    staged["propagation_decisions"] = acu_payload.get("stage_decisions") or []
    staged["design_candidates_legacy_cr"] = staged.get("design_candidates_legacy_cr") or []
    # Preserve prior legacy stage under explicit keys if not already moved
    # (legacy function wrote into staged["design_candidates"] — already replaced above;
    # keep a copy from legacy_traces context via re-call fields stored before overwrite)
    staged["owner_activation_summary"] = build_owner_activation_summary(
        effective_mode="acu",
        mode_reason=reason,
        acus=units,
        legacy_traces=legacy_traces,
        active_traces=acu_traces,
        acu_payload=acu_payload,
    )
    staged["owner_activation_diff"] = build_owner_activation_diff(
        legacy_traces=legacy_traces,
        acu_traces=acu_traces,
        acu_summary=acu_payload.get("summary") or {},
    )
    staged["acu_owner_mapping"] = {
        "stage": "acu_owner_mapping",
        "mode": "acu",
        "entries": acu_payload.get("mapping") or [],
        "note": "Per-ACU owner evaluation; aggregated into requirement-level traces for apply.",
    }

    if return_stages:
        return acu_traces, staged
    return acu_traces


def _build_propagation_plan_legacy(
    cr_text: str,
    consistency: list[ConsistencyDecision],
    blocks: list[RequirementBlock],
    *,
    b3_decisions: list[dict[str, Any]] | None = None,
    return_stages: bool = False,
) -> list[PropagationTrace] | tuple[list[PropagationTrace], dict[str, Any]]:
    """Legacy façade / orchestrator: whole-CR B5a → B5b → B5c (B5v2 semantics).

    Actual path: same-ID only. Shadow path remains observational.
    """
    by_key = {(b.req_id, b.document_type): b for b in blocks}
    b3_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for d in b3_decisions or []:
        rid = d.get("candidate_id") or d.get("candidate")
        doc = d.get("document")
        if rid and doc:
            b3_by_key[(rid, doc)] = d

    traces: list[PropagationTrace] = []
    stage_candidates: list[dict[str, Any]] = []
    stage_alignments: list[dict[str, Any]] = []
    stage_decisions: list[dict[str, Any]] = []
    # PR-2 shadow observation (never feeds B5c / allow_mdsr_patch / apply)
    shadow_candidates_trace: list[dict[str, Any]] = []
    shadow_alignments_trace: list[dict[str, Any]] = []
    shadow_comparison_trace: list[dict[str, Any]] = []
    evidence_provenance_items: list[dict[str, Any]] = []
    evidence_provenance_by_req: dict[str, Any] = {}
    lineage_groups_all: dict[str, list[str]] = {}

    for decision in consistency:
        if decision.document != "MDSR":
            continue
        mdsr = by_key.get((decision.req_id, "MDSR"))
        b3_prior = _extract_b3_prior(b3_by_key.get((decision.req_id, "MDSR")), decision)
        b4_prior = _extract_b4_prior(decision)

        # ---------- ACTUAL PATH (same-ID only; must remain PR-1 parity) ----------
        candidates = discover_design_candidates(decision.req_id, by_key)
        stage_candidates.append(
            {
                "requirement_id": decision.req_id,
                "candidate_count": len(candidates),
                "candidates": [c.to_dict() for c in candidates],
                "path": "actual",
            }
        )
        mddr = candidates[0].block if candidates else None
        actual_design_id = mddr.req_id if mddr else None

        if not mdsr:
            traces.append(
                PropagationTrace(
                    source_mdsr_req_id=decision.req_id,
                    mdsr_consistency_status=decision.status,
                    impacted_mddr_candidate=f"MDDR {decision.req_id}",
                    propagation_reason="MDSR block missing from index",
                    outcome="NEEDS_REVIEW",
                    evidence=["missing_mdsr_block"],
                    requirement=decision.req_id,
                    design_candidate="",
                    propagation_decision="NEEDS_REVIEW",
                    structured_evidence={
                        "requirement_spans": [],
                        "design_spans": [],
                        "matched_responsibilities": [],
                        "matched_facets": [],
                        "direct_traceability": [],
                        "conflicts": [],
                        "missing_information": ["mdsr_block"],
                    },
                    allow_mdsr_patch=False,
                    b3_prior=b3_prior,
                    b4_prior=b4_prior,
                )
            )
            continue

        # B5b → B5c on ACTUAL candidate only (whole-CR query — legacy)
        align = align_design_candidate(
            cr_text, mdsr, mddr, decision=decision, b3_prior=b3_prior
        )
        decided = decide_propagation(
            requirement_id=decision.req_id,
            design_id=(mddr.req_id if mddr else ""),
            alignment=align,
            decision=decision,
        )
        stage_alignments.append(align.to_dict())
        stage_decisions.append(decided.to_dict())

        # PR-3: collect actual-path provenance (sidecar; does not alter B5c)
        if align.provenance:
            for it in align.provenance.get("evidence_items") or []:
                evidence_provenance_items.append(dict(it))
                gid = it.get("independent_group") or ""
                if gid:
                    lineage_groups_all.setdefault(gid, []).append(it.get("evidence_id") or "")
            evidence_provenance_by_req[decision.req_id] = {
                "path": "actual",
                "design_id": mddr.req_id if mddr else "",
                "summary": dict(align.provenance.get("summary") or {}),
                "lineage_groups": dict(align.provenance.get("lineage_groups") or {}),
            }

        prop = decided.decision
        conf = decided.confidence
        reason = decided.reason
        pev = align._signals.get("propagation_evidence")
        if not isinstance(pev, PropagationEvidence):
            ed = decided.evidence or {}
            pev = PropagationEvidence(
                requirement_spans=list(ed.get("requirement_spans") or []),
                design_spans=list(ed.get("design_spans") or []),
                matched_responsibilities=list(ed.get("matched_responsibilities") or []),
                matched_facets=list(ed.get("matched_facets") or []),
                direct_traceability=list(ed.get("direct_traceability") or []),
                conflicts=list(ed.get("conflicts") or []),
                missing_information=list(ed.get("missing_information") or []),
                facet_detail=dict(ed.get("facet_detail") or {}),
            )
        else:
            ed = decided.evidence or {}
            pev.matched_responsibilities = list(
                ed.get("matched_responsibilities") or pev.matched_responsibilities
            )
            pev.matched_facets = list(ed.get("matched_facets") or pev.matched_facets)
            pev.conflicts = list(ed.get("conflicts") or pev.conflicts)
            pev.missing_information = list(
                ed.get("missing_information") or pev.missing_information
            )

        before = (mddr.body_text or "")[:240] if mddr else ""
        design_label = (
            f"{mddr.req_id} ({mddr.document_type})" if mddr else f"MDDR {decision.req_id} (missing)"
        )
        aligned = prop in ("PATCH_EXISTING", "EXTEND_EXISTING")
        after = ""
        no_delta = False
        if aligned and mddr:
            design_text = proposed_mddr_design_description(mddr, cr_text)
            if design_text is None:
                no_delta = True
                reason = (
                    f"{reason} | No additional MDDR design delta from CR append "
                    "(already covered or empty CR)"
                )
            else:
                after = design_text[:240]

        if aligned and after:
            outcome: PropagationOutcome = "PATCHED"
            allow_docs = True
        elif prop == "SKIP":
            outcome = "SKIPPED_WITH_REASON"
            allow_docs = False
        elif aligned and no_delta:
            outcome = "SKIPPED_WITH_REASON"
            allow_docs = False
        else:
            outcome = _decision_to_outcome(prop)
            allow_docs = False

        flat = [
            reason,
            f"propagation_decision={prop}",
            f"matched_facets={pev.matched_facets}",
            f"conflicts={pev.conflicts}",
        ]
        if mddr:
            flat.append(f"mddr_title={mddr.title}")

        traces.append(
            PropagationTrace(
                source_mdsr_req_id=decision.req_id,
                mdsr_consistency_status=decision.status,
                impacted_mddr_candidate=design_label,
                propagation_reason=reason,
                outcome=outcome,
                evidence=flat,
                design_responsibility_aligned=aligned and not no_delta,
                before_snippet=before,
                after_snippet=after,
                requirement=decision.req_id,
                design_candidate=design_label if mddr else "",
                propagation_decision=prop,
                structured_evidence={
                    **pev.to_dict(),
                    "provenance": align.provenance or {},
                    "owner_selection": "legacy_cr",
                },
                confidence=conf,
                allow_mdsr_patch=allow_docs,
                b3_prior=b3_prior,
                b4_prior=b4_prior,
            )
        )

        # ---------- SHADOW PATH (observation only; no owner selection) ----------
        shadow_pool = discover_design_candidates_shadow(
            decision.req_id,
            by_key,
            b3_decisions=b3_decisions,
            max_candidates=SHADOW_CANDIDATE_CAP,
        )
        shadow_eval = evaluate_shadow_candidates(
            cr_text=cr_text,
            mdsr=mdsr,
            decision=decision,
            actual_design_id=actual_design_id,
            shadow_candidates=shadow_pool,
            b3_by_key=b3_by_key,
        )
        shadow_candidates_trace.append(
            {
                "requirement_id": decision.req_id,
                "actual_candidate": actual_design_id,
                "candidate_count": len(shadow_pool),
                "candidates": shadow_eval.get("candidates") or [],
                "path": "shadow",
                "note": "Shadow candidate comparison does not select a new owner.",
            }
        )
        shadow_alignments_trace.extend(shadow_eval.get("alignments") or [])
        shadow_comparison_trace.append(
            {
                "requirement_id": decision.req_id,
                "actual_candidate": actual_design_id,
                "actual_propagation_decision": prop,
                "note": "Shadow candidate comparison does not select a new owner.",
                "shadow_candidates": shadow_eval.get("shadow_candidates") or [],
            }
        )
        # Shadow provenance items (observation)
        for arow in shadow_eval.get("alignments") or []:
            pev_shadow = (arow.get("evidence") or {}).get("provenance") or {}
            for it in pev_shadow.get("evidence_items") or []:
                evidence_provenance_items.append({**dict(it), "shadow": True})
                gid = it.get("independent_group") or ""
                if gid:
                    lineage_groups_all.setdefault(gid, []).append(it.get("evidence_id") or "")

    staged = {
        "design_candidates": stage_candidates,
        "responsibility_alignment": stage_alignments,
        "propagation_decisions": stage_decisions,
        "design_candidates_legacy_cr": stage_candidates,
        "responsibility_alignment_legacy_cr": stage_alignments,
        "propagation_decisions_legacy_cr": stage_decisions,
        "design_candidates_shadow": shadow_candidates_trace,
        "responsibility_alignment_shadow": shadow_alignments_trace,
        "design_candidate_shadow_comparison": shadow_comparison_trace,
        "evidence_provenance": {
            "evidence_items": evidence_provenance_items,
            "lineage_groups": lineage_groups_all,
            "summary_by_requirement": evidence_provenance_by_req,
            "note": (
                "Provenance is observational for PR-3; "
                "Shadow candidate comparison does not select a new owner."
            ),
        },
    }
    if return_stages:
        return traces, staged
    return traces


def apply_b4_b5_patches(
    *,
    ref_mdsr: Path,
    ref_mddr: Path,
    out_mdsr: Path,
    out_mddr: Path,
    consistency: list[ConsistencyDecision],
    traces: list[PropagationTrace],
    cr_text: str,
    blocks: list[RequirementBlock],
) -> dict[str, Any]:
    """Copy references, patch eligible MDSR/MDDR, return patch report + hashes.

    MDSR safety gate (B5v2): B4 CONSISTENT alone is insufficient — corresponding
    trace must allow_mdsr_patch (PATCH_EXISTING / EXTEND_EXISTING with design evidence).
    """
    out_mdsr.parent.mkdir(parents=True, exist_ok=True)
    out_mddr.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ref_mdsr, out_mdsr)
    shutil.copy2(ref_mddr, out_mddr)

    by_key = {(b.req_id, b.document_type): b for b in blocks}
    mdsr_before = {
        rid: parse_requirement_fields(by_key[(rid, "MDSR")]).description
        for rid, doc in ((c.req_id, c.document) for c in consistency)
        if doc == "MDSR" and (rid, "MDSR") in by_key
    }
    allow_mdsr = {t.source_mdsr_req_id: t.allow_mdsr_patch for t in traces}

    doc_mdsr = load_document(out_mdsr)
    mdsr_patched: list[str] = []
    mdsr_skipped: list[dict[str, str]] = []
    for decision in consistency:
        if decision.document != "MDSR":
            continue
        if not allow_mdsr.get(decision.req_id, False):
            mdsr_skipped.append(
                {
                    "req_id": decision.req_id,
                    "reason": (
                        "B5 MDSR safety gate: design propagation not patch-eligible "
                        f"(B4 status={decision.status}; allow_auto_patch={decision.allow_auto_patch})"
                    ),
                }
            )
            continue
        text = proposed_mdsr_description(decision, cr_text)
        if not text:
            mdsr_skipped.append(
                {
                    "req_id": decision.req_id,
                    "reason": f"B4 status={decision.status}; auto_patch={decision.allow_auto_patch}",
                }
            )
            continue
        ok = patch_mdsr_description_only(doc_mdsr, decision.req_id, text, overwrite=True)
        if ok:
            mdsr_patched.append(decision.req_id)
        else:
            mdsr_skipped.append(
                {"req_id": decision.req_id, "reason": "patch_mdsr_description_only failed"}
            )
    doc_mdsr.save(str(out_mdsr))

    design_changes: list[dict[str, Any]] = []
    for tr in traces:
        if tr.outcome != "PATCHED":
            continue
        rid = tr.source_mdsr_req_id
        mddr = by_key.get((rid, "MDDR"))
        if not mddr:
            tr.outcome = "NEEDS_REVIEW"
            tr.propagation_reason += " | MDDR missing at apply time"
            tr.propagation_decision = "NEEDS_REVIEW"
            continue
        design_text = proposed_mddr_design_description(mddr, cr_text)
        if not design_text:
            tr.outcome = "SKIPPED_WITH_REASON"
            tr.propagation_reason = "No design delta at apply time"
            continue
        design_changes.append({"req_id": rid, "design_description": design_text})
        tr.after_snippet = design_text[:240]
        tr.patch_applied = True

    mddr_patched: list[str] = []
    if design_changes:
        mddr_patched = patch_document_file(out_mddr, patch_mddr_design_items, design_changes)

    patched_set = set(mddr_patched)
    for tr in traces:
        if tr.source_mdsr_req_id in patched_set:
            tr.outcome = "PATCHED"
            tr.patch_applied = True
        tr.mdsr_patched = tr.source_mdsr_req_id in mdsr_patched

    after_blocks = extract_req_blocks(load_document(out_mdsr))
    diffs: dict[str, Any] = {"mdsr": {}, "mddr": {}}
    for rid in sorted({c.req_id for c in consistency if c.document == "MDSR"}):
        before = mdsr_before.get(rid, "")
        after = before
        if rid in mdsr_patched and rid in after_blocks:
            labeled = after_blocks[rid].by_label().get("설명", "")
            unlabeled = "\n".join(after_blocks[rid].unlabeled_values())
            extracted = labeled or unlabeled
            if extracted.strip():
                after = extracted
        elif rid not in mdsr_patched:
            after = before
        diffs["mdsr"][rid] = {
            "before": before,
            "after": after,
            "changed": before.strip() != after.strip(),
            "patched": rid in mdsr_patched,
        }

    for tr in traces:
        diffs["mddr"][tr.source_mdsr_req_id] = {
            "before": tr.before_snippet,
            "after": tr.after_snippet,
            "outcome": tr.outcome,
            "propagation_decision": tr.propagation_decision,
            "changed": bool(tr.patch_applied),
        }

    return {
        "mdsr_out": str(out_mdsr).replace("\\", "/"),
        "mddr_out": str(out_mddr).replace("\\", "/"),
        "mdsr_sha256": sha256_file(out_mdsr),
        "mddr_sha256": sha256_file(out_mddr),
        "ref_mdsr_sha256": sha256_file(ref_mdsr),
        "ref_mddr_sha256": sha256_file(ref_mddr),
        "mdsr_patched_req_ids": mdsr_patched,
        "mdsr_skipped": mdsr_skipped,
        "mddr_patched_req_ids": mddr_patched,
        "mddr_unchanged_vs_ref": sha256_file(out_mddr) == sha256_file(ref_mddr),
        "diffs": diffs,
    }


def legacy_theme_design_aligns(mdsr: RequirementBlock, mddr: RequirementBlock) -> tuple[bool, str]:
    """Diagnostic-only lockout/UX/audit theme co-occurrence (not B5v2 decision path)."""
    mdsr_role_hint = (mdsr.title or "") + (mdsr.body_text or "")
    mddr_text = (mddr.title or "") + (mddr.body_text or "")
    if mdsr.req_id != mddr.req_id:
        return False, "Different Req IDs — not auto-linked by ID alone"
    pairs = [
        (("감사",), ("감사", "audit")),
        (("안내", "에러", "오류"), ("안내", "에러", "오류", "메시지")),
        (("과다", "차단", "임계", "잠금", "제한"), ("잠금", "임계", "제한", "차단", "실패")),
    ]
    for src_terms, dst_terms in pairs:
        if any(t in mdsr_role_hint for t in src_terms) and any(t in mddr_text for t in dst_terms):
            return True, f"LEGACY theme pair src={src_terms}"
    if "로그인" in mdsr_role_hint and "로그인" in mddr_text:
        return True, "LEGACY login co-occurrence"
    return False, "LEGACY: no theme pair"


def _design_aligns(mdsr: RequirementBlock, mddr: RequirementBlock, cr_text: str) -> tuple[bool, str]:
    """Compatibility wrapper — B5v2 assess (legacy themes not used)."""
    synthetic = ConsistencyDecision(
        req_id=mdsr.req_id,
        document=mdsr.document_type,
        status="CONSISTENT",
        reason="compat_wrapper",
        allow_auto_patch=True,
        fields={},
    )
    prop, _pev, _c, reason = assess_design_propagation(
        cr_text, mdsr, mddr, decision=synthetic, b3_prior={}
    )
    return prop in ("PATCH_EXISTING", "EXTEND_EXISTING"), reason
