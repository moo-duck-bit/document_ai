"""Trial path helpers and JSON I/O."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from document_ai.paths import PROJECT_ROOT
from document_ai.trial.models import TRIAL_SUBDIRS

DEFAULT_TRIALS_ROOT = PROJECT_ROOT / "data" / "trials"
DEFAULT_BASELINE_ROOT = PROJECT_ROOT / "reports" / "baselines"
DEFAULT_EVALUATION_ROOT = PROJECT_ROOT / "data" / "evaluation"


def trials_root(root: str | Path | None = None) -> Path:
    return Path(root) if root else DEFAULT_TRIALS_ROOT


def trial_dir(trial_id: str | Path, *, root: str | Path | None = None) -> Path:
    path = Path(trial_id)
    if path.exists() and (path / "trial_manifest.json").exists():
        return path.resolve()
    if path.is_absolute() or path.parts[0] in (".", "data", "reports"):
        return path.resolve()
    return (trials_root(root) / str(trial_id)).resolve()


def ensure_trial_layout(trial_path: Path) -> dict[str, Path]:
    trial_path.mkdir(parents=True, exist_ok=True)
    dirs = {name: trial_path / name for name in TRIAL_SUBDIRS}
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    (dirs["reports"] / "tables").mkdir(parents=True, exist_ok=True)
    (dirs["reports"] / "figures" / "data").mkdir(parents=True, exist_ok=True)
    return dirs


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(trial_path: Path) -> dict[str, Any]:
    return read_json(trial_path / "trial_manifest.json")


def save_manifest(trial_path: Path, manifest: dict[str, Any]) -> Path:
    return write_json(trial_path / "trial_manifest.json", manifest)


def rel_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
