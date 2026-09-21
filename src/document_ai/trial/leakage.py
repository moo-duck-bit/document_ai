"""Data leakage and input safety checks for trials."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.paths import PROJECT_ROOT
from document_ai.trial.models import FORBIDDEN_INPUT_PATH_MARKERS, SENSITIVE_NAME_MARKERS
from document_ai.trial.paths import rel_to_project, sha256_file


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/").lower()


def path_looks_like_leakage(path: str | Path) -> list[str]:
    text = _norm(path)
    hits: list[str] = []
    for marker in FORBIDDEN_INPUT_PATH_MARKERS:
        if marker.replace("\\", "/").lower() in text:
            hits.append(marker)
    return hits


def scan_sensitive_names(path: Path) -> list[str]:
    name = path.name.lower()
    return [marker for marker in SENSITIVE_NAME_MARKERS if marker in name]


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def check_dataset_role_conflicts(cases: list[dict[str, Any]]) -> list[str]:
    """Detect conflicting roles for the same case_id."""
    by_id: dict[str, set[str]] = {}
    for entry in cases:
        case_id = str(entry.get("case_id", ""))
        role = str(entry.get("role", ""))
        if not case_id:
            continue
        by_id.setdefault(case_id, set()).add(role)
    conflicts: list[str] = []
    for case_id, roles in by_id.items():
        if "holdout" in roles and ("development" in roles or "real_world_trial" in roles):
            conflicts.append(
                f"{case_id}: holdout cannot also be development/real_world_trial ({sorted(roles)})"
            )
        if len(roles) > 1 and "holdout" in roles and "validation" in roles:
            # holdout + validation is allowed only if explicitly documented; warn
            conflicts.append(f"{case_id}: multiple roles {sorted(roles)}")
    return conflicts


def check_holdout_leakage(
    *,
    trial_case_id: str,
    input_files: list[Path],
    dataset_cases: list[dict[str, Any]] | None = None,
) -> list[str]:
    warnings: list[str] = []
    holdout_ids = {
        str(c.get("case_id"))
        for c in (dataset_cases or [])
        if c.get("role") == "holdout" or c.get("gold_status") == "frozen"
    }
    for path in input_files:
        rel = rel_to_project(path)
        for holdout_id in holdout_ids:
            if holdout_id and holdout_id != trial_case_id and holdout_id in _norm(rel):
                warnings.append(f"holdout case material referenced in input: {rel}")
        for hit in path_looks_like_leakage(rel):
            warnings.append(f"forbidden path marker '{hit}' in {rel}")
    return warnings


def build_input_inventory(input_dir: Path) -> dict[str, Any]:
    files = iter_files(input_dir)
    entries: list[dict[str, Any]] = []
    leakage: list[str] = []
    sensitive: list[str] = []
    for path in files:
        rel = rel_to_project(path) if PROJECT_ROOT in path.resolve().parents or path.resolve() == PROJECT_ROOT else str(path)
        try:
            rel = rel_to_project(path)
        except Exception:
            rel = str(path)
        entry = {
            "path": rel,
            "name": path.name,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        entries.append(entry)
        for hit in path_looks_like_leakage(path):
            leakage.append(f"{rel}: marker {hit}")
        for hit in scan_sensitive_names(path):
            sensitive.append(f"{rel}: sensitive name marker '{hit}'")
        # human_revised must not pre-exist under input
        if "human_revised" in path.parts:
            leakage.append(f"{rel}: human_revised under input/")
        if path.name.lower().startswith("gold_"):
            leakage.append(f"{rel}: gold-prefixed filename in input")
    return {
        "file_count": len(entries),
        "files": entries,
        "leakage_warnings": leakage,
        "sensitive_warnings": sensitive,
        "data_leakage_checked": True,
        "data_leakage_clean": len(leakage) == 0,
    }


def validate_trial_input_dirs(trial_path: Path, *, case_id: str) -> dict[str, Any]:
    input_dir = trial_path / "input"
    human_revised = trial_path / "human_revised"
    findings: list[str] = []
    warnings: list[str] = []

    if not input_dir.exists():
        findings.append("missing input/ directory")
    inventory = build_input_inventory(input_dir)
    findings.extend(inventory["leakage_warnings"])
    warnings.extend(inventory["sensitive_warnings"])

    # Pre-existing human revised files before review are leakage for generation phase
    revised_files = [p for p in iter_files(human_revised) if p.suffix.lower() in {".docx", ".json", ".md"}]
    # Allow empty placeholder .gitkeep
    revised_docs = [p for p in revised_files if p.name != ".gitkeep" and not p.name.endswith(".template.json")]
    manifest = {}
    manifest_path = trial_path / "trial_manifest.json"
    if manifest_path.exists():
        import json

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    status = manifest.get("status", "prepared")
    if revised_docs and status in {"prepared", "generated"}:
        # Before review_pending, human_revised should be empty (except templates)
        premature = [
            rel_to_project(p)
            for p in revised_docs
            if "template" not in p.name.lower()
        ]
        if premature and status == "prepared":
            findings.append(
                "human_revised contains documents before generation/review: " + ", ".join(premature)
            )

    # Case id consistency
    for path in inventory["files"]:
        name = path["name"]
        if case_id and case_id not in name and name in {
            "hospital_reservation.docx",
            "inventory_mgmt.docx",
        }:
            warnings.append(f"possible case mismatch for {name}")

    return {
        "ok": len(findings) == 0,
        "findings": findings,
        "warnings": warnings,
        "inventory": inventory,
        "case_id": case_id,
        "status": status,
    }
