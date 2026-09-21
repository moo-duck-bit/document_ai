"""Load Small-A regulatory_bench cases from disk.

On-disk layout (case_000):
  meta.json
  input/change_request.txt
  gold/impact_nodes.json
  gold/expected_patch.json
  gold/must_not_touch.json
  fp/originals.sha256
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(case_dir: Path, rel: str | None) -> Path | None:
    if not rel:
        return None
    return case_dir / rel


def load_case(case_dir: Path | str) -> dict[str, Any]:
    """Load case pack into a unified dict for scoring/running."""
    root = Path(case_dir)
    meta_path = root / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"missing meta.json under {root}")

    meta = _read_json(meta_path)
    gold_refs = meta.get("gold") or {}

    impact_path = _resolve(root, gold_refs.get("impact_nodes")) or (root / "gold" / "impact_nodes.json")
    patch_path = _resolve(root, gold_refs.get("expected_patch")) or (root / "gold" / "expected_patch.json")
    untouched_path = _resolve(root, gold_refs.get("must_not_touch")) or (root / "gold" / "must_not_touch.json")

    for p, label in (
        (impact_path, "impact_nodes"),
        (patch_path, "expected_patch"),
        (untouched_path, "must_not_touch"),
    ):
        if not p.exists():
            raise FileNotFoundError(f"case {root} missing gold/{label}: {p}")

    impact = _read_json(impact_path)
    expected_patch = _read_json(patch_path)
    must_not_touch = _read_json(untouched_path)

    cr_rel = (meta.get("change_request") or {}).get("path") or "input/change_request.txt"
    cr_path = root / cr_rel
    change_request_text = cr_path.read_text(encoding="utf-8") if cr_path.exists() else ""

    fp_rel = (meta.get("fingerprints") or {}).get("path") or "fp/originals.sha256"
    fp_path = root / fp_rel
    fingerprints_raw = fp_path.read_text(encoding="utf-8") if fp_path.exists() else ""

    impact_nodes = impact.get("impact_nodes") or []
    # Normalize to id list for set ops; keep objects for detail.
    impact_node_ids = [
        str(n.get("node_id") if isinstance(n, dict) else n) for n in impact_nodes
    ]
    document_impacts = impact.get("document_impacts") or []
    # Prefer document_id key used in gold files.
    for d in document_impacts:
        if "doc_id" not in d and "document_id" in d:
            d["doc_id"] = d["document_id"]

    patches = expected_patch.get("patches") or []
    must_match_exactly = [
        str(p["node_id"]) for p in patches if p.get("must_match_exactly") and p.get("node_id")
    ]
    accept_regex = [
        {"node_id": str(p["node_id"]), "pattern": str(p["accept_regex"])}
        for p in patches
        if p.get("accept_regex") and p.get("node_id")
    ]
    # Scorer uses new_value / after interchangeably.
    normalized_patches = []
    for p in patches:
        item = dict(p)
        if "new_value" not in item and "after" in item:
            item["new_value"] = item["after"]
        if "value" not in item and "after" in item:
            item["value"] = item["after"]
        normalized_patches.append(item)

    untouched_raw = must_not_touch.get("untouched_nodes") or []
    untouched_ids = [
        str(n.get("node_id") if isinstance(n, dict) else n) for n in untouched_raw
    ]
    writer_expectations = must_not_touch.get("writer_expectations") or {}
    # Merge meta safety_contract flags if present.
    safety = meta.get("safety_contract") or {}
    if "requires_human_approval" not in writer_expectations and "requires_human_approval" in safety:
        writer_expectations = {**writer_expectations, "requires_human_approval": safety["requires_human_approval"]}

    gold = {
        "impact_nodes": impact_node_ids,
        "impact_node_objects": impact_nodes,
        "document_impacts": document_impacts,
        "expected_patch": {"patches": normalized_patches},
        "must_match_exactly": must_match_exactly,
        "accept_regex": accept_regex,
        "untouched_nodes": untouched_ids,
        "untouched_node_objects": untouched_raw,
        "writer_expectations": writer_expectations,
        "original_files": must_not_touch.get("original_files") or [],
        "mu_mapping": must_not_touch.get("mu_mapping") or {},
    }

    return {
        "case_dir": str(root.resolve()),
        "case_id": meta.get("case_id") or root.name,
        "meta": meta,
        "change_request_text": change_request_text,
        "change_request_path": str(cr_path) if cr_path.exists() else None,
        "gold": gold,
        "gold_impact": impact,
        "gold_patch": expected_patch,
        "gold_must_not_touch": must_not_touch,
        "fingerprints_path": str(fp_path) if fp_path.exists() else None,
        "fingerprints_raw": fingerprints_raw,
    }
