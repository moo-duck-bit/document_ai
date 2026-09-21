# -*- coding: utf-8 -*-
"""Load Benchmark v2 manifests and labels (holdout sealed until unseal)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.evaluation.document_set_v2.schema import ALLOWED_DOMAINS, ALLOWED_SPLITS, BenchmarkV2Case

REPO = Path(__file__).resolve().parents[4]
DEFAULT_MANIFEST = REPO / "data" / "eval" / "document_set_benchmark_v2" / "manifest.json"
V1_MANIFEST = REPO / "data" / "eval" / "document_set_benchmark" / "manifest.json"


class BenchmarkV2ValidationError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_cases_from_manifest_section(
    *,
    base: Path,
    case_rels: list[str],
    default_split: str,
) -> list[BenchmarkV2Case]:
    cases: list[BenchmarkV2Case] = []
    seen: set[str] = set()
    for rel in case_rels:
        cpath = base / rel
        if not cpath.is_file():
            # regression may point at v1 paths with absolute-ish relative from v1 root
            raise BenchmarkV2ValidationError(f"missing_case:{rel}")
        raw = json.loads(cpath.read_text(encoding="utf-8"))
        cid = raw["case_id"]
        if cid in seen:
            raise BenchmarkV2ValidationError(f"duplicate_case_id:{cid}")
        seen.add(cid)
        domain = raw.get("domain")
        if domain not in ALLOWED_DOMAINS and default_split != "regression":
            raise BenchmarkV2ValidationError(f"invalid_domain:{domain}")
        if default_split == "regression" and domain not in {"ec_sw", "general_report"}:
            raise BenchmarkV2ValidationError(f"invalid_regression_domain:{domain}")
        split = raw.get("split") or default_split
        if split not in ALLOWED_SPLITS:
            raise BenchmarkV2ValidationError(f"invalid_split:{split}")
        for doc in raw.get("input_documents") or []:
            p = base / doc["path"]
            if not p.is_file():
                raise BenchmarkV2ValidationError(f"missing_document:{p}")
        fields = {k: raw[k] for k in BenchmarkV2Case.__dataclass_fields__ if k in raw}
        fields.setdefault("split", split)
        cases.append(BenchmarkV2Case(**fields))
    return cases


def load_label_bundle(labels_dir: Path) -> dict[str, Any]:
    return {
        "document_impacts": _read_jsonl(labels_dir / "document_impacts.jsonl"),
        "node_impacts": _read_jsonl(labels_dir / "node_impacts.jsonl"),
        "writer_expectations": _read_jsonl(labels_dir / "writer_expectations.jsonl"),
        "node_evaluation_eligibility": _read_jsonl(labels_dir / "node_evaluation_eligibility.jsonl"),
        "patch_expectations": _read_jsonl(labels_dir / "patch_expectations.jsonl"),
    }


def load_benchmark_v2_manifest(
    manifest_path: Path | None = None,
    *,
    load_holdout_labels: bool = False,
) -> dict[str, Any]:
    """
    Load v2 manifest. Holdout sealed labels are NOT loaded unless load_holdout_labels=True
    (evaluation unseal phase only).
    """
    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST
    path = path.resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent.resolve()
    meta = raw.get("meta") or {}

    # Regression: reference v1 cases without copying
    reg_ref = raw.get("regression_manifest") or str(V1_MANIFEST)
    reg_manifest = Path(reg_ref)
    if not reg_manifest.is_file():
        reg_manifest = V1_MANIFEST
    reg_raw = json.loads(reg_manifest.read_text(encoding="utf-8"))
    reg_base = reg_manifest.parent
    regression_cases = []
    seen_all: set[str] = set()
    for rel in reg_raw.get("cases") or []:
        cpath = reg_base / rel
        c = json.loads(cpath.read_text(encoding="utf-8"))
        cid = c["case_id"]
        if cid in seen_all:
            raise BenchmarkV2ValidationError(f"duplicate_case_id:{cid}")
        seen_all.add(cid)
        for doc in c.get("input_documents") or []:
            if not (reg_base / doc["path"]).is_file():
                raise BenchmarkV2ValidationError(f"missing_regression_doc:{doc['path']}")
        regression_cases.append(
            BenchmarkV2Case(
                case_id=cid,
                domain=c["domain"],
                document_set_id=c["document_set_id"],
                change_request=c["change_request"],
                split="regression",
                input_documents=[
                    {**d, "path": str((reg_base / d["path"]).resolve())} for d in c["input_documents"]
                ],
                enabled_documents=list(c.get("enabled_documents") or []),
                expected_status=c.get("expected_status") or "SUCCESS",
                tags=list(c.get("tags") or []) + ["regression_v1"],
                difficulty=c.get("difficulty") or "easy",
                notes=c.get("notes") or "",
                source_type="fixture",
            )
        )

    dev_cases = _load_cases_from_manifest_section(
        base=base,
        case_rels=list(raw.get("development_cases") or []),
        default_split="development",
    )
    for c in dev_cases:
        if c.case_id in seen_all:
            raise BenchmarkV2ValidationError(f"duplicate_across_splits:{c.case_id}")
        seen_all.add(c.case_id)

    holdout_cases = _load_cases_from_manifest_section(
        base=base,
        case_rels=list(raw.get("holdout_cases") or []),
        default_split="holdout",
    )
    for c in holdout_cases:
        if c.case_id in seen_all:
            raise BenchmarkV2ValidationError(f"duplicate_across_splits:{c.case_id}")
        seen_all.add(c.case_id)

    gold = {
        "regression": load_label_bundle(reg_base / "labels"),
        "development": load_label_bundle(base / "development" / "labels"),
        "holdout": {},
    }
    sealed_dir = base / "holdout" / "sealed_labels"
    if load_holdout_labels:
        gold["holdout"] = load_label_bundle(sealed_dir)

    metamorphic_pairs = _read_jsonl(base / "metamorphic_pairs.jsonl")

    return {
        "manifest_path": str(path).replace("\\", "/"),
        "base_dir": str(base).replace("\\", "/"),
        "regression_base_dir": str(reg_base).replace("\\", "/"),
        "meta": meta,
        "cases": {
            "regression": regression_cases,
            "development": dev_cases,
            "holdout": holdout_cases,
        },
        "gold": gold,
        "sealed_labels_dir": str(sealed_dir).replace("\\", "/"),
        "seal_manifest_path": str(base / "holdout" / "holdout_label_manifest.json").replace("\\", "/"),
        "metamorphic_pairs": metamorphic_pairs,
        "load_holdout_labels": load_holdout_labels,
    }


def validate_benchmark_v2(bundle: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    cases = bundle.get("cases") or {}
    ids = []
    for split, rows in cases.items():
        for c in rows:
            ids.append(c.case_id)
            if c.split != split and split != "regression":
                # regression cases forced to regression split
                if c.split not in ALLOWED_SPLITS:
                    issues.append(f"bad_split:{c.case_id}")
    if len(ids) != len(set(ids)):
        issues.append("duplicate_case_id")
    # sizes
    if len(cases.get("regression") or []) < 24:
        warnings.append("regression_lt_24")
    if len(cases.get("development") or []) < 20:
        issues.append("development_lt_20")
    if len(cases.get("holdout") or []) < 20:
        issues.append("holdout_lt_20")
    sealed = Path(bundle.get("sealed_labels_dir") or "")
    if not sealed.is_dir():
        issues.append("missing_sealed_labels_dir")
    status = "VALID" if not issues else "INVALID"
    if warnings and status == "VALID":
        status = "VALID_WITH_WARNINGS"
    return {"status": status, "issues": issues, "warnings": warnings}
