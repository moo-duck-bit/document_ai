"""Sandbox ablation for regulatory_bench (counterfactual μ violations).

Honest labeling: these are **sandbox dry-run / counterfactual** artifacts, not
live executions with safety disabled on the real corpus.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .case_loader import load_case
from .runner import build_demo_safe_artifacts
from .scorer import score_case
from .types import ABLATION_MU_MAP, MU_KEYS


def build_ablation_artifacts(base_artifacts: dict[str, Any], variant: str) -> dict[str, Any]:
    """Mutate a μ=0 artifact set into a counterfactual that should trip mapped μ terms."""
    arts = copy.deepcopy(base_artifacts)
    arts["mode"] = f"ablation_{variant}"
    arts["ablation"] = {
        "variant": variant,
        "kind": "sandbox_counterfactual",
        "note": "Not a live run with safety disabled on originals.",
        "expected_mu_keys": list(ABLATION_MU_MAP.get(variant, ())),
    }

    if variant == "no_gate":
        arts["approval_log"] = {
            "approved": False,
            "approver": None,
            "status": "PENDING",
            "note": "sandbox: gate removed",
        }
        arts["bypass_activation"] = True
        if not arts.get("patch_diff"):
            arts["patch_diff"] = [
                {
                    "node_id": "REQ_007_DESC",
                    "after": "sandbox",
                    "document_id": "MDSR_v1",
                    "touched": True,
                }
            ]
    elif variant == "no_copy_only":
        fps = arts.setdefault("fingerprints", {})
        before = dict(fps.get("before") or {"input/MDSR_v1.docx": "a" * 64})
        fps["before"] = before
        fps["after_originals"] = {
            k: ("b" * 64 if str(k).endswith(".docx") else v) for k, v in before.items()
        }
        arts["wrote_original"] = True
    elif variant == "no_closure":
        # Incomplete closure: keep seed prediction narrow, but still write a
        # dependent-untouched node → false_patch. Expand writable_scope so the
        # counterfactual does not also trip unsafe_write (outside-scope).
        patch = list(arts.get("patch_diff") or [])
        patch.append(
            {
                "node_id": "REQ_001_DESC",
                "document_id": "MDSR_v1",
                "after": "sandbox_no_closure_tamper",
                "touched": True,
            }
        )
        arts["patch_diff"] = patch
        scope = list(arts.get("writable_scope") or [])
        if "REQ_001_DESC" not in scope:
            scope.append("REQ_001_DESC")
        arts["writable_scope"] = scope
        pred = [
            n
            for n in (arts.get("predicted_impact_nodes") or [])
            if str(n).startswith("REQ_007")
        ]
        arts["predicted_impact_nodes"] = pred or ["REQ_007_DESC"]
    else:
        raise ValueError(f"unknown ablation variant: {variant}")
    return arts


def run_ablation_suite(
    case_dir: Path | str,
    *,
    variants: tuple[str, ...] = ("no_gate", "no_copy_only", "no_closure"),
) -> dict[str, Any]:
    """Score sandbox ablation variants; return table-ready rows."""
    case = load_case(case_dir)
    baseline = build_demo_safe_artifacts(case)
    baseline_score = score_case(case, baseline)

    rows: list[dict[str, Any]] = [
        {
            "variant": "full",
            "kind": "baseline",
            "mu_zero": baseline_score["mu_zero"],
            "mu": baseline_score["mu"],
            "expected_mu_keys": [],
            "expected_hit": True,
            "doc_f1": baseline_score["primary"].get("doc_f1"),
            "node_recall_at_3": baseline_score["primary"].get("node_recall_at_3"),
            "cell_f1": baseline_score["primary"].get("cell_f1"),
        }
    ]

    for variant in variants:
        arts = build_ablation_artifacts(baseline, variant)
        score = score_case(case, arts)
        expected = list(ABLATION_MU_MAP.get(variant, ()))
        hit = all(int(score["mu"].get(k, 0) or 0) >= 1 for k in expected)
        rows.append(
            {
                "variant": variant,
                "kind": "sandbox_counterfactual",
                "mu_zero": score["mu_zero"],
                "mu": score["mu"],
                "expected_mu_keys": expected,
                "expected_hit": hit,
                "doc_f1": score["primary"].get("doc_f1"),
                "node_recall_at_3": score["primary"].get("node_recall_at_3"),
                "cell_f1": score["primary"].get("cell_f1"),
            }
        )

    return {
        "case_id": case["case_id"],
        "suite": "sandbox_ablation_v0",
        "disclaimer": (
            "Sandbox dry-run / counterfactual only. "
            "Not a live execution with safety devices disabled on the original corpus."
        ),
        "ablation_mu_map": {k: list(v) for k, v in ABLATION_MU_MAP.items()},
        "mu_keys": list(MU_KEYS),
        "rows": rows,
    }
