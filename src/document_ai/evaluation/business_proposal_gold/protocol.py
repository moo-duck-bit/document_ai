# -*- coding: utf-8 -*-
"""Draft / review / sealed protocol for Business Proposal node gold.

Mirrors ``document_set_v2.holdout_protocol`` hashing/sealing conventions so
the same auditing story (hash manifest, aggregate hash, static
"prediction code must not read sealed" check) applies to this gold set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.evaluation.document_set_v2.holdout_protocol import (
    _sha256_bytes,
    hash_label_dir,
)

REPO = Path(__file__).resolve().parents[4]
DEFAULT_GOLD_ROOT = (
    REPO / "data" / "eval" / "document_set_benchmark_v2" / "business_proposal_node_gold"
)

DRAFT_FILENAME = "business_proposal_node_gold_draft.jsonl"
REVIEW_FILENAME = "business_proposal_node_gold_review.jsonl"
SEALED_FILENAME = "business_proposal_node_gold_final.jsonl"
MANIFEST_FILENAME = "business_proposal_node_gold_manifest.json"
HASHES_FILENAME = "business_proposal_node_gold_hashes.json"
DISAGREEMENTS_FILENAME = "business_proposal_label_disagreements.json"
SUMMARY_FILENAME = "business_proposal_labeling_summary.json"
AUDIT_FILENAME = "business_proposal_case_label_audit.json"

# Token that must never appear (as a *readable dependency*) in prediction /
# analysis source files: reading sealed BP gold at inference time would leak
# labels into the pipeline being evaluated.
SEALED_TOKEN = "business_proposal_node_gold/sealed"


def gold_dirs(gold_root: Path | None = None) -> dict[str, Path]:
    base = Path(gold_root) if gold_root else DEFAULT_GOLD_ROOT
    return {
        "root": base,
        "draft": base / "draft",
        "review": base / "review",
        "sealed": base / "sealed",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    path.write_text((body + "\n") if rows else "", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_draft(rows: list[dict[str, Any]], *, gold_root: Path | None = None) -> Path:
    dirs = gold_dirs(gold_root)
    path = dirs["draft"] / DRAFT_FILENAME
    write_jsonl(path, rows)
    return path


def write_review(rows: list[dict[str, Any]], *, gold_root: Path | None = None) -> Path:
    dirs = gold_dirs(gold_root)
    path = dirs["review"] / REVIEW_FILENAME
    write_jsonl(path, rows)
    return path


def seal_gold(rows: list[dict[str, Any]], *, gold_root: Path | None = None) -> dict[str, Any]:
    """Write the final sealed gold jsonl + manifest + hash file (Cycle6 gold set,
    distinct from the benchmark-wide holdout seal in ``holdout_protocol``)."""
    dirs = gold_dirs(gold_root)
    sealed_path = dirs["sealed"] / SEALED_FILENAME
    write_jsonl(sealed_path, rows)

    hashes = hash_label_dir(dirs["sealed"])
    manifest = {
        "n_rows": len(rows),
        "sealed_files": sorted(hashes),
        "aggregate_hash": _sha256_bytes(json.dumps(hashes, sort_keys=True).encode("utf-8")),
        "status": "SEALED",
    }
    (dirs["root"] / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dirs["root"] / HASHES_FILENAME).write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def load_sealed_gold(*, gold_root: Path | None = None) -> list[dict[str, Any]]:
    dirs = gold_dirs(gold_root)
    return read_jsonl(dirs["sealed"] / SEALED_FILENAME)


def prediction_code_must_not_read_sealed_bp_gold(paths_checked: list[str]) -> list[str]:
    """Static check: prediction/analysis/adapter code must not reference the
    sealed Business Proposal node gold directory. Returns offending paths."""
    bad: list[str] = []
    for p in paths_checked:
        text = Path(p).read_text(encoding="utf-8")
        normalized = p.replace("\\", "/")
        if SEALED_TOKEN in text and "business_proposal_gold" not in normalized:
            if any(
                marker in normalized
                for marker in (
                    "prediction_adapter",
                    "workflow/analysis",
                    "domain_packs/business_proposal",
                    "document_set/proposal_table_retrieval",
                )
            ):
                bad.append(p)
    return bad
