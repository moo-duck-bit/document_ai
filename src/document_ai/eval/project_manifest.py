"""Real EC-SW project case manifest loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_FILENAME = "project_manifest.json"


def load_project_manifest(case_dir: Path) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    path = case_dir / MANIFEST_FILENAME
    if not path.exists():
        return {
            "case_id": case_dir.name,
            "project_type": "ec_sw",
            "case_dir": str(case_dir),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("case_id", case_dir.name)
    payload["case_dir"] = str(case_dir)
    return payload


def resolve_gold_paths(
    case_dir: Path,
    manifest: dict[str, Any],
    *,
    gold_mdsr: Path | None = None,
    gold_mddr: Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Resolve gold DOCX paths.

    Priority:
    1. Explicit CLI overrides
    2. Independent gold dataset (`data/gold/`)
    3. Manifest gold / gold_fallback
    """
    from document_ai.eval.gold_dataset import resolve_independent_gold

    case_dir = case_dir.resolve()
    case_id = manifest.get("case_id") or case_dir.name

    def _resolve(candidate: str | Path | None) -> Path | None:
        if not candidate:
            return None
        path = Path(candidate)
        if not path.is_absolute():
            # Prefer paths relative to repo root, then case_dir
            repo_candidate = Path(candidate)
            if repo_candidate.exists():
                return repo_candidate.resolve()
            path = (case_dir / path).resolve()
        return path if path.exists() else None

    mdsr = gold_mdsr if gold_mdsr and Path(gold_mdsr).exists() else None
    mddr = gold_mddr if gold_mddr and Path(gold_mddr).exists() else None
    if gold_mdsr and mdsr is None:
        mdsr = _resolve(gold_mdsr)
    if gold_mddr and mddr is None:
        mddr = _resolve(gold_mddr)

    independent = resolve_independent_gold(case_id)
    if mdsr is None:
        mdsr = independent.get("mdsr")  # type: ignore[assignment]
    if mddr is None:
        mddr = independent.get("mddr")  # type: ignore[assignment]

    gold_block = manifest.get("gold") or {}
    if mdsr is None:
        mdsr = _resolve(manifest.get("gold_mdsr") or gold_block.get("mdsr"))
    if mddr is None:
        mddr = _resolve(manifest.get("gold_mddr") or gold_block.get("mddr"))

    fallback = manifest.get("gold_fallback") or {}
    if mdsr is None:
        mdsr = _resolve(fallback.get("mdsr"))
    if mddr is None:
        mddr = _resolve(fallback.get("mddr"))

    return mdsr, mddr


def benchmark_expectations(manifest: dict[str, Any]) -> dict[str, Any]:
    return dict(manifest.get("benchmark") or manifest.get("expectations") or {})
