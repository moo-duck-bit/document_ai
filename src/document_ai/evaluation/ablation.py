# -*- coding: utf-8 -*-
"""Ablation runner for Document-TNR / dual-mode agent (RQ3).

Variants:
  - baseline: gate + closure + copy_only
  - no_gate: approve bypassed (write without approval)
  - no_closure: selective set without C1 expansion
  - no_copy_only: pretend write hits original path
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from document_ai.document_set.dependency_graph import (
    DependencyGraph,
    build_graph_from_req_design_links,
    closure,
    salvage_ratio,
    selective_sets,
)
from document_ai.safety.document_tnr import SeverityBundle, evaluate_r3_prime, not_worse

Variant = Literal["baseline", "no_gate", "no_closure", "no_copy_only"]


@dataclass
class AblationCase:
    case_id: str
    requirement_ids: list[str]
    design_items: list[dict[str, Any]]
    undo_seed: list[str]
    # Simulated post-write severity if gates fail
    inject_false_patch: bool = False


def _graph_for(case: AblationCase) -> DependencyGraph:
    return build_graph_from_req_design_links(
        requirement_ids=case.requirement_ids,
        design_items=case.design_items,
    )


def run_variant(case: AblationCase, variant: Variant) -> dict[str, Any]:
    graph = _graph_for(case)
    approved = variant != "no_gate"
    apply_closure = variant != "no_closure"
    copy_only = variant != "no_copy_only"

    if apply_closure:
        sel = selective_sets(graph, case.undo_seed)
        R = set(sel["undo_set_R"])
    else:
        R = set(case.undo_seed)
        sel = {
            "undo_set_R": sorted(R),
            "keep_set_K": sorted(set(graph.nodes) - R),
            "salvage_ratio": salvage_ratio(len(set(graph.nodes) - R), len(graph.nodes) or 1),
            "closure_applied": False,
        }

    mu_pre = SeverityBundle()
    mu_post = SeverityBundle()

    # Safety violations injected by ablations
    if not approved:
        mu_post.unapproved_write = 1
    if not copy_only:
        mu_post.original_broken = 1
    if not apply_closure:
        # missing dependents ⇒ semantic inconsistency / false patch risk
        full = closure(graph, case.undo_seed)
        if full - R:
            mu_post.false_patch = 1
    if case.inject_false_patch:
        mu_post.false_patch += 1

    tnr = evaluate_r3_prime(
        mu_pre=mu_pre,
        mu_post=mu_post,
        approved=approved,
        closure_ok=apply_closure,
        copy_only=copy_only,
    )

    # Under baseline, severity must not increase on commit path
    safe = bool(tnr["decision"] == "ABORT_TO_PRE" or not_worse(mu_post, mu_pre))
    if tnr["decision"] == "COMMIT_POST" and mu_post.total() > 0:
        safe = False

    return {
        "case_id": case.case_id,
        "variant": variant,
        "approved": approved,
        "copy_only": copy_only,
        "closure_applied": apply_closure,
        "selective": sel,
        "mu_pre": mu_pre.to_dict(),
        "mu_post": mu_post.to_dict(),
        "tnr": tnr,
        "safe": safe,
        "original_preserved": mu_post.original_broken == 0,
        "false_patch": mu_post.false_patch,
        "unapproved_write": mu_post.unapproved_write,
    }


def run_ablation_suite(cases: list[AblationCase]) -> dict[str, Any]:
    variants: list[Variant] = ["baseline", "no_gate", "no_closure", "no_copy_only"]
    rows: list[dict[str, Any]] = []
    for case in cases:
        for v in variants:
            rows.append(run_variant(case, v))

    by_variant: dict[str, list[dict[str, Any]]] = {v: [] for v in variants}
    for row in rows:
        by_variant[row["variant"]].append(row)

    summary = {}
    for v, items in by_variant.items():
        n = len(items) or 1
        summary[v] = {
            "n": len(items),
            "safe_rate": round(sum(1 for i in items if i["safe"]) / n, 4),
            "original_preservation_rate": round(
                sum(1 for i in items if i["original_preserved"]) / n, 4
            ),
            "false_patch_rate": round(sum(i["false_patch"] for i in items) / n, 4),
            "unapproved_write_rate": round(
                sum(i["unapproved_write"] for i in items) / n, 4
            ),
            "abort_rate": round(
                sum(1 for i in items if i["tnr"]["decision"] == "ABORT_TO_PRE") / n, 4
            ),
        }

    return {
        "summary": summary,
        "rows": rows,
        "claim": (
            "baseline keeps Document-TNR; "
            "removing gate/closure/copy-only increases severity or forces abort"
        ),
    }


def demo_cases_from_hospital(case_dir: Path | None = None) -> list[AblationCase]:
    """Build a small ablation case from hospital_reservation payloads if present."""
    import json

    root = Path(__file__).resolve().parents[3]
    case_dir = case_dir or (root / "data" / "cases" / "hospital_reservation")
    req_ids: list[str] = []
    design_items: list[dict[str, Any]] = []
    if (case_dir / "requirements.json").exists():
        payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
        req_ids = [str(r.get("req_id") or "") for r in payload.get("requirements", [])][:12]
    if (case_dir / "design_items.json").exists():
        payload = json.loads((case_dir / "design_items.json").read_text(encoding="utf-8"))
        raw = payload.get("items") or payload.get("design_items") or []
        design_items = [x for x in raw if isinstance(x, dict)][:12]
    if not req_ids:
        req_ids = ["Req. 1", "Req. 2", "Req. 11"]
    # Ensure at least one downstream edge from the undo seed so −closure is observable
    seed = req_ids[0]
    if not any(str(d.get("req_id") or "") == seed for d in design_items):
        design_items = list(design_items) + [
            {"design_id": f"D-{seed}", "req_id": seed},
        ]
    return [
        AblationCase(
            case_id=case_dir.name if case_dir.exists() else "synthetic",
            requirement_ids=req_ids,
            design_items=design_items,
            undo_seed=[seed],
        )
    ]
