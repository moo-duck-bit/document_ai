# -*- coding: utf-8 -*-
"""PR-25: Copy workspace — never mutate originals."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_copy(
    source_path: str | Path,
    copy_dir: str | Path,
    *,
    stem_suffix: str = "_copy",
) -> dict[str, Any]:
    """Create a working copy. Never overwrite source. Refuse if source missing."""
    src = Path(source_path)
    out_dir = Path(copy_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src.exists() or not src.is_file():
        return {
            "ok": False,
            "source_path": str(src),
            "copy_path": None,
            "source_fingerprint": None,
            "reason_codes": ["SOURCE_MISSING"],
        }

    source_fp = file_sha256(src)
    copy_name = f"{src.stem}{stem_suffix}{src.suffix}"
    copy_path = out_dir / copy_name
    # unique if exists
    if copy_path.exists():
        for i in range(1, 1000):
            cand = out_dir / f"{src.stem}{stem_suffix}_{i:03d}{src.suffix}"
            if not cand.exists():
                copy_path = cand
                break

    shutil.copy2(src, copy_path)
    copy_fp = file_sha256(copy_path)

    # Verify source unchanged after copy
    source_fp_after = file_sha256(src)
    if source_fp != source_fp_after:
        return {
            "ok": False,
            "source_path": str(src),
            "copy_path": str(copy_path),
            "source_fingerprint": source_fp,
            "reason_codes": ["SOURCE_CHANGED_DURING_COPY"],
        }

    return {
        "ok": True,
        "source_path": str(src.resolve()),
        "copy_path": str(copy_path.resolve()),
        "source_fingerprint": source_fp,
        "copy_fingerprint": copy_fp,
        "reason_codes": ["COPY_CREATED"],
        "original_unchanged": True,
    }


def verify_original_unchanged(source_path: str | Path, expected_fp: str) -> bool:
    src = Path(source_path)
    if not src.exists():
        return False
    return file_sha256(src) == expected_fp
