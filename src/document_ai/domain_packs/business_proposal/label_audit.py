# -*- coding: utf-8 -*-
"""Business Proposal node label audit (proposals only; no gold mutation)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.domain_packs.business_proposal.concepts import (
    BUDGET,
    EXPECTED_EFFECT,
    ORGANIZATION,
    RISK_MANAGEMENT,
    SCHEDULE,
    TEMPLATE_ID,
    template_node_for_concepts,
)
from document_ai.domain_packs.business_proposal.query_intent import parse_business_proposal_query_intent
from document_ai.evaluation.document_set.node_evaluation import validate_eligibility_row

REPO = Path(__file__).resolve().parents[4]
DEFAULT_BENCH = REPO / "data" / "eval" / "document_set_benchmark_v2"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _collect_bp_cases(benchmark_root: Path) -> list[dict[str, Any]]:
    manifest = json.loads((benchmark_root / "manifest.json").read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for split, key in (("development", "development_cases"), ("holdout", "holdout_cases")):
        for rel in manifest.get(key) or []:
            cpath = benchmark_root / rel
            if not cpath.is_file():
                continue
            case = json.loads(cpath.read_text(encoding="utf-8"))
            if case.get("domain") != "business_proposal":
                continue
            case = dict(case)
            case["split"] = case.get("split") or split
            cases.append(case)
    return cases


def _labels_for_split(benchmark_root: Path, split: str) -> tuple[dict[str, dict], dict[str, list]]:
    if split == "holdout":
        label_dir = benchmark_root / "holdout" / "sealed_labels"
    else:
        label_dir = benchmark_root / "development" / "labels"
    eligibility = {r["case_id"]: r for r in _read_jsonl(label_dir / "node_evaluation_eligibility.jsonl")}
    node_gold: dict[str, list] = {}
    for r in _read_jsonl(label_dir / "node_impacts.jsonl"):
        node_gold.setdefault(r["case_id"], []).append(r)
    return eligibility, node_gold


def _propose_primary_node(case: dict[str, Any]) -> dict[str, Any] | None:
    cr = str(case.get("change_request") or "")
    tags = [str(t).lower() for t in (case.get("tags") or [])]
    intent = parse_business_proposal_query_intent(cr)
    if case.get("expected_status") == "UNRELATED" or "no_impact" in "_".join(tags):
        return None
    if intent.review_intent and not intent.primary_concept and "no_impact" in cr.lower():
        return None

    concepts = set(intent.canonical_concepts)
    if "schedule" in tags or "sched" in tags:
        concepts.add(SCHEDULE)
    if "budget" in tags:
        concepts.add(BUDGET)
    if "risk" in tags:
        concepts.add(RISK_MANAGEMENT)
    if "org" in tags or "organization" in tags:
        concepts.add(ORGANIZATION)
    if "effect" in tags or "outcome" in tags:
        concepts.add(EXPECTED_EFFECT)

    primary_tid = template_node_for_concepts(concepts) or intent.preferred_template_node_id
    if not primary_tid:
        return None
    return {
        "proposed_mode": "REQUIRED",
        "proposed_primary_node_id": primary_tid,
        "proposed_acceptable_node_ids": [primary_tid],
        "intent_primary_concept": intent.primary_concept,
        "intent_label": intent.intent_label,
        "derivation": "change_request_and_tags",
        "template_id": TEMPLATE_ID,
    }


def run_business_proposal_label_audit(
    benchmark_root: Path | None = None,
) -> dict[str, Any]:
    base = Path(benchmark_root) if benchmark_root else DEFAULT_BENCH
    audit_rows: list[dict[str, Any]] = []
    proposed: list[dict[str, Any]] = []

    for split in ("development", "holdout"):
        eligibility_by_case, gold_by_case = _labels_for_split(base, split)
        for case in _collect_bp_cases(base):
            if case.get("split") != split:
                continue
            cid = case["case_id"]

            elig = eligibility_by_case.get(cid) or {}
            mode = elig.get("node_evaluation_mode", "UNLABELED")
            golds = gold_by_case.get(cid) or []
            gold_ids = [g.get("node_id") for g in golds if g.get("node_id")]

            label_issue = "LABEL_COMPLETE"
            if mode == "OPTIONAL" and not gold_ids:
                label_issue = "OPTIONAL_NO_GOLD_REQUIRED_METRIC_GAP"
            elif mode == "NOT_APPLICABLE" and gold_ids:
                label_issue = "NODE_GOLD_NOT_REQUIRED"
            elif mode == "REQUIRED" and not gold_ids:
                label_issue = "NODE_GOLD_MISSING"

            v_issues = validate_eligibility_row(
                {
                    **elig,
                    "primary_node_id": elig.get("primary_node_id") or (gold_ids[0] if gold_ids else None),
                    "gold_node_ids": gold_ids,
                    "acceptable_node_ids": list(elig.get("acceptable_node_ids") or []),
                    "acceptable_node_groups": list(elig.get("acceptable_node_groups") or []),
                }
            )
            if v_issues and label_issue == "LABEL_COMPLETE":
                label_issue = "NODE_GOLD_INVALID"

            proposal = _propose_primary_node(case)
            row = {
                "case_id": cid,
                "split": split,
                "domain": "business_proposal",
                "change_request": case.get("change_request"),
                "tags": case.get("tags") or [],
                "node_evaluation_mode": mode,
                "gold_node_count": len(gold_ids),
                "label_issue": label_issue,
                "validation_issues": v_issues,
                "recommended_action": "none" if label_issue == "LABEL_COMPLETE" else "review_proposed_label_changes",
            }
            audit_rows.append(row)

            if proposal and mode == "OPTIONAL" and not gold_ids:
                proposed.append(
                    {
                        "case_id": cid,
                        "split": split,
                        "current_mode": mode,
                        "issue": label_issue,
                        **proposal,
                        "rationale": (
                            f"CR/theme maps to template section {proposal['proposed_primary_node_id']} "
                            f"via {proposal['derivation']}"
                        ),
                        "proposed_action": "promote_to_required_with_template_primary",
                        "auto_applied": False,
                    }
                )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_root": str(base).replace("\\", "/"),
        "domain": "business_proposal",
        "n_cases": len(audit_rows),
        "n_proposed_changes": len(proposed),
        "audit_rows": audit_rows,
        "proposed_label_changes": proposed,
        "notes": "Proposals only; gold files are not mutated by this audit.",
    }


def write_business_proposal_label_audit(
    out_dir: Path,
    *,
    benchmark_root: Path | None = None,
) -> dict[str, str]:
    payload = run_business_proposal_label_audit(benchmark_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in ("business_proposal_node_label_audit.json", "business_proposal_proposed_label_changes.json"):
        key = name.replace("business_proposal_", "").replace(".json", "")
        if name.endswith("proposed_label_changes.json"):
            body = {
                "generated_at": payload["generated_at"],
                "n_proposed": payload["n_proposed_changes"],
                "changes": payload["proposed_label_changes"],
            }
        else:
            body = payload
        path = out_dir / name
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths[name] = str(path).replace("\\", "/")
    return paths
