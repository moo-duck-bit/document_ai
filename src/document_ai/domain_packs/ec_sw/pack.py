# -*- coding: utf-8 -*-
"""EC-SW Domain Pack implementation."""

from __future__ import annotations

from typing import Any

from document_ai.document_set.domain_pack import DomainPack
from document_ai.document_set.schema import DocumentDescriptor, DocumentNode
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document


class EcSwDomainPack(DomainPack):
    pack_id = "ec_sw_v1"
    supported_document_types = frozenset(
        {"MDSR", "MDDR", "XXCS", "MDTM", "MDVP", "MDDP", "MDCP", "MDMP"}
    )
    supported_short_ids = frozenset(
        {
            "spec_mdsr",
            "spec_mddr",
            "report_xxcs",
            "matrix_mdtm",
            "plan_mdvp",
            "plan_mddp",
            "process_mdcp",
            "process_mdmp",
        }
    )
    # Sprint activation: only MDTM indexes via this pack
    active_index_short_ids = frozenset({"matrix_mdtm"})

    def can_handle(self, descriptor: DocumentDescriptor) -> bool:
        return (
            descriptor.short_id in self.supported_short_ids
            or descriptor.document_type in self.supported_document_types
        )

    def index_document(self, descriptor: DocumentDescriptor) -> list[DocumentNode]:
        if descriptor.short_id not in self.active_index_short_ids:
            return []
        result = index_mdtm_document(descriptor)
        return list(result.get("nodes") or [])

    def locator_hints(self, descriptor: DocumentDescriptor) -> dict[str, Any]:
        if descriptor.short_id == "matrix_mdtm":
            return {
                "strategies": ["table_row", "identifier_cells"],
                "preferred_node_type": "TABLE_ROW",
                "identifier_keys": ["requirement_ids", "design_ids", "test_ids"],
            }
        return {"strategies": [], "status": "future_support"}

    def operation_policy(self, descriptor: DocumentDescriptor) -> dict[str, Any]:
        base = super().operation_policy(descriptor)
        if descriptor.short_id == "matrix_mdtm":
            base.update(
                {
                    "allowed_operations": ["UPDATE"],
                    "forbidden_operations": [
                        "ADD_ROW",
                        "GENERATE_ID",
                        "ROW_WIDE_REPLACE",
                        "MERGE_CELL_EDIT",
                        "APPEND_DOCUMENT",
                    ],
                    "auto_write_default": False,
                }
            )
        return base
