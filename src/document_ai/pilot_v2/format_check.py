# -*- coding: utf-8 -*-
"""Format-preservation check for pilot writer output (reuse, no reimplementation).

When the gated copy writer produces an output copy, compare it against the
session's pre-write input copy using the same structural/style/table checks
used by the Document Set Benchmark v2. When the writer did not run (blocked
or disabled), format metrics are N/A.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.evaluation.document_set_v2.format_preservation import (
    aggregate_format_metrics,
    compare_format,
)

__all__ = ["compare_format", "aggregate_format_metrics", "check_writer_output"]


def check_writer_output(before: Path | None, after: Path | None) -> dict[str, Any]:
    """Wrap compare_format with pilot-friendly N/A handling."""
    if before is None or after is None:
        return {"status": "N/A", "reason": "writer_not_run"}
    if not Path(before).is_file() or not Path(after).is_file():
        return {"status": "N/A", "reason": "missing_before_or_after"}
    return compare_format(Path(before), Path(after))
