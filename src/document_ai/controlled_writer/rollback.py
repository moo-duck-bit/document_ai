# -*- coding: utf-8 -*-
"""PR-25: Rollback snapshot / restore."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from document_ai.controlled_writer.copy_workspace import file_sha256
from document_ai.controlled_writer.schema import RollbackPoint


def create_rollback_point(
    *,
    rollback_id: str,
    patch_contract_id: str,
    copy_path: str | Path,
    snapshot_dir: str | Path,
) -> RollbackPoint:
    """Snapshot the working copy BEFORE writer mutation."""
    copy = Path(copy_path)
    snap_dir = Path(snapshot_dir)
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{rollback_id}__{copy.name}"
    shutil.copy2(copy, snap_path)
    return RollbackPoint(
        rollback_id=rollback_id,
        patch_contract_id=patch_contract_id,
        copy_path=str(copy.resolve()),
        snapshot_path=str(snap_path.resolve()),
        snapshot_fingerprint=file_sha256(snap_path),
        created_before_write=True,
        rolled_back=False,
        evidence={"note": "pre-write snapshot"},
    )


def rollback_to_point(point: RollbackPoint) -> dict[str, Any]:
    """Restore copy from snapshot after failure."""
    snap = Path(point.snapshot_path)
    copy = Path(point.copy_path)
    if not snap.exists():
        return {
            "ok": False,
            "reason_codes": ["SNAPSHOT_MISSING"],
            "rolled_back": False,
        }
    shutil.copy2(snap, copy)
    point.rolled_back = True
    point.evidence = dict(point.evidence or {})
    point.evidence["restored_fingerprint"] = file_sha256(copy)
    return {
        "ok": True,
        "reason_codes": ["ROLLED_BACK"],
        "rolled_back": True,
        "copy_fingerprint": file_sha256(copy),
        "matches_snapshot": file_sha256(copy) == point.snapshot_fingerprint,
    }
