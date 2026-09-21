# -*- coding: utf-8 -*-
"""Document Set Benchmark v2 schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SplitName = Literal["regression", "development", "holdout"]
DomainName = Literal["ec_sw", "general_report", "business_proposal"]
SourceType = Literal["GENERATED", "SANITIZED_REAL", "TEMPLATE_DERIVED", "STRUCTURE_PERTURBED", "fixture"]


@dataclass
class BenchmarkV2Case:
    case_id: str
    domain: str
    document_set_id: str
    change_request: str
    split: str
    input_documents: list[dict[str, Any]]
    enabled_documents: list[str] = field(default_factory=list)
    expected_status: str = "SUCCESS"
    tags: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    notes: str = ""
    source_type: str = "GENERATED"
    transformation: str | None = None
    base_case_id: str | None = None
    source_document_id: str | None = None
    sanitization_status: str | None = None
    source_fingerprint: str | None = None
    fixture_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ALLOWED_DOMAINS = frozenset({"ec_sw", "general_report", "business_proposal"})
ALLOWED_SPLITS = frozenset({"regression", "development", "holdout"})
