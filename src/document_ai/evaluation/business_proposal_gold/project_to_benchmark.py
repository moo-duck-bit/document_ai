# -*- coding: utf-8 -*-
"""Project sealed Business Proposal gold rows into the benchmark label JSONLs.

Merges BP rows into ``node_evaluation_eligibility.jsonl`` / ``node_impacts.jsonl``
for both ``development/labels`` and ``holdout/sealed_labels`` while preserving
every non-BP row untouched, then re-seals the holdout label directory via
``write_seal_manifest``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.evaluation.document_set_v2.holdout_protocol import write_seal_manifest

REPO = Path(__file__).resolve().parents[4]
DEFAULT_BENCH = REPO / "data" / "eval" / "document_set_benchmark_v2"

ELIG_FILE = "node_evaluation_eligibility.jsonl"
NODE_FILE = "node_impacts.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    path.write_text((body + "\n") if rows else "", encoding="utf-8")


def _split_of(case_id: str) -> str:
    if case_id.startswith("v2_hol_"):
        return "holdout"
    return "development"


def _group_for_row(row: dict[str, Any]) -> list[str]:
    groups = row.get("acceptable_groups") or []
    if groups:
        return list(groups[0])
    return list(row.get("acceptable_references_ids") or [])


def gold_row_to_projection(row: dict[str, Any], *, now: str) -> dict[str, Any]:
    """Build (eligibility_row, node_impacts_row|None) for one sealed gold row.

    Primary-selection priority: Stable > Template > Physical. The template
    node id is used as the projected ``primary_node_id`` for cross-run
    identity stability (matches how BP template sections were already the
    Top-1 target in Cycle 5); the physical node is carried in
    ``acceptable_node_ids``/groups so either resolves the evaluation.
    """
    ref = row.get("primary_reference") or {}
    mode = row["node_evaluation_mode"]
    case_id = row["case_id"]
    document_id = row["document_id"]

    stable_id = ref.get("stable_node_id")
    template_id = ref.get("template_node_id")
    physical_id = ref.get("document_node_id")
    primary_id = stable_id or template_id or physical_id

    acceptable_ids: set[str] = set()
    for a in row.get("acceptable_references") or []:
        for key in ("stable_node_id", "template_node_id", "document_node_id"):
            v = a.get(key)
            if v:
                acceptable_ids.add(v)
    groups = [list(g) for g in (row.get("acceptable_groups") or [])]
    for g in groups:
        acceptable_ids.update(g)
    if physical_id:
        acceptable_ids.add(physical_id)
    if template_id:
        acceptable_ids.add(template_id)
    acceptable_ids.discard(primary_id)

    elig_row = {
        "case_id": case_id,
        "domain": "business_proposal",
        "document_id": document_id,
        "node_evaluation_mode": mode,
        "primary_node_id": primary_id,
        "acceptable_node_ids": sorted(acceptable_ids),
        "acceptable_node_groups": groups,
        "label_rationale": row.get("label_rationale") or "",
        "labeled_by": "cycle6_business_proposal_gold",
        "labeled_at": now,
        "confidence": row.get("label_confidence", 0.85),
    }

    node_row = None
    if mode in {"REQUIRED", "AMBIGUOUS"}:
        node_id = physical_id or primary_id
        node_acceptable = sorted(acceptable_ids | ({template_id} if template_id else set()))
        node_row = {
            "case_id": case_id,
            "document_id": document_id,
            "node_id": node_id,
            "gold_status": "REVIEW_REQUIRED",
            "node_evaluation_mode": mode,
            "primary_node_id": node_id,
            "acceptable_node_ids": [a for a in node_acceptable if a != node_id],
            "acceptable_node_groups": groups,
            "label_rationale": row.get("label_rationale") or "",
            "labeled_by": "cycle6_business_proposal_gold",
            "labeled_at": now,
            "confidence": row.get("label_confidence", 0.85),
        }
    return {"eligibility": elig_row, "node": node_row}


def project_gold_into_benchmark(
    gold_rows: list[dict[str, Any]],
    *,
    benchmark_root: Path | None = None,
) -> dict[str, Any]:
    base = Path(benchmark_root) if benchmark_root else DEFAULT_BENCH
    now = datetime.now(timezone.utc).isoformat()

    by_split: dict[str, list[dict[str, Any]]] = {"development": [], "holdout": []}
    for row in gold_rows:
        by_split[_split_of(row["case_id"])].append(row)

    written: dict[str, str] = {}
    for split, label_dir in (
        ("development", base / "development" / "labels"),
        ("holdout", base / "holdout" / "sealed_labels"),
    ):
        rows = by_split[split]
        bp_case_ids = {r["case_id"] for r in rows}

        elig_path = label_dir / ELIG_FILE
        node_path = label_dir / NODE_FILE
        existing_elig = _read_jsonl(elig_path)
        existing_node = _read_jsonl(node_path)

        kept_elig = [r for r in existing_elig if r.get("case_id") not in bp_case_ids]
        kept_node = [r for r in existing_node if r.get("case_id") not in bp_case_ids]

        new_elig = []
        new_node = []
        for row in rows:
            proj = gold_row_to_projection(row, now=now)
            new_elig.append(proj["eligibility"])
            if proj["node"] is not None:
                new_node.append(proj["node"])

        final_elig = sorted(kept_elig + new_elig, key=lambda r: r["case_id"])
        final_node = sorted(kept_node + new_node, key=lambda r: (r["case_id"], r["node_id"]))
        _write_jsonl(elig_path, final_elig)
        _write_jsonl(node_path, final_node)
        written[f"{split}_eligibility"] = str(elig_path).replace("\\", "/")
        written[f"{split}_node_impacts"] = str(node_path).replace("\\", "/")

    seal = write_seal_manifest(
        holdout_dir=base / "holdout",
        sealed_labels_dir=base / "holdout" / "sealed_labels",
        out_path=base / "holdout" / "holdout_label_manifest.json",
    )
    written["holdout_reseal_status"] = seal.get("status")
    written["holdout_reseal_aggregate_hash"] = seal.get("aggregate_hash")
    return written
