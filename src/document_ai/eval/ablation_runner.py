"""Ablation runner for Document-TNR variants (paper RQ3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.document_set.dependency_graph import expand_patch_candidates_with_closure
from document_ai.eval.field_f1 import compute_field_f1
from document_ai.orchestrator.document_agent import run_document_agent
from document_ai.safety.document_tnr import (
    ablation_flags,
    assess_scorecard,
    assess_severity,
    map_safety_scorecard_to_mu,
)

ABLATION_VARIANTS = ("full", "no_gate", "no_closure", "no_copy_only")


def _req_ids_from_change(change: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("changed_requirements", "req_ids"):
        for item in change.get(key) or []:
            if isinstance(item, str) and item.strip():
                ids.add(item.strip())
    for row in change.get("requirement_changes") or []:
        rid = row.get("req_id")
        if rid:
            ids.add(str(rid).strip())
    intake = change.get("intake") or {}
    for rid in intake.get("parsed_req_ids") or []:
        if rid:
            ids.add(str(rid).strip())
    return ids


def _find_change_files(case_dir: Path) -> list[Path]:
    changes_dir = case_dir / "changes"
    if not changes_dir.exists():
        return []
    preferred = [
        changes_dir / "req_change.json",
        changes_dir / "req6_update.json",
    ]
    found: list[Path] = []
    for path in preferred:
        if path.exists():
            found.append(path)
    for path in sorted(changes_dir.glob("*.json")):
        if path not in found:
            found.append(path)
    return found


def run_closure_ablation(
    case_dir: Path,
    candidate_ids: set[str],
) -> dict[str, Any]:
    """Compare patch sets with and without C1 closure."""
    req_path = case_dir / "requirements.json"
    design_path = case_dir / "design_items.json"
    if not req_path.exists():
        return {"error": "missing requirements.json"}
    req_payload = json.loads(req_path.read_text(encoding="utf-8"))
    design_payload = (
        json.loads(design_path.read_text(encoding="utf-8")) if design_path.exists() else None
    )
    with_closure = expand_patch_candidates_with_closure(
        candidate_ids, req_payload, design_payload, apply_closure=True
    )
    without_closure = expand_patch_candidates_with_closure(
        candidate_ids, req_payload, design_payload, apply_closure=False
    )
    return {
        "case_dir": str(case_dir),
        "with_closure": with_closure,
        "without_closure": without_closure,
        "closure_delta": len(with_closure["expanded"]) - len(without_closure["expanded"]),
    }


def run_ablation_suite(
    case_dir: Path | str,
    *,
    mode: str = "new",
    golden_path: Path | None = None,
    change: Path | None = None,
    scorecard_path: Path | None = None,
) -> dict[str, Any]:
    """Run all ablation variants and collect TNR + Field F1 / impact signals."""
    case_dir = Path(case_dir).resolve()
    results: dict[str, Any] = {"case_dir": str(case_dir), "mode": mode, "variants": {}}

    change_path = Path(change).resolve() if change else None
    if mode == "change" and change_path is None:
        files = _find_change_files(case_dir)
        change_path = files[0] if files else None

    for variant in ABLATION_VARIANTS:
        spec = ablation_flags(variant)
        entry: dict[str, Any] = {"tnr_spec": spec.to_dict()}

        if mode == "new":
            out = run_document_agent(case_dir, mode="new", ablation_variant=variant)
            entry["harness_ok"] = out.get("result", {}).get("ok")
            f1 = compute_field_f1(case_dir=case_dir, golden_path=golden_path)
            entry["field_f1"] = f1.get("field_f1")
            entry["field_matched"] = f1.get("matched_count")
            entry["field_count"] = f1.get("field_count")
        else:
            if change_path is None:
                entry["error"] = "no change JSON found"
            else:
                out = run_document_agent(
                    case_dir,
                    mode="change",
                    change=change_path,
                    ablation_variant=variant,
                )
                report = out.get("result") or {}
                entry["impact_mode"] = report.get("mode")
                entry["change_id"] = report.get("change_id")
                entry["pipeline_agents"] = [
                    step.get("agent_id") for step in (report.get("pipeline") or []) if isinstance(step, dict)
                ]
                entry["pipeline_ok"] = all(
                    step.get("status") == "ok" for step in (report.get("pipeline") or []) if isinstance(step, dict)
                )

        # Synthetic μ for variant (what would be allowed — for reporting only)
        mu = {
            "false_patch": 0,
            "unsafe_write": 1 if variant == "no_gate" else 0,
            "original_broken": 1 if variant == "no_copy_only" else 0,
            "unapproved_write": 1 if variant == "no_gate" else 0,
        }
        entry["simulated_mu"] = mu
        entry["simulated_tnr"] = assess_severity(mu, baseline_ok=variant != "no_copy_only")
        results["variants"][variant] = entry

    # Closure ablation from any available change file
    for path in ([change_path] if change_path else _find_change_files(case_dir)):
        if path is None or not path.exists():
            continue
        ch = json.loads(path.read_text(encoding="utf-8"))
        req_ids = _req_ids_from_change(ch)
        if req_ids:
            results["closure_ablation"] = run_closure_ablation(case_dir, req_ids)
            results["closure_ablation"]["change_path"] = str(path)
            results["closure_ablation"]["req_ids"] = sorted(req_ids)
            break

    if scorecard_path:
        results["observed_tnr"] = tnr_from_scorecard_file(Path(scorecard_path))

    return results


def load_safety_scorecard(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def tnr_from_scorecard_file(path: Path) -> dict[str, Any]:
    sc = load_safety_scorecard(path)
    result = assess_scorecard(sc)
    result["scorecard_path"] = str(path)
    return result


def evaluate_tnr_scorecards(paths: list[Path] | Path) -> dict[str, Any]:
    """Assess one or more safety scorecards (pilot or holdout benchmark)."""
    if isinstance(paths, Path):
        path = Path(paths)
        if path.is_dir():
            files = sorted(path.rglob("*scorecard*.json"))
            if not files:
                files = sorted(path.rglob("safety_scorecard.json"))
        else:
            files = [path]
    else:
        files = [Path(p) for p in paths]

    assessments = [tnr_from_scorecard_file(p) for p in files]
    satisfied = sum(1 for a in assessments if a.get("tnr_satisfied"))
    return {
        "scorecard_count": len(assessments),
        "tnr_satisfied_count": satisfied,
        "tnr_rate": round(satisfied / len(assessments), 4) if assessments else 0.0,
        "assessments": assessments,
    }
