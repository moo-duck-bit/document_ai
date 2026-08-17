from __future__ import annotations

import re
from typing import Any

from document_ai.learn.req_ids import (
    normalize_requirement_id,
    parse_linked_ids,
    parse_requirement_ids_from_text,
    requirement_sort_key,
)

# Backward-compatible alias (EC-SW Req. N)
normalize_req_id = normalize_requirement_id
parse_linked_reqs = parse_linked_ids

SECURITY_ID_PATTERN = re.compile(r"^([A-Z]{2})-(\d+)$")
XXCS_TEST_PREFIXES = ("IA-", "UC-", "SI-")
TEST_CASE_PREFIX = "TC-"


def _security_sort_key(security_id: str) -> tuple[str, int]:
    normalized = normalize_requirement_id(security_id) or security_id
    match = SECURITY_ID_PATTERN.match(normalized)
    if not match:
        return (normalized, 0)
    return (match.group(1), int(match.group(2)))


def _downstream_sort_key(item_id: str) -> tuple[str, int]:
    if item_id.upper().startswith(TEST_CASE_PREFIX):
        return _test_sort_key(item_id)
    return _security_sort_key(item_id)


def _test_sort_key(test_id: str) -> tuple[str, int]:
    match = re.match(r"^TC-(\d+)$", test_id, re.IGNORECASE)
    if not match:
        return (test_id, 0)
    return ("TC", int(match.group(1)))


def xxcs_test_ids(security_ids: list[str]) -> list[str]:
    return sorted(
        [sid for sid in security_ids if sid.startswith(XXCS_TEST_PREFIXES)],
        key=_security_sort_key,
    )


def linked_test_case_ids(linked_ids: list[str]) -> list[str]:
    return sorted(
        [item for item in linked_ids if item.upper().startswith(TEST_CASE_PREFIX)],
        key=_test_sort_key,
    )


class TraceabilityGraph:
    """Bidirectional index over traceability rows (EC-SW IA↔Req or SRS Req↔TC)."""

    def __init__(self, traceability: list[dict[str, Any]]) -> None:
        self.downstream_to_reqs: dict[str, set[str]] = {}
        self.req_to_downstream: dict[str, set[str]] = {}

        for row in traceability:
            upstream = normalize_requirement_id(row.get("requirement", "")) or row.get("requirement", "").strip()
            if not upstream:
                continue
            linked = parse_linked_ids(row.get("linked_reqs", ""))
            self.downstream_to_reqs.setdefault(upstream, set()).update(linked)
            for req_id in linked:
                self.req_to_downstream.setdefault(req_id, set()).add(upstream)

        # Legacy attribute names used in tests
        self.security_to_reqs = self.downstream_to_reqs
        self.req_to_security = self.req_to_downstream

    def downstream_for_req(self, req_id: str) -> list[str]:
        normalized = normalize_requirement_id(req_id)
        if not normalized:
            return []
        combined = set(self.req_to_downstream.get(normalized, set()))
        combined.update(self.downstream_to_reqs.get(normalized, set()))
        return sorted(combined, key=_downstream_sort_key)

    def security_for_req(self, req_id: str) -> list[str]:
        return self.downstream_for_req(req_id)

    def downstream_for_reqs(self, req_ids: list[str]) -> list[str]:
        combined: set[str] = set()
        for req_id in req_ids:
            combined.update(self.downstream_for_req(req_id))
        return sorted(combined, key=_downstream_sort_key)

    def security_for_reqs(self, req_ids: list[str]) -> list[str]:
        return self.downstream_for_reqs(req_ids)

    def impact(self, req_ids: list[str], design_index: Any | None = None) -> dict[str, Any]:
        normalized = [normalize_requirement_id(r) for r in req_ids]
        normalized = [r for r in normalized if r]
        linked_ids = self.downstream_for_reqs(normalized)
        xxcs_ids = xxcs_test_ids(linked_ids)
        test_ids = linked_test_case_ids(linked_ids)

        mddr_req_ids: list[str] = []
        mddr_reason = "MDDR / design blocks not indexed"
        if design_index is not None:
            mddr_req_ids = design_index.req_ids_for(normalized)
            if mddr_req_ids:
                mddr_reason = ""

        is_srs = any(r.startswith(("FR-", "NFR-")) for r in normalized)

        return {
            "changed_req_ids": normalized,
            "linked_downstream_ids": linked_ids,
            "linked_security_ids": linked_ids,
            "linked_test_ids": test_ids,
            "document_set_hint": "ieee_srs" if is_srs else "ec_sw",
            "documents": {
                "spec_requirements": {
                    "action": "patch",
                    "req_ids": normalized,
                },
                "spec_design": {
                    "action": "patch" if mddr_req_ids else "skip",
                    "req_ids": mddr_req_ids,
                    "reason": mddr_reason,
                },
                "report_security_verification": {
                    "action": "patch" if xxcs_ids else "skip",
                    "security_req_ids": xxcs_ids,
                },
                "test_cases": {
                    "action": "review" if test_ids else "skip",
                    "test_ids": test_ids,
                    "reason": "SRS RTM — update linked test cases (TC-xx) manually or via test spec DOCX when available",
                },
            },
        }
