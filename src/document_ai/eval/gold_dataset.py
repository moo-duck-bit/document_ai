"""Independent gold dataset paths, manifest, and resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLD_ROOT = Path("data/gold")
MANIFEST_NAME = "case_manifest.json"


def gold_root(root: str | Path | None = None) -> Path:
    return Path(root) if root else GOLD_ROOT


def manifest_path(root: str | Path | None = None) -> Path:
    return gold_root(root) / MANIFEST_NAME


def load_gold_manifest(root: str | Path | None = None) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.exists():
        return {"version": "1.0", "cases": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_gold_manifest(manifest: dict[str, Any], root: str | Path | None = None) -> Path:
    root_path = gold_root(root)
    root_path.mkdir(parents=True, exist_ok=True)
    (root_path / "mdsr").mkdir(parents=True, exist_ok=True)
    (root_path / "mddr").mkdir(parents=True, exist_ok=True)
    (root_path / "xxcs").mkdir(parents=True, exist_ok=True)
    (root_path / "fields").mkdir(parents=True, exist_ok=True)
    path = manifest_path(root)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def case_entry(manifest: dict[str, Any], case_id: str) -> dict[str, Any] | None:
    for entry in manifest.get("cases", []):
        if entry.get("case_id") == case_id:
            return entry
    return None


def gold_mdsr_path(case_id: str, root: str | Path | None = None) -> Path:
    return gold_root(root) / "mdsr" / f"{case_id}.docx"


def gold_mddr_path(case_id: str, root: str | Path | None = None) -> Path:
    return gold_root(root) / "mddr" / f"{case_id}.docx"


def gold_xxcs_path(case_id: str, root: str | Path | None = None) -> Path:
    return gold_root(root) / "xxcs" / f"{case_id}.docx"


def gold_fields_path(case_id: str, root: str | Path | None = None) -> Path:
    return gold_root(root) / "fields" / f"{case_id}.gold_fields.json"


def resolve_independent_gold(
    case_id: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Path | None]:
    """Resolve independent gold artifacts for a case_id."""
    mdsr = gold_mdsr_path(case_id, root)
    mddr = gold_mddr_path(case_id, root)
    xxcs = gold_xxcs_path(case_id, root)
    fields = gold_fields_path(case_id, root)
    return {
        "mdsr": mdsr if mdsr.exists() else None,
        "mddr": mddr if mddr.exists() else None,
        "xxcs": xxcs if xxcs.exists() else None,
        "fields": fields if fields.exists() else None,
    }


def upsert_manifest_case(
    case_id: str,
    *,
    split: str = "train",
    domain: str = "",
    product_name: str = "",
    status: str = "provisional",
    case_dir: str = "",
    notes: str = "",
    root: str | Path | None = None,
) -> dict[str, Any]:
    manifest = load_gold_manifest(root)
    cases = list(manifest.get("cases") or [])
    entry = {
        "case_id": case_id,
        "split": split,
        "domain": domain,
        "product_name": product_name,
        "status": status,
        "case_dir": case_dir,
        "gold_mdsr": f"mdsr/{case_id}.docx",
        "gold_mddr": f"mddr/{case_id}.docx",
        "gold_fields": f"fields/{case_id}.gold_fields.json",
        "notes": notes,
    }
    replaced = False
    for i, existing in enumerate(cases):
        if existing.get("case_id") == case_id:
            merged = {**existing, **entry}
            cases[i] = merged
            replaced = True
            break
    if not replaced:
        cases.append(entry)
    manifest["version"] = manifest.get("version", "1.0")
    manifest["cases"] = cases
    save_gold_manifest(manifest, root)
    return entry
