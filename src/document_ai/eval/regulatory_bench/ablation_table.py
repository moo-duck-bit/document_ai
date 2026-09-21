"""One-shot sandbox ablation μ table for paper / CLI.

Honest labeling: sandbox counterfactual only — never a live harness flip with
safety disabled on the original corpus.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .ablation import run_ablation_suite
from .paths import default_cases_root, default_reports_dir
from .types import ABLATION_MU_MAP, MU_KEYS


def _mu_sum(mu: dict[str, Any] | None) -> int:
    if not mu:
        return 0
    return sum(int(mu.get(k, 0) or 0) for k in MU_KEYS)


def build_ablation_mu_table(
    *,
    cases_root: Path | None = None,
    case_ids: list[str] | None = None,
    variants: tuple[str, ...] = ("no_gate", "no_copy_only", "no_closure"),
) -> dict[str, Any]:
    """Aggregate sandbox ablation μ across cases into a paper-ready table."""
    root = cases_root or default_cases_root()
    if case_ids is None:
        case_dirs = sorted(
            p for p in root.iterdir() if p.is_dir() and (p / "meta.json").exists()
        )
    else:
        case_dirs = [root / cid for cid in case_ids]

    per_case: list[dict[str, Any]] = []
    # Aggregate mean μ per variant
    agg: dict[str, list[dict[str, Any]]] = {v: [] for v in ("full", *variants)}

    for case_dir in case_dirs:
        if not case_dir.exists():
            continue
        suite = run_ablation_suite(case_dir, variants=variants)
        row = {
            "case_id": case_dir.name,
            "disclaimer": suite.get("disclaimer"),
            "by_variant": {},
        }
        for r in suite.get("rows") or []:
            name = str(r.get("variant") or "")
            block = {
                "mu": r.get("mu") or {},
                "mu_sum": _mu_sum(r.get("mu")),
                "mu_zero": bool(r.get("mu_zero")),
                "expected_mu_keys": list(r.get("expected_mu_keys") or []),
                "expected_hit": bool(r.get("expected_hit")),
            }
            row["by_variant"][name] = block
            if name in agg:
                agg[name].append(block)
        per_case.append(row)

    def _mean_mu(blocks: list[dict[str, Any]]) -> dict[str, Any]:
        if not blocks:
            return {"n": 0}
        out: dict[str, Any] = {
            "n": len(blocks),
            "mu_zero_rate": sum(1.0 if b.get("mu_zero") else 0.0 for b in blocks) / len(blocks),
            "mean_mu_sum": sum(float(b.get("mu_sum") or 0) for b in blocks) / len(blocks),
            "expected_hit_rate": sum(1.0 if b.get("expected_hit") else 0.0 for b in blocks)
            / len(blocks),
        }
        for k in MU_KEYS:
            out[f"mean_{k}"] = sum(float((b.get("mu") or {}).get(k, 0) or 0) for b in blocks) / len(
                blocks
            )
        return out

    summary = {
        "n_cases": len(per_case),
        "variants": {name: _mean_mu(blocks) for name, blocks in agg.items()},
        "ablation_mu_map": {k: list(v) for k, v in ABLATION_MU_MAP.items()},
        "label": "sandbox_counterfactual",
        "disclaimer": (
            "Sandbox dry-run / counterfactual only. "
            "Do not describe as live execution with safety devices disabled."
        ),
    }
    return {"summary": summary, "per_case": per_case}


def export_ablation_mu_table(
    payload: dict[str, Any],
    *,
    out_dir: Path | None = None,
    stem: str = "sandbox_ablation_mu",
) -> dict[str, Path]:
    out_dir = out_dir or default_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    csv_path = out_dir / f"{stem}.csv"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = payload["summary"]
    lines = [
        "# Sandbox ablation μ table (Small-A)",
        "",
        f"**Label:** `{summary.get('label')}` — counterfactual only.",
        "",
        summary.get("disclaimer") or "",
        "",
        "| variant | n | μ=0 rate | mean μ sum | false_patch | unsafe_write | "
        "original_broken | unapproved_write | expected_hit_rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, block in (summary.get("variants") or {}).items():
        if not block or block.get("n", 0) == 0:
            continue
        lines.append(
            f"| `{variant}` | {block.get('n', 0)} | {block.get('mu_zero_rate', 0):.3f} | "
            f"{block.get('mean_mu_sum', 0):.3f} | {block.get('mean_false_patch', 0):.3f} | "
            f"{block.get('mean_unsafe_write', 0):.3f} | {block.get('mean_original_broken', 0):.3f} | "
            f"{block.get('mean_unapproved_write', 0):.3f} | {block.get('expected_hit_rate', 0):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Ablation → μ map",
            "",
            "| removed control | expected μ keys |",
            "|---|---|",
        ]
    )
    for variant, keys in (summary.get("ablation_mu_map") or {}).items():
        lines.append(f"| `{variant}` | {', '.join(f'`{k}`' for k in keys)} |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "variant",
                "n",
                "mu_zero_rate",
                "mean_mu_sum",
                "mean_false_patch",
                "mean_unsafe_write",
                "mean_original_broken",
                "mean_unapproved_write",
                "expected_hit_rate",
            ],
        )
        w.writeheader()
        for variant, block in (summary.get("variants") or {}).items():
            if block.get("n", 0):
                w.writerow({"variant": variant, **block})

    return {"json": json_path, "md": md_path, "csv": csv_path}


def run_ablation_mu_table(
    *,
    cases_root: Path | None = None,
    out_dir: Path | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    payload = build_ablation_mu_table(cases_root=cases_root, case_ids=case_ids)
    paths = export_ablation_mu_table(payload, out_dir=out_dir)
    return {"summary": payload["summary"], "paths": {k: str(v) for k, v in paths.items()}}
