# -*- coding: utf-8 -*-
"""Node gold label audit (does not auto-mutate gold; proposals only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.evaluation.document_set.node_evaluation import validate_eligibility_row

REPO = Path(__file__).resolve().parents[4]
DEFAULT_BENCH = REPO / "data" / "eval" / "document_set_benchmark"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def audit_node_labels(
    *,
    bench_dir: Path | None = None,
    prediction_by_case: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """
    Audit node eligibility vs gold rows.

    Prediction counts are recorded for diagnostics only and MUST NOT drive gold mutation.
    """
    base = Path(bench_dir) if bench_dir else DEFAULT_BENCH
    cases_meta = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    eligibility = {r["case_id"]: r for r in _read_jsonl(base / "labels" / "node_evaluation_eligibility.jsonl")}
    node_gold = _read_jsonl(base / "labels" / "node_impacts.jsonl")
    gold_by_case: dict[str, list[dict[str, Any]]] = {}
    for r in node_gold:
        gold_by_case.setdefault(r["case_id"], []).append(r)

    pred = prediction_by_case or {}
    audit_rows: list[dict[str, Any]] = []
    proposed: list[dict[str, Any]] = []
    issues_count: dict[str, int] = {}

    for rel in cases_meta.get("cases") or []:
        cpath = base / rel
        case = json.loads(cpath.read_text(encoding="utf-8"))
        cid = case["case_id"]
        elig = eligibility.get(cid) or {
            "case_id": cid,
            "node_evaluation_mode": "UNLABELED",
        }
        mode = elig.get("node_evaluation_mode", "UNLABELED")
        golds = gold_by_case.get(cid) or []
        gold_ids = [g.get("node_id") for g in golds if g.get("node_id")]
        acc = list(elig.get("acceptable_node_ids") or [])
        for g in golds:
            acc.extend(g.get("acceptable_node_ids") or [])
        groups = list(elig.get("acceptable_node_groups") or [])

        label_issue = "LABEL_COMPLETE"
        v_issues = validate_eligibility_row(
            {
                **elig,
                "primary_node_id": elig.get("primary_node_id") or (gold_ids[0] if gold_ids else None),
                "gold_node_ids": gold_ids,
                "acceptable_node_ids": acc,
                "acceptable_node_groups": groups,
            }
        )
        if mode == "REQUIRED" and not gold_ids:
            label_issue = "NODE_GOLD_MISSING"
        elif mode == "NOT_APPLICABLE" and gold_ids:
            label_issue = "NODE_GOLD_NOT_REQUIRED"
        elif mode == "UNLABELED":
            label_issue = "NODE_GOLD_MISSING"
        elif mode == "AMBIGUOUS" and not (groups or acc or gold_ids):
            label_issue = "ACCEPTABLE_ALTERNATIVE_INVALID"
        elif v_issues:
            label_issue = "NODE_GOLD_INVALID"

        issues_count[label_issue] = issues_count.get(label_issue, 0) + 1
        pred_n = len(pred.get(cid) or [])
        row = {
            "case_id": cid,
            "domain": case.get("domain"),
            "document_status": (case.get("expected_status") or ""),
            "node_evaluation_mode": mode,
            "gold_node_count": len(gold_ids),
            "acceptable_node_count": len(set(acc)),
            "prediction_candidate_count": pred_n,
            "label_issue": label_issue,
            "recommended_action": (
                "none"
                if label_issue == "LABEL_COMPLETE"
                else "review_proposed_label_changes"
            ),
            "validation_issues": v_issues,
            # diagnostic only — not a gold mutation signal
            "prediction_seen_but_ignored_for_gold": pred_n > 0 and not gold_ids,
        }
        audit_rows.append(row)
        if label_issue != "LABEL_COMPLETE":
            proposed.append(
                {
                    "case_id": cid,
                    "current_mode": mode,
                    "issue": label_issue,
                    "rationale": elig.get("label_rationale") or case.get("notes") or "",
                    "proposed_action": "manual_review",
                    "auto_applied": False,
                }
            )

    summary = {
        "total_cases": len(audit_rows),
        "by_mode": {},
        "by_issue": issues_count,
        "unlabeled": sum(1 for r in audit_rows if r["node_evaluation_mode"] == "UNLABELED"),
        "automatic_gold_mutation": 0,
    }
    for r in audit_rows:
        m = r["node_evaluation_mode"]
        summary["by_mode"][m] = summary["by_mode"].get(m, 0) + 1

    return {
        "summary": summary,
        "rows": audit_rows,
        "proposed_label_changes": proposed,
    }


def write_audit_artifacts(
    payload: dict[str, Any],
    *,
    out_dir: Path,
    also_write_proposed_to_bench: bool = True,
    bench_dir: Path | None = None,
) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = {}
    audit_path = out_dir / "node_label_audit.json"
    audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["node_label_audit.json"] = str(audit_path).replace("\\", "/")

    stamped = out_dir.parent / f"node_label_audit_{stamp}.json"
    # keep under document_set_benchmark results root when out_dir is a run dir
    try:
        stamped = out_dir.parent / f"node_label_audit_{stamp}.json"
        stamped.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths["node_label_audit_stamped"] = str(stamped).replace("\\", "/")
    except Exception:
        pass

    proposed_path = out_dir / "proposed_label_changes.json"
    proposed_path.write_text(
        json.dumps(
            {
                "automatic_gold_mutation": False,
                "note": "Proposals only; do not apply from prediction outcomes.",
                "changes": payload.get("proposed_label_changes") or [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["proposed_label_changes.json"] = str(proposed_path).replace("\\", "/")

    if also_write_proposed_to_bench:
        bdir = Path(bench_dir) if bench_dir else DEFAULT_BENCH
        (bdir / "proposed_label_changes.json").write_text(
            proposed_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    return paths
