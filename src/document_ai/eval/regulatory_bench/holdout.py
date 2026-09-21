"""Sealed holdout split for Small-A regulatory_bench.

Deterministic, seed-locked split so paper tables stay reproducible.
Dev set may be inspected during iteration; holdout is for sealed reporting only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .paths import default_cases_root, default_reports_dir

DEFAULT_SEED = "document-tnr-small-a-holdout-v1"
DEFAULT_HOLDOUT_FRAC = 0.25


def _stable_bucket(case_id: str, seed: str) -> float:
    digest = hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).hexdigest()
    # map first 8 hex chars → [0, 1)
    return int(digest[:8], 16) / 0xFFFFFFFF


def list_case_ids(cases_root: Path | None = None) -> list[str]:
    root = cases_root or default_cases_root()
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and (p / "meta.json").exists() and p.name.startswith("case_")
    )


def build_holdout_split(
    *,
    cases_root: Path | None = None,
    seed: str = DEFAULT_SEED,
    holdout_frac: float = DEFAULT_HOLDOUT_FRAC,
    min_holdout: int = 4,
) -> dict[str, Any]:
    """Return sealed holdout vs dev partition (deterministic)."""
    case_ids = list_case_ids(cases_root)
    scored = sorted((_stable_bucket(c, seed), c) for c in case_ids)
    n = len(scored)
    n_hold = max(min_holdout, int(round(n * holdout_frac)))
    n_hold = min(n_hold, max(0, n - 1))  # leave at least one in dev when possible
    holdout = [c for _, c in scored[:n_hold]]
    dev = [c for _, c in scored[n_hold:]]
    return {
        "seed": seed,
        "holdout_frac": holdout_frac,
        "n_total": n,
        "n_holdout": len(holdout),
        "n_dev": len(dev),
        "holdout_case_ids": holdout,
        "dev_case_ids": dev,
        "protocol": {
            "sealed": True,
            "note": (
                "Holdout IDs are fixed by seed. Do not tune on holdout metrics. "
                "Paper Safety-first tables should report holdout (and optionally full) splits."
            ),
        },
    }


def export_holdout_split(
    split: dict[str, Any] | None = None,
    *,
    out_dir: Path | None = None,
    stem: str = "sealed_holdout_split",
) -> Path:
    out_dir = out_dir or default_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    split = split or build_holdout_split()
    path = out_dir / f"{stem}.json"
    path.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
