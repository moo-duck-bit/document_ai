# -*- coding: utf-8 -*-
"""EC-SW pack validation helpers."""

from __future__ import annotations

from typing import Any

from document_ai.document_set.schema import DocumentNode
from document_ai.document_set.validation import validate_nodes


def validate_mdtm_index_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nodes: list[DocumentNode] = list(payload.get("nodes") or [])
    base = validate_nodes(nodes, document_id="MDTM")
    issues = list(base.get("issues") or [])
    for n in nodes:
        loc = n.source_locator or {}
        if "table_index" not in loc or "row_index" not in loc:
            issues.append(f"missing_locator:{n.node_id}")
        if n.node_type != "TABLE_ROW":
            issues.append(f"unexpected_node_type:{n.node_id}")
    return {**base, "ok": not issues, "issues": issues}
