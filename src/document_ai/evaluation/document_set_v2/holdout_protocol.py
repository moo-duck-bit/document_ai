# -*- coding: utf-8 -*-
"""Blind holdout seal / unseal protocol."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def hash_label_dir(label_dir: Path) -> dict[str, str]:
    """Hash all files under sealed label directory (sorted relative paths)."""
    out: dict[str, str] = {}
    if not label_dir.is_dir():
        return out
    for p in sorted(label_dir.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(label_dir)).replace("\\", "/")
            out[rel] = _sha256_file(p)
    return out


def write_seal_manifest(
    *,
    holdout_dir: Path,
    sealed_labels_dir: Path,
    out_path: Path,
) -> dict[str, Any]:
    hashes = hash_label_dir(sealed_labels_dir)
    payload = {
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "sealed_labels_dir": str(sealed_labels_dir).replace("\\", "/"),
        "holdout_dir": str(holdout_dir).replace("\\", "/"),
        "label_file_hashes": hashes,
        "aggregate_hash": _sha256_bytes(
            json.dumps(hashes, sort_keys=True).encode("utf-8")
        ),
        "status": "SEALED",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_path.parent / "holdout_label_hashes.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def assert_labels_unchanged(seal_manifest: dict[str, Any], sealed_labels_dir: Path) -> list[str]:
    issues: list[str] = []
    current = hash_label_dir(sealed_labels_dir)
    expected = seal_manifest.get("label_file_hashes") or {}
    if current != expected:
        issues.append("label_hash_mismatch")
        for k in sorted(set(current) | set(expected)):
            if current.get(k) != expected.get(k):
                issues.append(f"hash_diff:{k}")
    return issues


def freeze_predictions(
    *,
    prediction_rows: list[dict[str, Any]],
    out_path: Path,
) -> dict[str, Any]:
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in prediction_rows) + "\n"
    digest = _sha256_bytes(body.encode("utf-8"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    manifest = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "prediction_path": str(out_path).replace("\\", "/"),
        "n_rows": len(prediction_rows),
        "sha256": digest,
        "status": "FROZEN",
    }
    man_path = out_path.parent / "prediction_freeze_manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def unseal_for_evaluation(
    *,
    seal_manifest: dict[str, Any],
    prediction_freeze: dict[str, Any],
    sealed_labels_dir: Path,
    out_log_path: Path,
) -> dict[str, Any]:
    """Record unseal after predictions are frozen. Does not mutate labels."""
    issues = assert_labels_unchanged(seal_manifest, sealed_labels_dir)
    sealed_at = seal_manifest.get("sealed_at") or ""
    frozen_at = prediction_freeze.get("frozen_at") or ""
    unsealed_at = datetime.now(timezone.utc).isoformat()
    # Protocol: seal before freeze; unseal after freeze
    protocol_ok = True
    if sealed_at and frozen_at and sealed_at > frozen_at:
        issues.append("prediction_before_seal")
        protocol_ok = False
    if not prediction_freeze.get("sha256"):
        issues.append("missing_prediction_freeze_hash")
        protocol_ok = False
    log = {
        "unsealed_at": unsealed_at,
        "sealed_at": sealed_at,
        "prediction_frozen_at": frozen_at,
        "protocol_ok": protocol_ok and not issues,
        "issues": issues,
        "status": "UNSEALED" if protocol_ok and not issues else "PROTOCOL_VIOLATION",
    }
    out_log_path.parent.mkdir(parents=True, exist_ok=True)
    out_log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return log


def prediction_code_must_not_read_sealed(paths_checked: list[str], sealed_token: str = "sealed_labels") -> list[str]:
    """Static check helper: return paths that mention sealed_labels incorrectly."""
    bad: list[str] = []
    for p in paths_checked:
        text = Path(p).read_text(encoding="utf-8")
        # prediction adapter / workflow analysis must not load sealed gold
        if sealed_token in text and "holdout_protocol" not in p.replace("\\", "/"):
            if "prediction_adapter" in p.replace("\\", "/") or "workflow/analysis" in p.replace("\\", "/"):
                bad.append(p)
    return bad
