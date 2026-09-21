# -*- coding: utf-8 -*-
"""EC-SW semantic-only review evidence (PATCH forbidden)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from document_ai.document_set.schema import DocumentNode
from document_ai.domain_packs.ec_sw.identifier_parser import valid_canonical_requirement_ids
from document_ai.template.concept_normalization import (
    ACCESS_CONTROL,
    AUTHENTICATION,
    REQUIREMENT_INTENT,
    SECURITY,
    USER,
    concept_overlap,
    normalize_concepts,
    tokenize,
)

EvidenceStatus = Literal["STRONG_REVIEW", "WEAK_REVIEW", "NO_MATCH", "INVALID"]

DOMAIN_CONCEPTS = frozenset({AUTHENTICATION, ACCESS_CONTROL, SECURITY, USER})

DEFAULT_STRONG_THRESHOLD = 0.42
DEFAULT_WEAK_THRESHOLD = 0.28


@dataclass
class SemanticReviewThresholds:
    strong: float = DEFAULT_STRONG_THRESHOLD
    weak: float = DEFAULT_WEAK_THRESHOLD


@dataclass
class SemanticReviewEvidence:
    document_id: str
    node_id: str
    matched_terms: list[str]
    normalized_query_terms: list[str]
    normalized_node_terms: list[str]
    token_overlap: float
    character_similarity: float
    heading_similarity: float
    semantic_score: float
    evidence_status: EvidenceStatus
    reason_codes: list[str] = field(default_factory=list)
    supports_review: bool = False
    supports_patch: bool = False  # always false
    independent_group: str = "semantic"
    score_components: dict[str, float] = field(default_factory=dict)
    canonical_concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _char_ngram_sim(a: str, b: str, n: int = 2) -> float:
    def grams(s: str) -> set[str]:
        s = re.sub(r"\s+", "", (s or "").lower())
        if len(s) < n:
            return {s} if s else set()
        return {s[i : i + n] for i in range(len(s) - n + 1)}

    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / max(1, len(ga | gb))


def collect_semantic_review_evidence(
    *,
    change_request: str,
    nodes: list[DocumentNode],
    document_id: str = "MDTM",
    thresholds: SemanticReviewThresholds | None = None,
) -> list[SemanticReviewEvidence]:
    """Build per-node semantic REVIEW evidence. Never sets supports_patch."""
    th = thresholds or SemanticReviewThresholds()
    cr = change_request or ""
    if valid_canonical_requirement_ids(cr):
        # Exact path owned elsewhere; semantic pack stays quiet to avoid noise
        return []

    q_toks = tokenize(cr)
    q_concepts = normalize_concepts(cr)
    domain_hits = q_concepts & DOMAIN_CONCEPTS
    has_intent = REQUIREMENT_INTENT in q_concepts
    results: list[SemanticReviewEvidence] = []

    for node in nodes:
        if node.node_type != "TABLE_ROW":
            continue
        text = node.text or ""
        n_toks = tokenize(text)
        n_concepts = normalize_concepts(text)
        # Also consider display name
        n_toks |= tokenize(node.display_name or "")
        inter = sorted(q_toks & n_toks)
        tok_ov = len(q_toks & n_toks) / max(1, len(q_toks | n_toks)) if q_toks else 0.0
        char_sim = _char_ngram_sim(cr, text)
        head_sim = _char_ngram_sim(cr, node.display_name or "")
        c_ov = concept_overlap(q_concepts, n_concepts)

        # Sparse MDTM rows: boost when CR has domain+intent and row is a requirement row
        sid = node.source_identifiers or {}
        req_ids = list(sid.get("requirement_ids") or [])
        sparse_boost = 0.0
        reasons: list[str] = ["NO_EXACT_IDENTIFIER", "PATCH_FORBIDDEN_SEMANTIC_ONLY"]
        if req_ids and len(domain_hits) >= 2 and has_intent:
            sparse_boost = 0.40 + 0.05 * min(2, len(domain_hits))
            reasons.extend(["SEMANTIC_REVIEW_CANDIDATE", "SEMANTIC_NODE_MATCH"])
            # attach domain terms as matched conceptual terms
            inter = sorted(set(inter) | {t for t in q_toks if any(c.lower() in t or t in c.lower() for c in [])})
            # use concept labels as matched_terms for provenance
            inter = sorted(set(inter) | {c.lower() for c in domain_hits})

        score = (
            0.35 * tok_ov
            + 0.20 * char_sim
            + 0.15 * head_sim
            + 0.15 * c_ov
            + sparse_boost
        )
        # Ambiguity later; per-node score first
        components = {
            "token_overlap": round(tok_ov, 4),
            "character_similarity": round(char_sim, 4),
            "heading_similarity": round(head_sim, 4),
            "concept_overlap": round(c_ov, 4),
            "sparse_requirement_row_boost": round(sparse_boost, 4),
        }

        if score >= th.strong:
            status: EvidenceStatus = "STRONG_REVIEW"
            reasons.append("SEMANTIC_TOKEN_OVERLAP" if tok_ov > 0 else "SEMANTIC_CHARACTER_SIMILARITY")
            supports_review = True
        elif score >= th.weak:
            status = "WEAK_REVIEW"
            reasons.append("SEMANTIC_SCORE_LOW")
            supports_review = False
        else:
            status = "NO_MATCH"
            supports_review = False

        results.append(
            SemanticReviewEvidence(
                document_id=document_id,
                node_id=node.node_id,
                matched_terms=inter[:20],
                normalized_query_terms=sorted(q_toks)[:40],
                normalized_node_terms=sorted(n_toks)[:40],
                token_overlap=round(tok_ov, 4),
                character_similarity=round(char_sim, 4),
                heading_similarity=round(head_sim, 4),
                semantic_score=round(score, 4),
                evidence_status=status,
                reason_codes=sorted(set(reasons)),
                supports_review=supports_review,
                supports_patch=False,
                independent_group=f"semantic:{node.node_id}",
                score_components=components,
                canonical_concepts=sorted(q_concepts),
            )
        )

    # Rank deterministic
    results.sort(key=lambda e: (-e.semantic_score, e.document_id, e.node_id))
    strong = [e for e in results if e.evidence_status == "STRONG_REVIEW"]
    if len(strong) > 1:
        for e in strong:
            if "SEMANTIC_AMBIGUOUS" not in e.reason_codes:
                e.reason_codes.append("SEMANTIC_AMBIGUOUS")
    return results


def semantic_to_review_candidates(
    evidences: list[SemanticReviewEvidence],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    out = []
    for e in evidences:
        if not e.supports_review or e.evidence_status != "STRONG_REVIEW":
            continue
        out.append(
            {
                "item_id": f"SEM-{e.node_id}",
                "candidate_id": f"SEM-{e.node_id}",
                "document_id": e.document_id,
                "node_id": e.node_id,
                "status": "REVIEW_REQUIRED",
                "overlap": e.semantic_score,
                "reason_codes": e.reason_codes,
                "human_review_required": True,
                "metadata": {
                    "overlap": e.semantic_score,
                    "evidence_type": "SEMANTIC_SECTION_MATCH",
                    "supports_patch": False,
                    "matched_terms": e.matched_terms,
                },
            }
        )
        if len(out) >= limit:
            break
    return out


def write_semantic_review_artifacts(out_dir: Path, evidences: list[SemanticReviewEvidence]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    strong = [e for e in evidences if e.evidence_status == "STRONG_REVIEW"]
    weak = [e for e in evidences if e.evidence_status == "WEAK_REVIEW"]
    summary = {
        "total": len(evidences),
        "strong_review": len(strong),
        "weak_review": len(weak),
        "patch_candidates_from_semantic": 0,
        "supports_patch_always_false": True,
    }
    validation = {
        "ok": all(not e.supports_patch for e in evidences),
        "issues": [] if all(not e.supports_patch for e in evidences) else ["semantic_supports_patch"],
        "invariants": ["no_semantic_only_patch", "review_requires_substantive_evidence"],
    }
    files = {
        "ec_sw_semantic_review_evidence.json": [e.to_dict() for e in evidences],
        "ec_sw_semantic_review_candidates.json": semantic_to_review_candidates(evidences),
        "ec_sw_semantic_review_summary.json": summary,
        "ec_sw_semantic_review_validation.json": validation,
    }
    written = {}
    for name, payload in files.items():
        path = out_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written[name] = str(path).replace("\\", "/")
    return written
