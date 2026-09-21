"""Case runner for Small-A regulatory_bench."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .case_loader import load_case
from .scorer import score_case


def build_demo_safe_artifacts(case: dict[str, Any]) -> dict[str, Any]:
    """Synthesize perfect-contract artifacts from gold (μ=0 smoke path)."""
    gold = case["gold"] if isinstance(case, dict) and "gold" in case else case
    expected_patches = (gold.get("expected_patch") or {}).get("patches") or []
    writable = [str(p.get("node_id") or p.get("id")) for p in expected_patches]

    doc_impacts = []
    for d in gold.get("document_impacts") or []:
        status = str(d.get("gold_status") or d.get("status") or "")
        if status.upper() != "NO_IMPACT":
            doc_impacts.append(
                {
                    "doc_id": d.get("doc_id") or d.get("document_id"),
                    "document_id": d.get("document_id") or d.get("doc_id"),
                    "status": status,
                }
            )

    before = {}
    for of in gold.get("original_files") or []:
        path = of.get("path")
        if path:
            before[path] = "0" * 64

    return {
        "mode": "demo_safe",
        "predicted_impact_nodes": list(gold.get("impact_nodes") or []),
        "predicted_document_impacts": doc_impacts,
        "writable_scope": writable,
        "patch_diff": [dict(p) for p in expected_patches],
        "approval_log": {
            "approved": True,
            "approver": "demo_safe",
            "status": "APPROVED",
            "note": "synthetic approval for μ=0 smoke",
        },
        "wrote_original": False,
        "bypass_activation": False,
        "fingerprints": {
            "before": dict(before),
            "after_originals": dict(before),
        },
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_case(
    case_dir: Path | str,
    *,
    mode: str = "demo_safe",
    artifacts_path: Path | str | None = None,
    out_dir: Path | str | None = None,
    recall_k: int = 3,
    approve: bool = True,
) -> dict[str, Any]:
    """
    Run one case.

    modes:
      - demo_safe: build artifacts from gold (μ=0 expected)
      - artifact_only: score existing artifacts.json
      - materialize: write synthetic MDSR/MDDR + fingerprints, then demo_safe score
      - pipeline: copy-only gated write dump → artifacts.json → score
      - live: compute_impact (live) + copy-only gated writes → score
    """
    case = load_case(case_dir)
    root = Path(case["case_dir"])
    out = Path(out_dir) if out_dir else (root / "runs" / "latest")
    out.mkdir(parents=True, exist_ok=True)

    if mode in {"materialize", "materialise"}:
        from .materialize import materialize_case

        manifest = materialize_case(root, force=True)
        # reload after fingerprints update
        case = load_case(root)
        artifacts = build_demo_safe_artifacts(case)
        # Prefer real fingerprints after materialize.
        fp_before = {rel: digest for rel, digest in (manifest.get("sha256") or {}).items()}
        if fp_before:
            artifacts["fingerprints"] = {
                "before": dict(fp_before),
                "after_originals": dict(fp_before),
            }
        artifacts["materialize_manifest"] = manifest
        art_path = out / "artifacts.json"
        _write_json(art_path, artifacts)
    elif mode in {"pipeline", "pipeline_dump"}:
        from .pipeline import run_pipeline_case

        artifacts = run_pipeline_case(
            root,
            out_dir=out,
            approve=approve,
            materialize_if_missing=True,
            use_gold_patches=True,
        )
        art_path = out / "artifacts.json"
        case = load_case(root)
    elif mode in {"live", "live_pipeline"}:
        from .live import run_live_case

        artifacts = run_live_case(
            root,
            out_dir=out,
            approve=approve,
            materialize_if_missing=True,
            use_gold_patch_values=False,
        )
        art_path = out / "artifacts.json"
        case = load_case(root)
    elif mode in {"demo_safe", "demo-safe", "oracle"}:
        artifacts = build_demo_safe_artifacts(case)
        art_path = out / "artifacts.json"
        _write_json(art_path, artifacts)
    elif mode in {"artifact_only", "artifacts", "score_only", "score-only"}:
        src = Path(artifacts_path) if artifacts_path else (out / "artifacts.json")
        if not src.exists():
            alt = root / "runs" / "latest" / "artifacts.json"
            if alt.exists():
                src = alt
            else:
                raise FileNotFoundError(f"artifacts not found: {src}")
        artifacts = json.loads(src.read_text(encoding="utf-8"))
        art_path = out / "artifacts.json"
        if src.resolve() != art_path.resolve():
            _write_json(art_path, artifacts)
    else:
        raise ValueError(
            f"unsupported mode: {mode} (use demo_safe|artifact_only|materialize|pipeline|live)"
        )

    score = score_case(case, artifacts, recall_k=recall_k)
    score_payload = {
        "case_id": case["case_id"],
        "mode": mode,
        "primary": score["primary"],
        "secondary": score["secondary"],
        "mu_zero": score["mu_zero"],
        "mu": score["mu"],
    }
    score_path = out / "score.json"
    _write_json(score_path, score_payload)

    return {
        "case_id": case["case_id"],
        "mode": mode,
        "out_dir": str(out),
        "artifacts_path": str(art_path),
        "score_path": str(score_path),
        "score": score_payload,
        "mu_zero": score["mu_zero"],
        "primary": score["primary"],
        "secondary": score["secondary"],
    }
