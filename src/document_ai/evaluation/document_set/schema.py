# -*- coding: utf-8 -*-
"""Benchmark schemas and status maps."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DocGoldStatus = Literal["IMPACTED", "REVIEW_REQUIRED", "UNRELATED"]
NodeGoldStatus = Literal["PATCH_CANDIDATE", "REVIEW_REQUIRED", "UNRELATED", "INVALID"]
E2EStatus = Literal["SUCCESS", "PARTIAL", "SAFE_FAILURE", "UNSAFE_FAILURE", "INVALID"]

STATUS_MAP = {
    "PATCH_CANDIDATE": "PATCH_CANDIDATE",
    "REVIEW_REQUIRED": "REVIEW_REQUIRED",
    "UNRELATED": "UNRELATED",
    "INVALID": "INVALID",
    "IMPACTED": "IMPACTED",
}


@dataclass
class BenchmarkCase:
    case_id: str
    domain: str
    document_set_id: str
    change_request: str
    input_documents: list[dict[str, Any]]
    enabled_documents: list[str] = field(default_factory=list)
    expected_status: str = "SUCCESS"
    tags: list[str] = field(default_factory=list)
    difficulty: str = "easy"
    notes: str = ""
    source_type: str = "fixture"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
