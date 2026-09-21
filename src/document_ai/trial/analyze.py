"""trial-analyze: diff + metrics + presentation data stubs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.trial.diff import diff_trial_documents
from document_ai.trial.metrics import aggregate_human_ratings, time_saving_rate
from document_ai.trial.models import empty_error_annotation
from document_ai.trial.paths import load_manifest, read_json, rel_to_project, save_manifest, trial_dir, write_json


def _load_human_record(path: Path) -> dict[str, Any] | None:
    for candidate in (
        path / "human_revision_record.json",
        path / "review" / "human_revision_record.json",
    ):
        if candidate.exists():
            return read_json(candidate)
    return None


def _load_error_annotations(path: Path) -> list[dict[str, Any]]:
    for candidate in (
        path / "error_annotations.json",
        path / "review" / "error_annotations.json",
    ):
        if candidate.exists():
            data = read_json(candidate)
            if isinstance(data, list):
                return data
            return list(data.get("annotations") or [])
    return []


def analyze_trial(trial: str | Path) -> dict[str, Any]:
    path = trial_dir(trial)
    manifest = load_manifest(path)
    document_types = list(manifest.get("document_types") or ["MDSR", "MDDR"])

    diff = diff_trial_documents(
        generated_dir=path / "generated",
        revised_dir=path / "human_revised",
        document_types=document_types,
        out_dir=path / "diff",
    )

    human = _load_human_record(path)
    annotations = _load_error_annotations(path)
    auto_candidates = list(diff.get("error_candidates") or [])

    # Merge: human annotations preferred; auto remain unverified
    merged_annotations: list[dict[str, Any]] = []
    for item in annotations:
        row = empty_error_annotation(
            document_type=str(item.get("document_type") or ""),
            error_type=str(item.get("error_type") or "MISSING_CONTENT"),
            verified=bool(item.get("verified", True)),
        )
        row.update(item)
        if "verified" not in item:
            row["verified"] = True
            row["source"] = "human"
        merged_annotations.append(row)

    if not annotations:
        for item in auto_candidates:
            item = dict(item)
            item["verified"] = False
            item["source"] = "auto_candidate"
            merged_annotations.append(item)

    write_json(
        path / "error_annotations.json",
        {
            "trial_id": manifest.get("trial_id"),
            "annotations": merged_annotations,
            "unverified_count": sum(1 for a in merged_annotations if not a.get("verified")),
            "verified_count": sum(1 for a in merged_annotations if a.get("verified")),
        },
    )

    generation = {}
    gen_path = path / "generation_manifest.json"
    if gen_path.exists():
        generation = read_json(gen_path)

    gen_minutes = None
    if generation.get("duration_minutes") is not None:
        gen_minutes = generation.get("duration_minutes")
    if human and human.get("harness_generation_minutes") is not None:
        gen_minutes = human.get("harness_generation_minutes")

    time_metrics = time_saving_rate(
        manual_baseline_minutes=(human or {}).get("manual_baseline_minutes"),
        generation_minutes=gen_minutes,
        revision_minutes=(human or {}).get("human_revision_minutes"),
    )

    ratings = aggregate_human_ratings((human or {}).get("document_reviews") or [])

    auto_metrics = {
        "quality": (generation.get("quality") or {}),
        "validation": (generation.get("validation") or {}),
        "diff": {
            doc: {
                "unchanged_paragraph_ratio": (meta.get("unchanged_paragraph_ratio")),
                "modified_paragraph_ratio": meta.get("modified_paragraph_ratio"),
                "added_paragraph_ratio": meta.get("added_paragraph_ratio"),
                "deleted_paragraph_ratio": meta.get("deleted_paragraph_ratio"),
                "unchanged_table_cell_ratio": meta.get("unchanged_table_cell_ratio"),
                "modified_table_cell_ratio": meta.get("modified_table_cell_ratio"),
                "document_level_edit_burden_score": meta.get("document_level_edit_burden_score"),
                "status": meta.get("status"),
            }
            for doc, meta in (diff.get("documents") or {}).items()
        },
    }

    # Traceability proxy from validation scores if present
    val_scores = ((generation.get("validation") or {}).get("scores") or {})
    auto_metrics["traceability"] = {
        "validation_overall": val_scores.get("overall"),
        "mdsr": val_scores.get("mdsr"),
        "mddr": val_scores.get("mddr"),
        "xxcs": val_scores.get("xxcs"),
    }

    error_counts: dict[str, int] = {}
    for ann in merged_annotations:
        key = str(ann.get("error_type") or "UNKNOWN")
        error_counts[key] = error_counts.get(key, 0) + 1

    readiness = {
        "usable_without_change": [],
        "internal_review_ready": [],
        "external_delivery_ready": [],
    }
    for review in (human or {}).get("document_reviews") or []:
        dt = review.get("document_type")
        if review.get("usable_without_change"):
            readiness["usable_without_change"].append(dt)
        if review.get("internal_review_ready"):
            readiness["internal_review_ready"].append(dt)
        if review.get("external_delivery_ready"):
            readiness["external_delivery_ready"].append(dt)

    metrics = {
        "trial_id": manifest.get("trial_id"),
        "system_version": manifest.get("system_version"),
        "synthetic": bool(manifest.get("synthetic")),
        "auto": auto_metrics,
        "human_ratings": ratings,
        "time": time_metrics,
        "error_counts": error_counts,
        "readiness": readiness,
        "human_record_present": human is not None,
        "revision_docs_present": any(
            (path / "human_revised").glob("*.docx")
        ),
        "real_world_trial_complete": False,
    }
    # Real completion requires non-synthetic + human record + revised docs
    if (
        not manifest.get("synthetic")
        and human is not None
        and metrics["revision_docs_present"]
        and ratings.get("overall") is not None
    ):
        metrics["real_world_trial_complete"] = True
        manifest["status"] = "reviewed"
    elif metrics["revision_docs_present"] or human is not None:
        manifest["status"] = "reviewed" if not manifest.get("synthetic") else manifest.get("status")

    write_json(path / "metrics.json", metrics)
    write_json(path / "metrics" / "metrics.json", metrics)

    # Presentation figure data
    figures = path / "reports" / "figures" / "data"
    write_json(figures / "error_distribution.json", error_counts)
    write_json(figures / "edit_ratio.json", auto_metrics["diff"])
    write_json(figures / "time_comparison.json", time_metrics)
    write_json(figures / "traceability.json", auto_metrics["traceability"])
    write_json(
        figures / "score_comparison.json",
        {
            "baseline": manifest.get("baseline_metrics_snapshot"),
            "trial_quality": (generation.get("quality") or {}).get("scores"),
            "trial_validation": (generation.get("validation") or {}).get("scores"),
            "human_overall": ratings.get("overall"),
        },
    )

    if manifest.get("status") == "review_pending" and metrics["revision_docs_present"]:
        manifest["status"] = "reviewed"
    save_manifest(path, manifest)

    return {
        "ok": True,
        "trial_dir": rel_to_project(path),
        "metrics": metrics,
        "diff_documents": list((diff.get("documents") or {}).keys()),
        "annotation_count": len(merged_annotations),
    }
