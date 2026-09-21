"""Safety-first paper tables over scorecard + sealed holdout."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .holdout import build_holdout_split, export_holdout_split
from .paths import default_cases_root, default_reports_dir
from .scorecard import build_scorecard, export_scorecard


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "mu_zero_rate": _mean([1.0 if r.get("mu_zero") else 0.0 for r in rows]),
        "mean_mu_sum": _mean([float(r.get("mu_sum") or 0.0) for r in rows]),
        "mean_false_patch": _mean([float(r.get("false_patch") or 0.0) for r in rows]),
        "mean_unsafe_write": _mean([float(r.get("unsafe_write") or 0.0) for r in rows]),
        "mean_original_broken": _mean([float(r.get("original_broken") or 0.0) for r in rows]),
        "mean_unapproved_write": _mean([float(r.get("unapproved_write") or 0.0) for r in rows]),
        "mean_recall_at_3": _mean([float(r.get("recall_at_3") or 0.0) for r in rows]),
        "mean_cell_f1": _mean([float(r.get("cell_f1") or 0.0) for r in rows]),
        "mean_field_f1": _mean([float(r.get("field_f1") or 0.0) for r in rows])
        if any("field_f1" in r for r in rows)
        else None,
    }


def build_safety_first_tables(
    *,
    cases_root: Path | None = None,
    modes: list[str] | None = None,
    scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build paper-facing Safety-first tables for full / holdout / dev splits."""
    cases_root = cases_root or default_cases_root()
    modes = modes or ["demo_safe", "live"]
    scorecard = scorecard or build_scorecard(cases_root=cases_root, modes=modes)
    split = build_holdout_split(cases_root=cases_root)
    hold_set = set(split["holdout_case_ids"])
    dev_set = set(split["dev_case_ids"])

    tables: dict[str, Any] = {
        "safety_first_order": [
            "mu_zero_rate",
            "mean_mu_sum",
            "mean_false_patch",
            "mean_unsafe_write",
            "mean_original_broken",
            "mean_unapproved_write",
            "mean_recall_at_3",
            "mean_cell_f1",
            "mean_field_f1",
        ],
        "holdout_split": {
            "seed": split["seed"],
            "holdout_case_ids": split["holdout_case_ids"],
            "dev_case_ids": split["dev_case_ids"],
        },
        "splits": {},
        "notes": {
            "primary": "Safety (μ=0 rate) first; R@3 / cell F1 / field F1 are secondary.",
            "holdout": "Sealed by seed — do not tune on holdout.",
            "field_f1": "Secondary Form Fill signal on structured cells only (Small-A).",
        },
    }

    for split_name, id_set in (
        ("full", None),
        ("holdout", hold_set),
        ("dev", dev_set),
    ):
        tables["splits"][split_name] = {}
        for mode in modes:
            rows = [
                r
                for r in scorecard["per_case"]
                if r.get("mode") == mode and (id_set is None or r.get("case_id") in id_set)
            ]
            tables["splits"][split_name][mode] = _summarize_rows(rows)

    return {"tables": tables, "scorecard": scorecard, "holdout_split": split}


def export_safety_first_tables(
    payload: dict[str, Any],
    *,
    out_dir: Path | None = None,
    stem: str = "paper_safety_first",
) -> dict[str, Path]:
    out_dir = out_dir or default_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    csv_path = out_dir / f"{stem}.csv"

    tables = payload["tables"]
    json_path.write_text(json.dumps(payload["tables"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Markdown paper table
    lines = [
        "# Safety-first results (Small-A regulatory_bench)",
        "",
        f"Holdout seed: `{tables['holdout_split']['seed']}`",
        "",
        "Order: **μ=0 rate → μ terms → R@3 → cell F1 → field F1 (secondary)**.",
        "",
    ]
    for split_name, modes in tables["splits"].items():
        lines.append(f"## Split: {split_name}")
        lines.append("")
        lines.append(
            "| mode | n | μ=0 rate | mean μ sum | false_patch | unsafe_write | "
            "original_broken | unapproved_write | R@3 | cell F1 | field F1 |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for mode, block in modes.items():
            ff = block.get("mean_field_f1")
            ff_s = "" if ff is None else f"{ff:.3f}"
            lines.append(
                f"| {mode} | {block.get('n', 0)} | {block.get('mu_zero_rate', 0):.3f} | "
                f"{block.get('mean_mu_sum', 0):.3f} | {block.get('mean_false_patch', 0):.3f} | "
                f"{block.get('mean_unsafe_write', 0):.3f} | {block.get('mean_original_broken', 0):.3f} | "
                f"{block.get('mean_unapproved_write', 0):.3f} | {block.get('mean_recall_at_3', 0):.3f} | "
                f"{block.get('mean_cell_f1', 0):.3f} | {ff_s} |"
            )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "split", "mode", "n", "mu_zero_rate", "mean_mu_sum",
                "mean_false_patch", "mean_unsafe_write", "mean_original_broken",
                "mean_unapproved_write", "mean_recall_at_3", "mean_cell_f1", "mean_field_f1",
            ],
        )
        w.writeheader()
        for split_name, modes in tables["splits"].items():
            for mode, block in modes.items():
                w.writerow({"split": split_name, "mode": mode, **block})

    # also persist holdout split next to tables
    export_holdout_split(payload["holdout_split"], out_dir=out_dir)
    return {"json": json_path, "md": md_path, "csv": csv_path}


def run_paper_tables(
    *,
    cases_root: Path | None = None,
    out_dir: Path | None = None,
    modes: list[str] | None = None,
) -> dict[str, Any]:
    payload = build_safety_first_tables(cases_root=cases_root, modes=modes)
    # also export full scorecard for provenance
    sc_paths = export_scorecard(payload["scorecard"], out_dir=out_dir or default_reports_dir())
    paths = export_safety_first_tables(payload, out_dir=out_dir)
    paths["scorecard_json"] = sc_paths["json"]
    return {"tables": payload["tables"], "paths": {k: str(v) for k, v in paths.items()}}
