# -*- coding: utf-8 -*-
"""Identity / pack routing evaluation metrics (no gold mutation)."""

from __future__ import annotations

from typing import Any


def _acc(pairs: list[tuple[Any, Any]]) -> float:
    if not pairs:
        return 0.0
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def compute_identity_metrics(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    rows: predicted identity vs expected (from domain / tags / registry), not holdout case hardcodes.
    Each row keys:
      pred_document_type, gold_document_type,
      pred_document_role, gold_document_role,
      pred_canonical_document_id, gold_canonical_document_id,
      pred_short_id, gold_short_id,
      pred_template_id, gold_template_id,
      filename_only_auto (bool),
      source_equals_canonical (bool)
    """
    type_pairs = [(r.get("pred_document_type"), r.get("gold_document_type")) for r in rows if r.get("gold_document_type")]
    role_pairs = [(r.get("pred_document_role"), r.get("gold_document_role")) for r in rows if r.get("gold_document_role")]
    canon_pairs = [
        (r.get("pred_canonical_document_id"), r.get("gold_canonical_document_id"))
        for r in rows
        if r.get("gold_canonical_document_id")
    ]
    short_pairs = [(r.get("pred_short_id"), r.get("gold_short_id")) for r in rows if r.get("gold_short_id")]
    tmpl_pairs = [(r.get("pred_template_id"), r.get("gold_template_id")) for r in rows if r.get("gold_template_id")]
    filename_indep = [
        not bool(r.get("filename_only_auto")) for r in rows if r.get("decision_status") == "AUTO_SELECTED"
    ]
    return {
        "document_type_accuracy": _acc(type_pairs),
        "document_role_accuracy": _acc(role_pairs),
        "canonical_document_id_accuracy": _acc(canon_pairs),
        "short_id_accuracy": _acc(short_pairs),
        "template_id_accuracy": _acc(tmpl_pairs),
        "uploaded_filename_independence_rate": (
            sum(filename_indep) / len(filename_indep) if filename_indep else 1.0
        ),
        "n_rows": len(rows),
    }


def compute_pack_routing_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    rows:
      gold_pack_id, pred_top1_pack, pred_pack_rank (list),
      auto_selected (bool), auto_correct (bool|None), routing_status
    """
    top1 = [(r.get("pred_top1_pack"), r.get("gold_pack_id")) for r in rows if r.get("gold_pack_id")]
    recall3_hits = 0
    recall3_n = 0
    for r in rows:
        gold = r.get("gold_pack_id")
        if not gold:
            continue
        recall3_n += 1
        ranked = list(r.get("pred_pack_rank") or [])
        if gold in ranked[:3] or r.get("pred_top1_pack") == gold:
            recall3_hits += 1
    autos = [r for r in rows if r.get("auto_selected")]
    auto_correct = [r for r in autos if r.get("auto_correct") is True]
    wrong_auto = [r for r in autos if r.get("auto_correct") is False]
    reviews = [r for r in rows if r.get("routing_status") == "REVIEW_REQUIRED"]
    return {
        "domain_pack_top1_accuracy": _acc(top1),
        "domain_pack_recall_at_3": (recall3_hits / recall3_n) if recall3_n else 0.0,
        "auto_selection_precision": (len(auto_correct) / len(autos)) if autos else 1.0,
        "auto_selection_coverage": (len(autos) / len(rows)) if rows else 0.0,
        "wrong_auto_route_rate": (len(wrong_auto) / len(rows)) if rows else 0.0,
        "review_routing_rate": (len(reviews) / len(rows)) if rows else 0.0,
        "n_rows": len(rows),
        "n_auto": len(autos),
        "n_wrong_auto": len(wrong_auto),
    }


def compute_alignment_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fixture_match = [
        bool(r.get("fixture_canonical_match")) for r in rows if "fixture_canonical_match" in r
    ]
    registry = [bool(r.get("registry_aligned")) for r in rows if "registry_aligned" in r]
    dup = [bool(r.get("duplicate_detected_ok")) for r in rows if "duplicate_detected_ok" in r]
    return {
        "fixture_to_canonical_id_match_rate": (
            sum(fixture_match) / len(fixture_match) if fixture_match else 0.0
        ),
        "registry_alignment_accuracy": (sum(registry) / len(registry) if registry else 0.0),
        "duplicate_detection_accuracy": (sum(dup) / len(dup) if dup else 1.0),
        "n_rows": len(rows),
    }


def expected_identity_from_domain(domain: str) -> dict[str, str]:
    if domain == "ec_sw":
        return {
            "gold_document_type": "MDTM",
            "gold_document_role": "traceability",
            "gold_short_id": "MDTM",
            "gold_canonical_document_id": "EC_SW_MDTM",
            "gold_template_id": "ec_sw_mdtm",
            "gold_pack_id": "ec_sw_v1",
        }
    if domain == "general_report":
        return {
            "gold_document_type": "GENERAL_REPORT",
            "gold_document_role": "general_report",
            "gold_short_id": "REPORT",
            "gold_canonical_document_id": "GENERIC_GENERAL_REPORT",
            "gold_template_id": "general_report_v1",
            "gold_pack_id": "generic_document_v1",
        }
    if domain == "business_proposal":
        return {
            "gold_document_type": "BUSINESS_PROPOSAL",
            "gold_document_role": "business_proposal",
            "gold_short_id": "PROPOSAL",
            "gold_canonical_document_id": "GENERIC_BUSINESS_PROPOSAL",
            "gold_template_id": "business_proposal_v1",
            "gold_pack_id": "generic_document_v1",
        }
    return {}
