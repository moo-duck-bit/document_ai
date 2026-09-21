# -*- coding: utf-8 -*-
"""Benchmark dataset / result validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_benchmark_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    cases = bundle.get("cases") or []
    ids = [c.case_id for c in cases]
    if len(ids) != len(set(ids)):
        issues.append("duplicate_case_id")
    gold = bundle.get("gold") or {}
    doc_cases = {r["case_id"] for r in gold.get("document_impacts") or []}
    for cid in ids:
        if cid not in doc_cases:
            issues.append(f"incomplete_document_gold:{cid}")
    for r in gold.get("node_impacts") or []:
        alts = r.get("acceptable_node_ids") or []
        for a in alts:
            # same-document alternatives only (soft check via notes)
            if not a:
                issues.append(f"empty_acceptable:{r.get('case_id')}")

    elig = {r["case_id"]: r for r in gold.get("node_evaluation_eligibility") or []}
    nodes_by = {}
    for r in gold.get("node_impacts") or []:
        nodes_by.setdefault(r["case_id"], []).append(r)
    if elig:
        missing = set(ids) - set(elig)
        if missing:
            issues.append(f"missing_eligibility:{sorted(missing)[:3]}")
        for cid in ids:
            row = elig.get(cid) or {}
            mode = row.get("node_evaluation_mode")
            nids = [n.get("node_id") for n in nodes_by.get(cid) or [] if n.get("node_id")]
            if mode == "UNLABELED":
                warnings.append(f"unlabeled_node_mode:{cid}")
            if mode == "REQUIRED" and not (row.get("primary_node_id") or nids):
                issues.append(f"REQUIRED_without_gold:{cid}")
            if mode == "AMBIGUOUS" and not (
                row.get("acceptable_node_groups") or row.get("acceptable_node_ids") or nids
            ):
                issues.append(f"AMBIGUOUS_without_group:{cid}")
            if mode == "NOT_APPLICABLE" and nids:
                warnings.append(f"na_with_node_gold:{cid}")

    status = "VALID" if not issues else "INVALID"
    if warnings and status == "VALID":
        status = "VALID_WITH_WARNINGS"
    return {"status": status, "issues": issues, "warnings": warnings}


def assert_result_root_inside(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_r = root.resolve()
    if not str(resolved).startswith(str(root_r)):
        raise ValueError("ARTIFACT_OUTSIDE_RESULT_ROOT")
