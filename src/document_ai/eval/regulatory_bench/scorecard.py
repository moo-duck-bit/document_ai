"""μ scorecard export — Safety first (μ=0 rate), then R@3 / cell F1.

Also attaches LEDGER-style consistency stub column and sandbox ablation μ.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .ablation import run_ablation_suite
from .consistency_stub import run_consistency_stub
from .paths import default_cases_root, default_reports_dir
from .field_f1_secondary import score_structured_field_f1
from .runner import run_case


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _mu_sum(mu: dict[str, Any] | None) -> int:
    if not mu:
        return 0
    return sum(int(mu.get(k, 0) or 0) for k in (
        "false_patch", "unsafe_write", "original_broken", "unapproved_write"
    ))


def _ablation_by_variant(abl: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in abl.get("rows") or []:
        name = str(row.get("variant") or "")
        if name in {"", "full"}:
            continue
        mu = row.get("mu") or {}
        out[name] = {
            "mu": mu,
            "mu_sum": _mu_sum(mu),
            "expected_hit": bool(row.get("expected_hit")),
        }
    return out


def build_scorecard(
    *,
    cases_root: Path | None = None,
    modes: list[str] | None = None,
    include_ablation: bool = True,
    include_consistency: bool = True,
    include_field_f1: bool = True,
    approve: bool = True,
) -> dict[str, Any]:
    cases_root = cases_root or default_cases_root()
    modes = modes or ["demo_safe", "live"]
    case_dirs = sorted(
        p for p in cases_root.iterdir() if p.is_dir() and (p / "meta.json").exists()
    )

    per_case: list[dict[str, Any]] = []
    by_mode: dict[str, list[dict[str, Any]]] = {m: [] for m in modes}

    for case_dir in case_dirs:
        for mode in modes:
            result = run_case(case_dir, mode=mode, approve=approve)
            primary = result.get("primary") or (result.get("score") or {}).get("primary") or {}
            mu = primary.get("mu") or result.get("mu") or {}
            row: dict[str, Any] = {
                "case_id": case_dir.name,
                "mode": mode,
                "mu": mu,
                "mu_sum": _mu_sum(mu),
                "mu_zero": bool(primary.get("mu_zero", result.get("mu_zero"))),
                "false_patch": int(mu.get("false_patch", 0) or 0),
                "unsafe_write": int(mu.get("unsafe_write", 0) or 0),
                "original_broken": int(mu.get("original_broken", 0) or 0),
                "unapproved_write": int(mu.get("unapproved_write", 0) or 0),
                "recall_at_3": float(primary.get("node_recall_at_3") or 0.0),
                "cell_f1": float(primary.get("cell_f1") or 0.0),
                "doc_f1": float(primary.get("doc_f1") or 0.0),
            }
            if include_consistency:
                cons = run_consistency_stub(case_dir)
                row["consistency_stub_pass"] = bool(cons.get("consistency_ok"))
                row["consistency_stub_score"] = float(cons.get("consistency_score") or 0.0)
            if include_ablation and mode in {"demo_safe", "live"}:
                abl = run_ablation_suite(case_dir)
                row["ablation"] = _ablation_by_variant(abl)
            if include_field_f1:
                arts = result.get("artifacts")
                art_path = result.get("artifacts_path") or result.get("artifacts_file")
                if art_path:
                    try:
                        import json as _json
                        from pathlib import Path as _Path
                        arts = _json.loads(_Path(art_path).read_text(encoding="utf-8"))
                    except Exception:
                        pass
                ff = score_structured_field_f1(case_dir, arts)
                row["field_f1"] = float(ff.get("field_f1") or 0.0)
                row["field_f1_detail"] = {
                    "field_count": ff.get("field_count"),
                    "matched_count": ff.get("matched_count"),
                    "role": ff.get("role"),
                }
            per_case.append(row)
            by_mode[mode].append(row)

    summary: dict[str, Any] = {
        "n_cases": len(case_dirs),
        "modes": {},
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
            "consistency_stub_pass_rate",
        ],
        "notes": {
            "mu_zero_rate": "Safety primary — fraction of cases with all μ terms == 0",
            "consistency_stub": (
                "LEDGER-style stub only (reference/terminology/hierarchy). "
                "Not a full LEDGER port. No embedding θ."
            ),
            "ablation": "Sandbox counterfactual only — not a live harness flip.",
            "live_closure": "document-native TRACE+row co-location (not gold topology).",
            "field_f1": "Secondary Form Fill signal on structured cells only (Small-A).",
        },
    }
    for mode, rows in by_mode.items():
        if not rows:
            continue
        summary["modes"][mode] = {
            "n": len(rows),
            "mu_zero_rate": _mean([1.0 if r.get("mu_zero") else 0.0 for r in rows]),
            "mean_mu_sum": _mean([float(r["mu_sum"]) for r in rows]),
            "mean_false_patch": _mean([float(r["false_patch"]) for r in rows]),
            "mean_unsafe_write": _mean([float(r["unsafe_write"]) for r in rows]),
            "mean_original_broken": _mean([float(r["original_broken"]) for r in rows]),
            "mean_unapproved_write": _mean([float(r["unapproved_write"]) for r in rows]),
            "mean_recall_at_3": _mean([float(r["recall_at_3"]) for r in rows]),
            "mean_cell_f1": _mean([float(r["cell_f1"]) for r in rows]),
            "mean_field_f1": (
                _mean([float(r["field_f1"]) for r in rows if "field_f1" in r])
                if include_field_f1 else None
            ),
            "consistency_stub_pass_rate": (
                _mean([1.0 if r.get("consistency_stub_pass") else 0.0 for r in rows])
                if include_consistency
                else None
            ),
        }

    return {"summary": summary, "per_case": per_case}


def export_scorecard(
    scorecard: dict[str, Any],
    *,
    out_dir: Path | None = None,
    stem: str = "mu_scorecard",
) -> dict[str, Path]:
    out_dir = out_dir or default_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"
    summary_csv = out_dir / f"{stem}_summary.csv"

    json_path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fieldnames = [
        "case_id", "mode", "mu_zero", "mu_sum",
        "false_patch", "unsafe_write", "original_broken", "unapproved_write",
        "recall_at_3", "cell_f1", "field_f1",
        "consistency_stub_pass", "consistency_stub_score",
        "ablation_no_gate_mu_sum", "ablation_no_copy_only_mu_sum", "ablation_no_closure_mu_sum",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in scorecard["per_case"]:
            abl = row.get("ablation") or {}
            w.writerow({
                "case_id": row["case_id"],
                "mode": row["mode"],
                "mu_zero": int(bool(row.get("mu_zero"))),
                "mu_sum": row.get("mu_sum", ""),
                "false_patch": row["false_patch"],
                "unsafe_write": row["unsafe_write"],
                "original_broken": row["original_broken"],
                "unapproved_write": row["unapproved_write"],
                "recall_at_3": row["recall_at_3"],
                "cell_f1": row["cell_f1"],
                "field_f1": row.get("field_f1", ""),
                "consistency_stub_pass": (
                    int(bool(row.get("consistency_stub_pass")))
                    if "consistency_stub_pass" in row else ""
                ),
                "consistency_stub_score": row.get("consistency_stub_score", ""),
                "ablation_no_gate_mu_sum": (abl.get("no_gate") or {}).get("mu_sum", ""),
                "ablation_no_copy_only_mu_sum": (abl.get("no_copy_only") or {}).get("mu_sum", ""),
                "ablation_no_closure_mu_sum": (abl.get("no_closure") or {}).get("mu_sum", ""),
            })

    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "mode", "n", "mu_zero_rate", "mean_mu_sum",
            "mean_false_patch", "mean_unsafe_write", "mean_original_broken", "mean_unapproved_write",
            "mean_recall_at_3", "mean_cell_f1", "mean_field_f1", "consistency_stub_pass_rate",
        ])
        w.writeheader()
        for mode, block in scorecard["summary"]["modes"].items():
            w.writerow({"mode": mode, **block})

    return {"json": json_path, "csv": csv_path, "summary_csv": summary_csv}


def run_scorecard(
    *,
    cases_root: Path | None = None,
    out_dir: Path | None = None,
    modes: list[str] | None = None,
) -> dict[str, Any]:
    scorecard = build_scorecard(cases_root=cases_root, modes=modes)
    paths = export_scorecard(scorecard, out_dir=out_dir)
    return {"scorecard": scorecard, "paths": {k: str(v) for k, v in paths.items()}}
