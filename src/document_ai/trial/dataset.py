"""Evaluation dataset manifest load/validate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.paths import PROJECT_ROOT
from document_ai.trial.leakage import check_dataset_role_conflicts
from document_ai.trial.models import DATASET_ROLES
from document_ai.trial.paths import DEFAULT_EVALUATION_ROOT, read_json, write_json

DEFAULT_MANIFEST_PATH = DEFAULT_EVALUATION_ROOT / "dataset_manifest.json"


def default_dataset_manifest() -> dict[str, Any]:
    return {
        "version": "1.0",
        "description": "Document Harness evaluation dataset roles for Trial/holdout separation",
        "baseline_system_version": "v0.5-document-harness",
        "baseline_commit": "d73fc18",
        "cases": [
            {
                "case_id": "lab_ec_sw",
                "domain": "medical_software",
                "role": "development",
                "document_types": ["MDSR", "MDDR", "XXCS"],
                "gold_status": "plan_gold",
                "human_review_status": "pending",
                "case_dir": "data/cases/lab_ec_sw",
            },
            {
                "case_id": "jm_collection",
                "domain": "ecommerce_b2c",
                "role": "reference",
                "document_types": ["MDSR", "MDDR", "XXCS"],
                "gold_status": "plan_gold",
                "human_review_status": "pending",
                "case_dir": "data/cases/jm_collection",
            },
            {
                "case_id": "inventory_mgmt",
                "domain": "general_software",
                "role": "validation",
                "document_types": ["MDSR", "MDDR"],
                "gold_status": "provisional",
                "human_review_status": "pending",
                "case_dir": "data/cases/inventory_mgmt",
            },
            {
                "case_id": "hospital_reservation",
                "domain": "general_software",
                "role": "holdout",
                "document_types": ["MDSR", "MDDR"],
                "gold_status": "frozen",
                "human_review_status": "prepared",
                "case_dir": "data/cases/hospital_reservation",
            },
        ],
    }


def ensure_dataset_manifest(path: str | Path | None = None) -> Path:
    manifest_path = Path(path) if path else DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        write_json(manifest_path, default_dataset_manifest())
    return manifest_path


def load_dataset_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = ensure_dataset_manifest(path)
    return read_json(manifest_path)


def validate_dataset_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    cases = manifest.get("cases") or []
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty list")
        return {"ok": False, "errors": errors, "warnings": warnings}

    seen: set[str] = set()
    for idx, entry in enumerate(cases):
        case_id = str(entry.get("case_id") or "")
        role = str(entry.get("role") or "")
        if not case_id:
            errors.append(f"cases[{idx}].case_id missing")
        if case_id in seen:
            errors.append(f"duplicate case_id: {case_id}")
        seen.add(case_id)
        if role not in DATASET_ROLES:
            errors.append(f"{case_id}: invalid role '{role}'")
        case_dir = entry.get("case_dir")
        if case_dir:
            path = PROJECT_ROOT / case_dir if not Path(case_dir).is_absolute() else Path(case_dir)
            if not path.exists():
                warnings.append(f"{case_id}: case_dir not found: {case_dir}")

    conflicts = check_dataset_role_conflicts(cases)
    # For default manifest, each case_id appears once — conflicts empty.
    # Multi-entry conflicts are errors.
    errors.extend(conflicts)
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "case_count": len(cases)}
