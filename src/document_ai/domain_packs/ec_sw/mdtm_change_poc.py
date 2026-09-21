# -*- coding: utf-8 -*-
"""MDTM Change POC — map requirement impacts to MDTM TABLE_ROW candidates."""

from __future__ import annotations

import re
from typing import Any, Iterable

from document_ai.document_set.schema import ChangeCandidate, DocumentNode
from document_ai.domain_packs.ec_sw.mdtm_schema import extract_requirement_ids, normalize_req_id
from document_ai.domain_packs.ec_sw.node_ranking import rank_mdtm_candidates
from document_ai.domain_packs.ec_sw.query_intent import parse_query_intent


def extract_requirement_ids_from_inputs(
    *,
    change_request: str | None = None,
    requirement_ids: Iterable[str] | None = None,
    impact_results: list[dict[str, Any]] | None = None,
) -> list[str]:
    found: list[str] = []

    def _add(rid: str | None) -> None:
        if not rid:
            return
        n = normalize_req_id(rid)
        if not n:
            if isinstance(rid, str) and rid.startswith("Req. "):
                n = normalize_req_id(rid)
            if not n:
                return
        if n not in found:
            found.append(n)

    for rid in requirement_ids or []:
        _add(str(rid))
    for item in impact_results or []:
        judgment = str(item.get("judgment") or item.get("status") or "").upper()
        if judgment and judgment not in {"IMPACTED", "PATCH", "CONSISTENT"}:
            pass
        rid = item.get("requirement_id") or item.get("candidate_id") or item.get("req_id")
        if rid:
            _add(str(rid))
        if judgment == "IMPACTED" and rid:
            _add(str(rid))
    if change_request:
        for rid in extract_requirement_ids(change_request):
            _add(rid)
    out: list[str] = []
    for r in found:
        nr = normalize_req_id(r) or (r if isinstance(r, str) and r.startswith("Req. ") else None)
        nr = normalize_req_id(nr or "")
        if nr and nr not in out:
            out.append(nr)
    return out


def _token_overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9가-힣]+", (a or "").lower()))
    tb = set(re.findall(r"[a-z0-9가-힣]+", (b or "").lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def run_mdtm_change_poc(
    nodes: list[DocumentNode],
    *,
    change_request: str = "",
    requirement_ids: list[str] | None = None,
    impact_results: list[dict[str, Any]] | None = None,
    design_ids: list[str] | None = None,
    test_ids: list[str] | None = None,
) -> dict[str, Any]:
    intent = parse_query_intent(
        change_request,
        requirement_ids=requirement_ids
        or extract_requirement_ids_from_inputs(
            change_request=change_request,
            requirement_ids=requirement_ids,
            impact_results=impact_results,
        ),
        design_ids=design_ids,
        test_ids=test_ids,
    )
    # Merge impact-derived requirement ids into intent
    extra_reqs = extract_requirement_ids_from_inputs(
        change_request=None,
        requirement_ids=requirement_ids,
        impact_results=impact_results,
    )
    for r in extra_reqs:
        if r not in intent.requirement_ids:
            intent.requirement_ids.append(r)

    reqs = list(intent.requirement_ids)
    design_q = list(intent.design_ids)
    test_q = list(intent.test_ids)

    candidates: list[ChangeCandidate] = []
    req_hit_nodes: dict[str, list[str]] = {r: [] for r in reqs}

    for i, node in enumerate(nodes):
        if node.node_type != "TABLE_ROW":
            candidates.append(
                ChangeCandidate(
                    candidate_id=f"MC-{i:04d}",
                    node_id=node.node_id,
                    document_id=node.document_id,
                    status="INVALID",
                    reason_codes=["not_table_row"],
                    human_review_required=True,
                )
            )
            continue

        sid = node.source_identifiers or {}
        row_reqs = list(sid.get("requirement_ids") or [])
        row_designs = [str(x) for x in (sid.get("design_ids") or [])]
        row_tests = [str(x).upper() for x in (sid.get("test_ids") or [])]
        cell_values = list(sid.get("cell_values") or [])
        # Provenance: indexer extracts from row cells only → LOCAL_CELL
        identifier_origins = {
            **{f"requirement:{r}": "LOCAL_CELL" for r in row_reqs},
            **{f"design:{d}": "LOCAL_CELL" for d in row_designs},
            **{f"test:{t}": "LOCAL_CELL" for t in row_tests},
        }

        exact = [r for r in reqs if r in row_reqs]
        for r in exact:
            req_hit_nodes.setdefault(r, []).append(node.node_id)

        design_hits = [
            d
            for d in design_q
            if d in row_designs or d.upper() in [x.upper() for x in row_designs]
        ]
        test_hits = [t for t in test_q if t in row_tests]
        overlap = _token_overlap(change_request, node.text) if change_request else 0.0

        status = "UNRELATED"
        reasons: list[str] = []
        evidence: list[str] = []
        review = True
        patch_preview = None

        primary = intent.primary_identifier_type

        if exact and primary in {"REQUIREMENT", "MIXED", "NONE"}:
            # Exact Req → PATCH only when requirement is primary or mixed/none
            # When DESIGN/TEST is primary, Req match is secondary evidence (REVIEW)
            if primary in {"DESIGN", "TEST"}:
                status = "REVIEW_REQUIRED"
                reasons.append("secondary_requirement_id_match")
                evidence.extend([f"requirement_id:{r}" for r in exact])
                review = True
            else:
                status = "PATCH_CANDIDATE"
                reasons.append("exact_requirement_id_match")
                evidence.extend([f"requirement_id:{r}" for r in exact])
                review = False
                col_index = max(0, len(cell_values) - 1)
                original = cell_values[col_index] if cell_values else ""
                note = f"[CR] {', '.join(exact)} impact — review traceability"
                proposed = original
                if original and note not in original:
                    proposed = f"{original} | {note}" if original else note
                elif not original:
                    proposed = note
                patch_preview = {
                    "document_id": node.document_id,
                    "node_id": node.node_id,
                    "table_index": node.source_locator.get("table_index"),
                    "row_index": node.source_locator.get("row_index"),
                    "column_index": col_index,
                    "original_text": original,
                    "proposed_text": proposed,
                    "operation": "UPDATE",
                    "reason_codes": ["exact_requirement_id_match"],
                    "human_review_required": False,
                    "source_identifiers": {
                        "requirement_ids": row_reqs,
                        "design_ids": sid.get("design_ids") or [],
                        "test_ids": sid.get("test_ids") or [],
                    },
                    "row_wide_replacement": False,
                    "generated_id": False,
                }
        elif design_hits or test_hits:
            status = "REVIEW_REQUIRED"
            if design_hits and primary == "DESIGN":
                reasons.append("exact_design_id_match")
            elif test_hits and primary == "TEST":
                reasons.append("exact_test_id_match")
            else:
                reasons.append("indirect_design_or_test_match")
            evidence.extend([f"design:{d}" for d in design_hits])
            evidence.extend([f"test:{t}" for t in test_hits])
            review = True
        elif not row_reqs and not row_designs and not row_tests:
            status = "REVIEW_REQUIRED" if overlap >= 0.15 else "UNRELATED"
            reasons.append("no_identifiers_in_row")
            if overlap >= 0.15:
                reasons.append("weak_text_overlap")
            review = True
        elif overlap >= 0.2 and not exact:
            status = "REVIEW_REQUIRED"
            reasons.append("semantic_or_lexical_overlap_only")
            evidence.append(f"overlap:{overlap:.3f}")
            review = True
        else:
            status = "UNRELATED"
            reasons.append("no_match")

        # Never allow auto patch on semantic-only / design-only / test-only
        if status == "PATCH_CANDIDATE" and "exact_requirement_id_match" not in reasons:
            status = "REVIEW_REQUIRED"
            review = True
            patch_preview = None

        candidates.append(
            ChangeCandidate(
                candidate_id=f"MC-{i:04d}",
                node_id=node.node_id,
                document_id=node.document_id,
                status=status,
                matched_requirement_ids=exact,
                evidence=evidence,
                reason_codes=reasons,
                human_review_required=review,
                patch_preview=patch_preview,
                metadata={
                    "display_name": node.display_name,
                    "design_hits": design_hits,
                    "test_hits": test_hits,
                    "overlap": round(overlap, 4),
                    "row_text": node.text,
                    "row_requirement_ids": row_reqs,
                    "row_design_ids": row_designs,
                    "row_test_ids": row_tests,
                    "identifier_origins": identifier_origins,
                    "table_index": node.source_locator.get("table_index"),
                    "row_index": node.source_locator.get("row_index"),
                    "source_identifiers": {
                        "requirement_ids": row_reqs,
                        "design_ids": row_designs,
                        "test_ids": row_tests,
                    },
                    "evidence_scopes": ["ROW_LOCAL", "CELL_LOCAL"],
                    "legacy_node_id": node.node_id,
                    "stable_node_id": (node.metadata or {}).get("stable_node_id")
                    or (node.source_identifiers or {}).get("stable_node_id"),
                    "stable_node_id_base": (node.metadata or {}).get("stable_node_id_base")
                    or (node.source_identifiers or {}).get("stable_node_id_base"),
                    "stable_node_id_v1": (node.metadata or {}).get("stable_node_id_v1"),
                    "stable_node_id_v2": (node.metadata or {}).get("stable_node_id_v2"),
                    "instance_signature": (node.metadata or {}).get("instance_signature")
                    or (node.source_identifiers or {}).get("instance_signature"),
                    "duplicate_instance_key": (node.metadata or {}).get("duplicate_instance_key"),
                    "identity_status": ((node.metadata or {}).get("stable_identity") or {}).get(
                        "identity_status"
                    ),
                    "identifier_values": list(
                        dict.fromkeys([*row_reqs, *row_designs, *row_tests])
                    ),
                    "logical_identity_resolved": True,
                    "writer_executable": False,
                },
            )
        )

    for rid, nids in req_hit_nodes.items():
        if len(set(nids)) > 1:
            for c in candidates:
                if rid in c.matched_requirement_ids:
                    c.human_review_required = True
                    if "duplicate_requirement_rows" not in c.reason_codes:
                        c.reason_codes.append("duplicate_requirement_rows")

    ranking = rank_mdtm_candidates(
        [c.to_dict() for c in candidates],
        intent=intent,
        change_request=change_request,
    )
    from document_ai.document_set.node_reconciliation import reconcile_node_candidates

    ranked_dicts = []
    score_by_pre = {r["node_id"]: r for r in ranking.get("ranking_candidates") or []}
    for c in candidates:
        d = c.to_dict()
        r = score_by_pre.get(c.node_id)
        if r:
            d.setdefault("metadata", {}).update(
                {
                    "final_score": r.get("final_score"),
                    "rank_tier": r.get("rank_tier"),
                    "rank": r.get("rank"),
                    "score_components": r.get("score_components"),
                    "stable_node_id_base": (c.metadata or {}).get("stable_node_id_base"),
                }
            )
        ranked_dicts.append(d)
    reconciliation = reconcile_node_candidates(
        [d for d in ranked_dicts if d.get("status") in {"PATCH_CANDIDATE", "REVIEW_REQUIRED"}],
        document_id=str(candidates[0].document_id if candidates else ""),
    )
    # Apply ranking metadata back onto ChangeCandidate objects
    by_id = {c.node_id: c for c in candidates}
    for row in ranking.get("ranking_candidates") or []:
        c = by_id.get(row["node_id"])
        if c is None:
            continue
        meta = dict(c.metadata or {})
        # find from ranking matrices
        for m in ranking.get("identifier_match_matrix") or []:
            if m.get("candidate_node_id") == c.node_id:
                meta["identifier_match"] = m
                break
        for cand_dict in ranking.get("ranking_candidates") or []:
            if cand_dict.get("node_id") == c.node_id:
                meta["rank_tier"] = cand_dict.get("rank_tier")
                meta["final_score"] = cand_dict.get("final_score")
                meta["rank"] = cand_dict.get("rank")
                meta["score_components"] = cand_dict.get("score_components")
                meta["overlap"] = cand_dict.get("final_score")
                break
        # duplicate flags from ranking artifact
        for g in ranking.get("duplicate_identifier_groups") or []:
            if c.node_id in (g.get("node_ids") or []):
                c.human_review_required = True
                if "DUPLICATE_IDENTIFIER_ROWS" not in c.reason_codes:
                    c.reason_codes.append("DUPLICATE_IDENTIFIER_ROWS")
                meta["duplicate_group_id"] = g.get("duplicate_group_id")
                meta["duplicate_group_size"] = g.get("duplicate_group_size")
        c.metadata = meta

    # Re-build dicts after metadata update
    candidate_dicts = [c.to_dict() for c in candidates]
    # Ensure final_score on dicts from ranking sort order
    score_by = {r["node_id"]: r for r in ranking.get("ranking_candidates") or []}
    for d in candidate_dicts:
        r = score_by.get(d.get("node_id"))
        if r:
            d.setdefault("metadata", {})["final_score"] = r.get("final_score")
            d["metadata"]["rank_tier"] = r.get("rank_tier")
            d["metadata"]["rank"] = r.get("rank")
            d["metadata"]["overlap"] = r.get("final_score")
            d["metadata"]["score_components"] = r.get("score_components")

    patch_candidates = [c for c in candidates if c.status == "PATCH_CANDIDATE"]
    review_required = [c for c in candidates if c.status == "REVIEW_REQUIRED"]
    unrelated = [c for c in candidates if c.status == "UNRELATED"]
    invalid = [c for c in candidates if c.status == "INVALID"]

    return {
        "input_requirement_ids": reqs,
        "query_intent": intent.to_dict(),
        "ranking": ranking,
        "reconciliation": reconciliation,
        "candidates": candidates,
        "candidate_dicts": candidate_dicts,
        "patch_candidates": [c.to_dict() for c in patch_candidates],
        "review_required": [c.to_dict() for c in review_required],
        "unrelated_count": len(unrelated),
        "invalid_count": len(invalid),
        "patch_previews": [
            c.patch_preview for c in patch_candidates if c.patch_preview is not None
        ],
        "summary": {
            "patch_candidate_count": len(patch_candidates),
            "review_required_count": len(review_required),
            "unrelated_count": len(unrelated),
            "invalid_count": len(invalid),
            "auto_patch_allowed_without_review": sum(
                1 for c in patch_candidates if not c.human_review_required
            ),
            "primary_identifier_type": intent.primary_identifier_type,
            "reconciled_candidate_count": reconciliation.get("n_reconciled"),
        },
    }
