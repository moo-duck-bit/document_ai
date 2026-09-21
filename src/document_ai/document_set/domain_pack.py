# -*- coding: utf-8 -*-
"""DomainPack interface and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from document_ai.document_set.schema import DocumentDescriptor, DocumentNode


class DomainPack(ABC):
    pack_id: str
    supported_document_types: frozenset[str]
    supported_short_ids: frozenset[str]

    @abstractmethod
    def can_handle(self, descriptor: DocumentDescriptor) -> bool:
        ...

    @abstractmethod
    def index_document(self, descriptor: DocumentDescriptor) -> list[DocumentNode]:
        ...

    def locator_hints(self, descriptor: DocumentDescriptor) -> dict[str, Any]:
        return {}

    def validate_nodes(self, nodes: list[DocumentNode]) -> dict[str, Any]:
        node_ids = [n.node_id for n in nodes]
        return {
            "ok": len(node_ids) == len(set(node_ids)),
            "node_count": len(nodes),
            "unique_node_ids": len(set(node_ids)),
            "issues": []
            if len(node_ids) == len(set(node_ids))
            else ["duplicate_node_id"],
        }

    def operation_policy(self, descriptor: DocumentDescriptor) -> dict[str, Any]:
        return {
            "allowed_operations": ["UPDATE"],
            "review_required_operations": ["UPDATE", "REPLACE"],
            "forbidden_operations": ["ADD_ROW", "GENERATE_ID", "ROW_WIDE_REPLACE"],
            "document_id": descriptor.document_id,
        }


class DomainPackRegistry:
    def __init__(self) -> None:
        self._packs: dict[str, DomainPack] = {}

    def register(self, pack: DomainPack) -> None:
        self._packs[pack.pack_id] = pack

    def get(self, pack_id: str) -> DomainPack | None:
        return self._packs.get(pack_id)

    def select_for(self, descriptor: DocumentDescriptor) -> DomainPack | None:
        if descriptor.domain_pack_id and descriptor.domain_pack_id in self._packs:
            pack = self._packs[descriptor.domain_pack_id]
            if pack.can_handle(descriptor):
                return pack
        for pack in self._packs.values():
            if pack.can_handle(descriptor):
                return pack
        return None

    def list_pack_ids(self) -> list[str]:
        return sorted(self._packs.keys())
