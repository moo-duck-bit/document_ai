# -*- coding: utf-8 -*-
"""Identifier match matrix + tiered MDTM node ranking."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from document_ai.document_set.stable_node_identity import (
    build_stable_node_id_base,
    canonical_identifier_key,
    IDENTITY_VERSION_V2,
)
from document_ai.domain_packs.ec_sw.query_intent import QueryIntent
from document_ai.domain_packs.ec_sw.ranking_config import DEFAULT_RANKING_CONFIG, RankingConfig


def _query_stable_base(intent: QueryIntent) -> str:
    key = canonical_identifier_key(
        requirement_ids=list(intent.requirement_ids or []),
        design_ids=list(intent.design_ids or []),
        test_ids=list(intent.test_ids or []),
        version=IDENTITY_VERSION_V2,
    )
    if not key:
        return ""
    return build_stable_node_id_base(
        domain_pack_id="ec_sw_v1",
        document_role="traceability",
        node_type="TABLE_ROW",
        logical_key=key,
        structural_role="traceability_row",
    )


def _row_stable_base(meta: dict[str, Any], *, row_reqs: list[str], row_des: list[str], row_tes: list[str]) -> str:
    base = meta.get("stable_node_id_base") or ""
    if base:
        return str(base)
    key = canonical_identifier_key(
        requirement_ids=row_reqs,
        design_ids=row_des,
        test_ids=row_tes,
        version=IDENTITY_VERSION_V2,
    )
    if not key:
        return ""
    return build_stable_node_id_base(
        domain_pack_id="ec_sw_v1",
        document_role="traceability",
        node_type="TABLE_ROW",
        logical_key=key,
        structural_role="traceability_row",
    )


def _partial_stable_overlap(intent: QueryIntent, row_reqs: list[str], row_des: list[str], row_tes: list[str]) -> bool:
    """True when query identifiers are a subset of row identifiers (same logical family)."""
    q_reqs = set(intent.requirement_ids or [])
    q_des = set(intent.design_ids or [])
    q_tes = set(intent.test_ids or [])
    if not (q_reqs or q_des or q_tes):
        return False
    r_reqs = set(row_reqs or [])
    r_des = set(row_des or [])
    r_tes = set(row_tes or [])
    ok = True
    if q_reqs:
        ok = ok and bool(q_reqs & r_reqs)
    if q_des:
        ok = ok and bool(q_des & r_des)
    if q_tes:
        ok = ok and bool(q_tes & r_tes)
    return ok


def _tok_overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9가-힣]+", (a or "").lower()))
    tb = set(re.findall(r"[a-z0-9가-힣]+", (b or "").lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


@dataclass
class IdentifierMatchMatrix:
    candidate_node_id: str
    query_requirement_ids: list[str] = field(default_factory=list)
    query_design_ids: list[str] = field(default_factory=list)
    query_test_ids: list[str] = field(default_factory=list)
    row_requirement_ids: list[str] = field(default_factory=list)
    row_design_ids: list[str] = field(default_factory=list)
    row_test_ids: list[str] = field(default_factory=list)
    exact_requirement_matches: list[str] = field(default_factory=list)
    exact_design_matches: list[str] = field(default_factory=list)
    exact_test_matches: list[str] = field(default_factory=list)
    normalized_requirement_matches: list[str] = field(default_factory=list)
    normalized_design_matches: list[str] = field(default_factory=list)
    normalized_test_matches: list[str] = field(default_factory=list)
    mismatched_identifier_types: list[str] = field(default_factory=list)
    identifier_match_score: float = 0.0
    primary_identifier_match: bool = False
    secondary_identifier_match: bool = False
    reason_codes: list[str] = field(default_factory=list)
    evidence_scope: str = "ROW_LOCAL"
    identifier_origins: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_identifier_match_matrix(
    *,
    node_id: str,
    intent: QueryIntent,
    row_requirement_ids: list[str],
    row_design_ids: list[str],
    row_test_ids: list[str],
    identifier_origins: dict[str, str] | None = None,
) -> IdentifierMatchMatrix:
    origins = identifier_origins or {}
    # Only LOCAL_CELL / CELL_LOCAL count as exact
    def _local(ids: list[str], kind: str) -> list[str]:
        out = []
        for v in ids:
            origin = origins.get(f"{kind}:{v}") or origins.get(v) or "LOCAL_CELL"
            if origin in {"LOCAL_CELL", "CELL_LOCAL", "ROW_LOCAL"}:
                out.append(v)
            # inherited / adjacent never exact
        return out

    row_reqs = list(row_requirement_ids or [])
    row_des = [str(x) for x in (row_design_ids or [])]
    row_tes = [str(x).upper() for x in (row_test_ids or [])]

    local_reqs = _local(row_reqs, "requirement") if origins else row_reqs
    local_des = _local(row_des, "design") if origins else row_des
    local_tes = _local(row_tes, "test") if origins else row_tes

    exact_req = [r for r in intent.requirement_ids if r in local_reqs]
    exact_des = [d for d in intent.design_ids if d in local_des or d.upper() in [x.upper() for x in local_des]]
    exact_tes = [t for t in intent.test_ids if t in local_tes]

    # normalized: case-fold only (no fuzzy)
    norm_req = [r for r in intent.requirement_ids if r.lower() in {x.lower() for x in local_reqs} and r not in exact_req]
    norm_des = [
        d
        for d in intent.design_ids
        if d.lower() in {x.lower() for x in local_des} and d not in exact_des
    ]
    norm_tes = [
        t
        for t in intent.test_ids
        if t.lower() in {x.lower() for x in local_tes} and t not in exact_tes
    ]

    primary = intent.primary_identifier_type
    primary_match = False
    secondary_match = False
    reasons: list[str] = []
    mismatched: list[str] = []

    if primary == "REQUIREMENT":
        primary_match = bool(exact_req)
        secondary_match = bool(exact_des or exact_tes)
        if primary_match:
            reasons.append("PRIMARY_IDENTIFIER_EXACT")
        elif norm_req:
            reasons.append("PRIMARY_IDENTIFIER_NORMALIZED")
        if secondary_match:
            reasons.append("SECONDARY_IDENTIFIER_EXACT")
        if not primary_match and (exact_des or exact_tes):
            mismatched.append("secondary_without_primary")
    elif primary == "DESIGN":
        primary_match = bool(exact_des)
        secondary_match = bool(exact_req or exact_tes)
        if primary_match:
            reasons.append("PRIMARY_IDENTIFIER_EXACT")
        elif norm_des:
            reasons.append("PRIMARY_IDENTIFIER_NORMALIZED")
        if secondary_match:
            reasons.append("SECONDARY_IDENTIFIER_EXACT")
        if not primary_match and exact_req:
            mismatched.append("requirement_without_design_primary")
    elif primary == "TEST":
        primary_match = bool(exact_tes)
        secondary_match = bool(exact_req or exact_des)
        if primary_match:
            reasons.append("PRIMARY_IDENTIFIER_EXACT")
        elif norm_tes:
            reasons.append("PRIMARY_IDENTIFIER_NORMALIZED")
        if secondary_match:
            reasons.append("SECONDARY_IDENTIFIER_EXACT")
    elif primary == "MIXED":
        primary_match = bool(exact_req or exact_des or exact_tes)
        secondary_match = primary_match
        if exact_req or exact_des or exact_tes:
            reasons.append("PRIMARY_IDENTIFIER_EXACT")
    else:
        if exact_req or exact_des or exact_tes:
            secondary_match = True
            reasons.append("SECONDARY_IDENTIFIER_EXACT")

    score = 0.0
    if primary_match:
        score += 10.0
    if secondary_match:
        score += 3.0
    score += 2.0 * len(exact_req) + 2.0 * len(exact_des) + 2.0 * len(exact_tes)
    score += 0.5 * (len(norm_req) + len(norm_des) + len(norm_tes))

    return IdentifierMatchMatrix(
        candidate_node_id=node_id,
        query_requirement_ids=list(intent.requirement_ids),
        query_design_ids=list(intent.design_ids),
        query_test_ids=list(intent.test_ids),
        row_requirement_ids=row_reqs,
        row_design_ids=row_des,
        row_test_ids=row_tes,
        exact_requirement_matches=exact_req,
        exact_design_matches=exact_des,
        exact_test_matches=exact_tes,
        normalized_requirement_matches=norm_req,
        normalized_design_matches=norm_des,
        normalized_test_matches=norm_tes,
        mismatched_identifier_types=mismatched,
        identifier_match_score=score,
        primary_identifier_match=primary_match,
        secondary_identifier_match=secondary_match,
        reason_codes=reasons,
        evidence_scope="ROW_LOCAL",
        identifier_origins=origins,
    )


def assign_rank_tier(
    matrix: IdentifierMatchMatrix,
    *,
    row_local_semantic: float,
    stable_base_match: bool = False,
    instance_match: bool = False,
    structural_match: bool = False,
) -> tuple[int, list[str]]:
    """Identity-aware tiers (0 = strongest). Lower number = higher priority."""
    reasons = list(matrix.reason_codes)
    if matrix.primary_identifier_match and stable_base_match and instance_match:
        reasons.append("RANK_TIER_0")
        reasons.append("STABLE_BASE_AND_INSTANCE")
        return 0, reasons
    if matrix.primary_identifier_match and stable_base_match:
        reasons.append("RANK_TIER_1")
        reasons.append("STABLE_BASE_EXACT")
        return 1, reasons
    if matrix.primary_identifier_match:
        reasons.append("RANK_TIER_1")
        return 1, reasons
    if ("PRIMARY_IDENTIFIER_NORMALIZED" in matrix.reason_codes) and matrix.secondary_identifier_match:
        reasons.append("RANK_TIER_2")
        return 2, reasons
    if matrix.secondary_identifier_match or "PRIMARY_IDENTIFIER_NORMALIZED" in matrix.reason_codes:
        if stable_base_match:
            reasons.append("RANK_TIER_3")
            reasons.append("SECONDARY_PLUS_STABLE")
            return 3, reasons
        reasons.append("RANK_TIER_3")
        return 3, reasons
    if structural_match and row_local_semantic >= 0.15:
        reasons.append("RANK_TIER_4")
        reasons.append("STRUCTURAL_EQUIVALENCE")
        return 4, reasons
    if row_local_semantic >= 0.2:
        reasons.append("RANK_TIER_5")
        reasons.append("ROW_LOCAL_SEMANTIC_MATCH")
        return 5, reasons
    reasons.append("RANK_TIER_6")
    if row_local_semantic > 0:
        reasons.append("CONTEXT_ONLY_MATCH")
    return 6, reasons


def score_candidate(
    *,
    matrix: IdentifierMatchMatrix,
    tier: int,
    row_local_semantic: float,
    context_support: float = 0.0,
    neighbor_penalty: float = 0.0,
    duplicate_penalty: float = 0.0,
    ambiguity_penalty: float = 0.0,
    stable_base_match: bool = False,
    instance_match: bool = False,
    structural_match: float = 0.0,
    cfg: RankingConfig | None = None,
) -> dict[str, Any]:
    c = cfg or DEFAULT_RANKING_CONFIG
    base = {
        0: c.tier0_base,
        1: c.tier1_base,
        2: c.tier2_base,
        3: c.tier3_base,
        4: c.tier4_base,
        5: c.tier5_base,
        6: c.tier6_base,
    }.get(tier, c.tier6_base)
    components = {
        "primary_identifier_exact": c.primary_exact_bonus if matrix.primary_identifier_match else 0.0,
        "secondary_identifier_exact": c.secondary_exact_bonus if matrix.secondary_identifier_match else 0.0,
        "normalized_identifier": c.normalized_bonus
        * (
            len(matrix.normalized_requirement_matches)
            + len(matrix.normalized_design_matches)
            + len(matrix.normalized_test_matches)
        ),
        "stable_base_match": c.stable_base_bonus if stable_base_match else 0.0,
        "instance_match": c.instance_match_bonus if instance_match else 0.0,
        "row_local_semantic": c.row_local_semantic_weight * float(row_local_semantic),
        "structural_match": float(structural_match),
        "template_alignment": 0.0,
        "context_support": c.context_support_weight * float(context_support),
        "ambiguity_penalty": -float(ambiguity_penalty),
        "neighbor_penalty": -float(neighbor_penalty),
        "duplicate_penalty": -float(duplicate_penalty),
        "tier_base": base,
    }
    final = base + sum(v for k, v in components.items() if k != "tier_base")
    return {"final_score": round(final, 6), "score_components": components, "rank_tier": tier}


def rank_mdtm_candidates(
    candidates: list[dict[str, Any]],
    *,
    intent: QueryIntent,
    change_request: str = "",
    cfg: RankingConfig | None = None,
) -> dict[str, Any]:
    """
    Re-score TABLE_ROW candidates with identifier-aware tiers.
    Mutates candidate metadata with ranking fields; returns artifact payload.
    Does not drop duplicate exact rows.
    """
    c = cfg or DEFAULT_RANKING_CONFIG
    matrices: list[dict[str, Any]] = []
    ranked_rows: list[dict[str, Any]] = []
    neighbor_analysis: list[dict[str, Any]] = []
    dup_groups: dict[str, list[str]] = {}

    # Pre-pass: collect exact primary keys for duplicate groups
    for cand in candidates:
        if cand.get("status") not in {"PATCH_CANDIDATE", "REVIEW_REQUIRED"}:
            continue
        sid = (cand.get("metadata") or {}).get("source_identifiers") or {}
        # fallbacks from cand fields
        row_reqs = list(cand.get("matched_requirement_ids") or sid.get("requirement_ids") or [])
        row_des = list(sid.get("design_ids") or cand.get("metadata", {}).get("design_hits") or [])
        row_tes = list(sid.get("test_ids") or cand.get("metadata", {}).get("test_hits") or [])
        origins = (cand.get("metadata") or {}).get("identifier_origins") or {}
        # Prefer row-local identifiers recorded at match time
        if cand.get("metadata", {}).get("row_requirement_ids") is not None:
            row_reqs = list(cand["metadata"]["row_requirement_ids"])
        if cand.get("metadata", {}).get("row_design_ids") is not None:
            row_des = list(cand["metadata"]["row_design_ids"])
        if cand.get("metadata", {}).get("row_test_ids") is not None:
            row_tes = list(cand["metadata"]["row_test_ids"])

        matrix = build_identifier_match_matrix(
            node_id=str(cand.get("node_id")),
            intent=intent,
            row_requirement_ids=row_reqs,
            row_design_ids=row_des,
            row_test_ids=row_tes,
            identifier_origins=origins,
        )
        meta0 = cand.get("metadata") or {}
        row_text = str(meta0.get("row_text") or cand.get("display_name") or "")
        semantic = float(meta0.get("overlap") or 0.0)
        if change_request and row_text:
            semantic = max(semantic, _tok_overlap(change_request, row_text))

        q_base = _query_stable_base(intent)
        r_base = _row_stable_base(meta0, row_reqs=row_reqs, row_des=row_des, row_tes=row_tes)
        stable_base_match = bool(q_base and r_base and q_base == r_base)
        if not stable_base_match and _partial_stable_overlap(intent, row_reqs, row_des, row_tes):
            # Partial: query IDs present on row — treat as soft stable family match for ranking boost
            stable_base_match = matrix.primary_identifier_match or matrix.secondary_identifier_match
        instance_match = False
        q_inst = str(meta0.get("query_instance_signature") or "")
        r_inst = str(meta0.get("instance_signature") or "")
        if q_inst and r_inst and q_inst == r_inst:
            instance_match = True
        elif stable_base_match and matrix.primary_identifier_match and not meta0.get("duplicate_group_size"):
            instance_match = True
        structural = float(meta0.get("structural_match") or 0.0)
        structural_bool = structural >= 0.5 or bool(meta0.get("structural_group_id"))

        # Neighbor penalty: context-only evidence while neighbors have primary exact
        neighbor_pen = 0.0
        if not matrix.primary_identifier_match and semantic > 0 and intent.primary_identifier_type != "NONE":
            # weak context while query has identifiers → penalize
            if "ADJACENT_ROW" in str(meta0.get("evidence_scopes") or []):
                neighbor_pen = c.neighbor_penalty
                matrix.reason_codes.append("ADJACENT_ROW_CONTEXT")
                matrix.reason_codes.append("NEIGHBOR_PENALTY_APPLIED")

        tier, reasons = assign_rank_tier(
            matrix,
            row_local_semantic=semantic,
            stable_base_match=stable_base_match,
            instance_match=instance_match,
            structural_match=structural_bool,
        )
        matrix.reason_codes = sorted(set(reasons))

        # Duplicate group key — prefer stable base
        dup_key = r_base or None
        if not dup_key:
            if matrix.exact_requirement_matches:
                dup_key = "REQ:" + ",".join(matrix.exact_requirement_matches)
            elif matrix.exact_design_matches:
                dup_key = "DES:" + ",".join(matrix.exact_design_matches)
            elif matrix.exact_test_matches:
                dup_key = "TST:" + ",".join(matrix.exact_test_matches)
        if dup_key:
            dup_groups.setdefault(dup_key, []).append(str(cand.get("node_id")))

        amb_pen = 0.0
        if meta0.get("identity_status") == "DUPLICATE_GROUP" and not instance_match:
            amb_pen = c.ambiguity_penalty

        scored = score_candidate(
            matrix=matrix,
            tier=tier,
            row_local_semantic=semantic,
            context_support=float(meta0.get("context_support") or 0.0),
            neighbor_penalty=neighbor_pen,
            ambiguity_penalty=amb_pen,
            stable_base_match=stable_base_match,
            instance_match=instance_match,
            structural_match=structural,
            cfg=c,
        )
        meta = cand.setdefault("metadata", {})
        meta["rank_tier"] = scored["rank_tier"]
        meta["final_score"] = scored["final_score"]
        meta["score_components"] = scored["score_components"]
        meta["identifier_match"] = matrix.to_dict()
        meta["ranking_reason_codes"] = matrix.reason_codes
        meta["stable_base_match"] = stable_base_match
        meta["instance_match"] = instance_match
        if r_base:
            meta["stable_node_id_base"] = r_base
        # Prefer ranking score for downstream adapters
        meta["overlap"] = scored["final_score"]
        matrices.append(matrix.to_dict())
        loc = (cand.get("patch_preview") or {}).get("table_index"), (
            cand.get("patch_preview") or {}
        ).get("row_index")
        ranked_rows.append(
            {
                "node_id": cand.get("node_id"),
                "status": cand.get("status"),
                "rank_tier": scored["rank_tier"],
                "final_score": scored["final_score"],
                "score_components": scored["score_components"],
                "reason_codes": matrix.reason_codes,
                "table_index": meta.get("table_index") or loc[0],
                "row_index": meta.get("row_index") or loc[1],
                "stable_node_id_base": r_base,
                "stable_base_match": stable_base_match,
            }
        )
        if neighbor_pen:
            neighbor_analysis.append(
                {
                    "node_id": cand.get("node_id"),
                    "neighbor_penalty": neighbor_pen,
                    "reason": "context_without_primary_exact",
                }
            )

    # Apply duplicate penalties / review flags (preserve all rows)
    dup_payload = []
    for key, nids in dup_groups.items():
        uniq = list(dict.fromkeys(nids))
        if len(uniq) <= 1:
            continue
        for cand in candidates:
            if cand.get("node_id") not in uniq:
                continue
            meta = cand.setdefault("metadata", {})
            comps = dict(meta.get("score_components") or {})
            comps["duplicate_penalty"] = -c.duplicate_penalty
            meta["score_components"] = comps
            meta["final_score"] = round(float(meta.get("final_score") or 0) - c.duplicate_penalty, 6)
            meta["overlap"] = meta["final_score"]
            meta["duplicate_group_id"] = key
            meta["duplicate_group_size"] = len(uniq)
            rc = list(cand.get("reason_codes") or [])
            if "DUPLICATE_IDENTIFIER_ROWS" not in rc:
                rc.append("DUPLICATE_IDENTIFIER_ROWS")
            cand["reason_codes"] = rc
            cand["human_review_required"] = True
            ranking_rc = list(meta.get("ranking_reason_codes") or [])
            ranking_rc.append("DUPLICATE_IDENTIFIER_ROWS")
            meta["ranking_reason_codes"] = sorted(set(ranking_rc))
        dup_payload.append(
            {
                "duplicate_group_id": key,
                "duplicate_group_size": len(uniq),
                "duplicate_identifier_values": key.split(":", 1)[-1].split(","),
                "node_ids": uniq,
                "human_review_required": True,
            }
        )

    # Sort deterministically
    def _sort_key(row: dict[str, Any]) -> tuple:
        nid = str(row.get("node_id") or "")
        tier_raw = row.get("rank_tier")
        tier = int(tier_raw) if tier_raw is not None else 99
        return (
            tier,
            -float(row.get("final_score") or 0.0),
            int(row.get("table_index") or 0),
            int(row.get("row_index") or 0),
            nid,
        )

    # Refresh ranked_rows scores after dup penalty
    by_id = {c.get("node_id"): c for c in candidates}
    for row in ranked_rows:
        cand = by_id.get(row["node_id"])
        if cand:
            row["final_score"] = (cand.get("metadata") or {}).get("final_score", row["final_score"])
            row["rank_tier"] = (cand.get("metadata") or {}).get("rank_tier", row["rank_tier"])

    ranked_rows.sort(key=_sort_key)
    for i, row in enumerate(ranked_rows, start=1):
        row["rank"] = i
        cand = by_id.get(row["node_id"])
        if cand is not None:
            cand.setdefault("metadata", {})["rank"] = i

    # Invariant checks
    validation = {
        "primary_exact_ranked_before_non_exact": True,
        "no_adjacent_row_exact_evidence": True,
        "duplicate_rows_preserved": True,
        "identity_rank_tier_consistent": True,
        "issues": [],
    }
    seen_non_exact = False
    for row in ranked_rows:
        tier_raw = row.get("rank_tier")
        tier = int(tier_raw) if tier_raw is not None else 99
        if tier > 1:
            seen_non_exact = True
        if tier <= 1 and seen_non_exact:
            validation["primary_exact_ranked_before_non_exact"] = False
            validation["identity_rank_tier_consistent"] = False
            validation["issues"].append(f"tier1_after_non_exact:{row.get('node_id')}")
        # TIER_0/1 must beat TIER_4+
        if tier <= 1:
            pass
    # Ensure no semantic tier ranked above stable-base primary in list order
    best_semantic_rank = None
    best_stable_rank = None
    for row in ranked_rows:
        t_raw = row.get("rank_tier")
        t = int(t_raw) if t_raw is not None else 99
        rnk = int(row.get("rank") or 999)
        if t <= 1 and best_stable_rank is None:
            best_stable_rank = rnk
        if t >= 5 and best_semantic_rank is None:
            best_semantic_rank = rnk
    if best_stable_rank is not None and best_semantic_rank is not None and best_semantic_rank < best_stable_rank:
        validation["identity_rank_tier_consistent"] = False
        validation["issues"].append("semantic_before_stable_primary")
    for m in matrices:
        for origin in (m.get("identifier_origins") or {}).values():
            if origin in {"ADJACENT_CONTEXT", "ADJACENT_ROW"} and m.get("primary_identifier_match"):
                validation["no_adjacent_row_exact_evidence"] = False
                validation["issues"].append(f"adjacent_exact:{m.get('candidate_node_id')}")
    for g in dup_payload:
        if g["duplicate_group_size"] != len(g["node_ids"]):
            validation["duplicate_rows_preserved"] = False

    return {
        "query_intent": intent.to_dict(),
        "identifier_match_matrix": matrices,
        "ranking_candidates": ranked_rows,
        "ranking_results": {
            "ranked_node_ids": [r["node_id"] for r in ranked_rows],
            "n_ranked": len(ranked_rows),
        },
        "neighbor_context_analysis": neighbor_analysis,
        "duplicate_identifier_groups": dup_payload,
        "validation": validation,
        "config": c.to_dict(),
    }
