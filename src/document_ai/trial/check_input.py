"""trial-check-input."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.trial.dataset import load_dataset_manifest, validate_dataset_manifest
from document_ai.trial.leakage import check_holdout_leakage, validate_trial_input_dirs
from document_ai.trial.paths import (
    load_manifest,
    read_json,
    rel_to_project,
    save_manifest,
    trial_dir,
    write_json,
)


REQUIRED_BY_TYPE = {
    "new_document_generation": ["input.json"],
    "change_update": ["input.json"],
}


def check_trial_input(trial: str | Path) -> dict[str, Any]:
    path = trial_dir(trial)
    if not (path / "trial_manifest.json").exists():
        raise FileNotFoundError(f"trial_manifest.json missing: {path}")

    manifest = load_manifest(path)
    case_id = str(manifest.get("case_id") or "")
    trial_type = str(manifest.get("trial_type") or "change_update")
    validation = validate_trial_input_dirs(path, case_id=case_id)

    findings = list(validation["findings"])
    warnings = list(validation["warnings"])

    input_dir = path / "input"
    required = REQUIRED_BY_TYPE.get(trial_type, ["input.json"])
    for name in required:
        if not (input_dir / name).exists():
            # synthetic may use README only early — still warn
            if manifest.get("synthetic") and name == "input.json":
                warnings.append(f"synthetic trial missing preferred input: {name}")
            else:
                findings.append(f"missing required input: input/{name}")

    if trial_type == "change_update":
        has_change = any(
            p.name.lower().startswith("change") or p.suffix == ".txt"
            for p in input_dir.glob("*")
            if p.is_file()
        )
        if not has_change and not (input_dir / "change_request.json").exists():
            warnings.append("change_update trial has no change request file yet")

    dataset = load_dataset_manifest()
    dataset_check = validate_dataset_manifest(dataset)
    if not dataset_check["ok"]:
        findings.extend(dataset_check["errors"])
    warnings.extend(dataset_check.get("warnings") or [])

    inventory = validation["inventory"]
    input_files = [path / "input" / Path(f["path"]).name for f in inventory.get("files", [])]
    # Prefer absolute from inventory hashing already done
    from document_ai.trial.leakage import iter_files

    holdout_warnings = check_holdout_leakage(
        trial_case_id=case_id,
        input_files=iter_files(input_dir),
        dataset_cases=dataset.get("cases"),
    )
    findings.extend([w for w in holdout_warnings if "forbidden path marker" in w])
    warnings.extend([w for w in holdout_warnings if "forbidden path marker" not in w])

    # Gold path references inside input_manifest / notes
    input_manifest_path = path / "input_manifest.json"
    if input_manifest_path.exists():
        im = read_json(input_manifest_path)
        blob = str(im).lower()
        if "data/gold" in blob or "human_revised" in blob and "do not" not in blob:
            if "data/gold" in blob:
                findings.append("input_manifest references data/gold")

    ok = len(findings) == 0
    result = {
        "ok": ok,
        "trial_id": manifest.get("trial_id"),
        "trial_dir": rel_to_project(path),
        "case_id": case_id,
        "trial_type": trial_type,
        "findings": findings,
        "warnings": warnings,
        "inventory": inventory,
        "dataset_check": dataset_check,
        "data_leakage_checked": True,
        "data_leakage_clean": ok and inventory.get("data_leakage_clean", False),
    }
    write_json(path / "metrics" / "input_check.json", result)
    write_json(
        path / "input_manifest.json",
        {
            "trial_id": manifest.get("trial_id"),
            "status": "checked" if ok else "check_failed",
            "files": inventory.get("files", []),
            "check": {
                "ok": ok,
                "findings": findings,
                "warnings": warnings,
            },
            "synthetic": bool(manifest.get("synthetic")),
        },
    )
    manifest["data_leakage_checked"] = True
    manifest["data_leakage_clean"] = result["data_leakage_clean"]
    save_manifest(path, manifest)
    return result
