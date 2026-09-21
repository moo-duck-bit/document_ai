# -*- coding: utf-8 -*-
"""Adapt workflow outputs to benchmark predictions (no gold reads)."""

from __future__ import annotations

from typing import Any

from document_ai.evaluation.document_set.schema import STATUS_MAP

# Explicit document decision → evaluation status
DOCUMENT_STATUS_MAP = {
    "IMPACTED": "IMPACTED",
    "REVIEW_REQUIRED": "REVIEW_REQUIRED",
    "UNRELATED": "UNRELATED",
    "INVALID": "INVALID",
}


def _node_score(c: dict[str, Any], *, default: float) -> float:
    meta = c.get("metadata") or {}
    for key in ("final_score", "ranking_score", "overlap"):
        if meta.get(key) is not None:
            return float(meta[key])
    if c.get("overlap") is not None:
        return float(c["overlap"])
    return float(default)


def _extended_node_metadata(c: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    aligned_doc = meta.get("aligned_document_node_id")
    base = {
        "score_components": meta.get("score_components") or meta.get("structural_score_components"),
        "identifier_match": meta.get("identifier_match"),
        "stable_node_id": meta.get("stable_node_id"),
        "stable_node_id_base": meta.get("stable_node_id_base"),
        "stable_node_id_v1": meta.get("stable_node_id_v1"),
        "stable_node_id_v2": meta.get("stable_node_id_v2"),
        "instance_signature": meta.get("instance_signature"),
        "duplicate_instance_key": meta.get("duplicate_instance_key"),
        "legacy_node_id": meta.get("legacy_node_id") or c.get("node_id"),
        "writer_executable": False,
        "reconciled_candidate_id": meta.get("reconciled_candidate_id"),
        "structural_role": meta.get("structural_role"),
        "query_intent": meta.get("query_intent"),
        "template_node_id": meta.get("template_node_id"),
        "alignment_confidence": meta.get("alignment_confidence"),
        "evaluation_equivalent": meta.get("evaluation_equivalent"),
        "parent_section_id": meta.get("parent_section_id"),
        "physical": meta.get("physical"),
        "virtual_target": meta.get("virtual_target"),
        "node_alignments": meta.get("node_alignments"),
        "structural_equivalence_groups": meta.get("structural_equivalence_groups"),
        "structural_score_components": meta.get("structural_score_components"),
        "domain": meta.get("domain") or c.get("domain"),
        "template_id": meta.get("template_id") or c.get("template_id"),
        "document_node_id": aligned_doc or meta.get("document_node_id") or c.get("document_node_id"),
        "canonical_concepts": meta.get("canonical_concepts"),
        "alignment_ids": meta.get("alignment_ids"),
        "stable_reference": meta.get("stable_reference") or meta.get("stable_node_id"),
        "virtual": meta.get("virtual"),
        "supports_review": meta.get("supports_review", c.get("status") == "REVIEW_REQUIRED"),
        "supports_patch": meta.get("supports_patch", False),
        "reason_codes": c.get("reason_codes") or meta.get("reason_codes") or meta.get("ranking_reason_codes"),
    }
    return base


def adapt_workflow_prediction(case_id: str, workflow: dict[str, Any]) -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    meta = workflow.get("metadata") or {}
    decisions = list(workflow.get("document_impact_decisions") or [])
    if not decisions:
        decisions = list(meta.get("document_impact_decisions") or [])

    decided: dict[str, dict[str, Any]] = {
        d["document_id"]: d for d in decisions if d.get("document_id")
    }

    if decided:
        for did, d in decided.items():
            status = DOCUMENT_STATUS_MAP.get(d.get("predicted_status"), "UNRELATED")
            stages = d.get("source_stages") or []
            docs.append(
                {
                    "case_id": case_id,
                    "document_id": did,
                    "predicted_status": STATUS_MAP.get(status, status),
                    "source_stage": (stages[0] if stages else "document_impact_policy"),
                    "reason_codes": d.get("reason_codes") or [],
                    "substantive_evidence_count": d.get("substantive_evidence_count"),
                    "metadata": {
                        "exact_identifier_count": d.get("exact_identifier_count"),
                        "role_evidence_count": d.get("role_evidence_count"),
                        "source_stages": stages,
                        "target_status": d.get("target_status"),
                    },
                }
            )
        for d in workflow.get("documents") or []:
            did = d.get("document_id")
            if did and did not in decided:
                docs.append(
                    {
                        "case_id": case_id,
                        "document_id": did,
                        "predicted_status": "UNRELATED",
                        "source_stage": "document_impact_policy",
                        "reason_codes": ["no_decision_row"],
                    }
                )
    else:
        patch_docs = {c.get("document_id") for c in (workflow.get("patch_candidates") or [])}
        review_docs = {r.get("document_id") for r in (workflow.get("review_required") or [])}
        for d in workflow.get("documents") or []:
            did = d.get("document_id")
            if did in patch_docs:
                status = "IMPACTED"
                stage = "patch_candidate_doc"
            elif did in review_docs:
                status = "REVIEW_REQUIRED"
                stage = "review_doc"
            else:
                status = "UNRELATED"
                stage = "no_substantive_node_evidence"
            docs.append(
                {
                    "case_id": case_id,
                    "document_id": did,
                    "predicted_status": STATUS_MAP.get(status, status),
                    "source_stage": stage,
                }
            )
        if "MDTM" in patch_docs and not any(x.get("document_id") == "MDTM" for x in docs):
            docs.append(
                {
                    "case_id": case_id,
                    "document_id": "MDTM",
                    "predicted_status": "IMPACTED",
                    "source_stage": "mdtm_change",
                }
            )
        elif "MDTM" in review_docs and not any(x.get("document_id") == "MDTM" for x in docs):
            docs.append(
                {
                    "case_id": case_id,
                    "document_id": "MDTM",
                    "predicted_status": "REVIEW_REQUIRED",
                    "source_stage": "mdtm_change",
                }
            )

    nodes = []
    for rank, c in enumerate(workflow.get("patch_candidates") or [], start=1):
        meta = c.get("metadata") or {}
        ext = _extended_node_metadata(c, meta)
        ext["identifier_values"] = meta.get("identifier_values") or list(
            (meta.get("source_identifiers") or {}).get("requirement_ids") or []
        ) + list((meta.get("source_identifiers") or {}).get("design_ids") or []) + list(
            (meta.get("source_identifiers") or {}).get("test_ids") or []
        )
        nodes.append(
            {
                "case_id": case_id,
                "document_id": c.get("document_id"),
                "node_id": c.get("node_id") or c.get("item_id") or c.get("candidate_id"),
                "predicted_status": "PATCH_CANDIDATE",
                "score": _node_score(c, default=1.0),
                "rank": meta.get("rank") or rank,
                "rank_tier": meta.get("rank_tier"),
                "reason_codes": c.get("reason_codes") or [],
                "source_stage": c.get("source_stage") or meta.get("source_stage") or "change_poc",
                "stable_node_id": meta.get("stable_node_id"),
                "stable_node_id_base": meta.get("stable_node_id_base"),
                "metadata": ext,
            }
        )
    for rank, c in enumerate(workflow.get("review_required") or [], start=1):
        meta = c.get("metadata") or {}
        ext = _extended_node_metadata(c, meta)
        ext["identifier_values"] = meta.get("identifier_values") or []
        ext["template_alignment"] = meta.get("template_alignment")
        nodes.append(
            {
                "case_id": case_id,
                "document_id": c.get("document_id"),
                "node_id": c.get("node_id") or c.get("item_id") or c.get("candidate_id"),
                "predicted_status": "REVIEW_REQUIRED",
                "score": _node_score(c, default=0.5),
                "rank": meta.get("rank") or rank,
                "rank_tier": meta.get("rank_tier"),
                "reason_codes": c.get("reason_codes") or [],
                "source_stage": c.get("source_stage") or meta.get("source_stage") or "change_poc",
                "stable_node_id": meta.get("stable_node_id"),
                "stable_node_id_base": meta.get("stable_node_id_base"),
                "metadata": ext,
            }
        )

    patches = [
        {
            "case_id": case_id,
            "document_id": c.get("document_id"),
            "node_id": c.get("node_id") or c.get("item_id"),
            "predicted_status": "PATCH_CANDIDATE",
            "human_review_required": bool(c.get("human_review_required")),
        }
        for c in (workflow.get("patch_candidates") or [])
    ]
    wr = workflow.get("writer_result") or {}
    writer = {
        "case_id": case_id,
        "should_write_attempted": bool(wr),
        "applied": int(wr.get("applied") or 0),
        "controlled_writer_invoked": bool(wr.get("controlled_writer_invoked")),
        "enable_write": bool(wr.get("enable_write")),
        "status": wr.get("status"),
    }
    alignments = list(workflow.get("node_alignments") or [])
    equiv_groups = list(workflow.get("structural_equivalence_groups") or [])
    if not alignments:
        alignments = list(meta.get("node_alignments") or [])
    if not equiv_groups:
        equiv_groups = list(meta.get("structural_equivalence_groups") or [])
    if not alignments:
        for c in workflow.get("review_required") or []:
            cmeta = c.get("metadata") or {}
            for a in cmeta.get("node_alignments") or []:
                alignments.append(a)
            for g in cmeta.get("structural_equivalence_groups") or []:
                equiv_groups.append(g)
    seen_a = set()
    uniq_a = []
    for a in alignments:
        key = (a.get("template_node_id"), a.get("document_node_id"))
        if key in seen_a:
            continue
        seen_a.add(key)
        uniq_a.append(a)

    return {
        "case_id": case_id,
        "documents": docs,
        "nodes": nodes,
        "patches": patches,
        "writer": writer,
        "workflow_state": workflow.get("state"),
        "node_alignments": uniq_a,
        "structural_equivalence_groups": equiv_groups,
        "metadata": {
            "node_alignments": uniq_a,
            "structural_equivalence_groups": equiv_groups,
        },
    }
