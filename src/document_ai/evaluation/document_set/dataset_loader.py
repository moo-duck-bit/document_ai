# -*- coding: utf-8 -*-
"""Load document-set benchmark manifest and golden labels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.evaluation.document_set.schema import BenchmarkCase

REPO = Path(__file__).resolve().parents[4]
DEFAULT_MANIFEST = REPO / "data" / "eval" / "document_set_benchmark" / "manifest.json"


class DatasetValidationError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_benchmark_manifest(manifest_path: Path | None = None) -> dict[str, Any]:
    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    cases: list[BenchmarkCase] = []
    case_ids: set[str] = set()
    for rel in raw.get("cases") or []:
        cpath = base / rel
        c = json.loads(cpath.read_text(encoding="utf-8"))
        cid = c["case_id"]
        if cid in case_ids:
            raise DatasetValidationError(f"duplicate case_id: {cid}")
        case_ids.add(cid)
        if c.get("domain") not in {"ec_sw", "general_report"}:
            raise DatasetValidationError(f"invalid domain: {c.get('domain')}")
        for doc in c.get("input_documents") or []:
            p = base / doc["path"]
            if not p.is_file():
                raise DatasetValidationError(f"missing document: {p}")
        cases.append(BenchmarkCase(**{k: c[k] for k in BenchmarkCase.__dataclass_fields__ if k in c}))

    labels_dir = base / "labels"
    gold = {
        "document_impacts": _read_jsonl(labels_dir / "document_impacts.jsonl"),
        "node_impacts": _read_jsonl(labels_dir / "node_impacts.jsonl"),
        "patch_expectations": _read_jsonl(labels_dir / "patch_expectations.jsonl"),
        "writer_expectations": _read_jsonl(labels_dir / "writer_expectations.jsonl"),
        "node_evaluation_eligibility": _read_jsonl(
            labels_dir / "node_evaluation_eligibility.jsonl"
        ),
    }
    for row in gold["document_impacts"]:
        if row["case_id"] not in case_ids:
            raise DatasetValidationError(f"orphan document gold: {row['case_id']}")
    for row in gold["node_impacts"]:
        if row["case_id"] not in case_ids:
            raise DatasetValidationError(f"orphan node gold: {row['case_id']}")
    elig_ids = {r["case_id"] for r in gold["node_evaluation_eligibility"]}
    if gold["node_evaluation_eligibility"]:
        missing_elig = case_ids - elig_ids
        if missing_elig:
            raise DatasetValidationError(f"missing node eligibility: {sorted(missing_elig)[:5]}")

    return {
        "manifest_path": str(path).replace("\\", "/"),
        "base_dir": str(base).replace("\\", "/"),
        "cases": cases,
        "case_dicts": [c.to_dict() for c in cases],
        "gold": gold,
        "meta": raw.get("meta") or {},
    }
