# -*- coding: utf-8 -*-
"""Thin Generic Document Set Core — DocumentDescriptor / DocumentNode / DomainPack."""

from document_ai.document_set.domain_pack import DomainPack, DomainPackRegistry
from document_ai.document_set.loader import load_document_set_registry
from document_ai.document_set.schema import DocumentDescriptor, DocumentNode, RelationHint
from document_ai.document_set.dependency_graph import (
    DependencyGraph,
    build_ec_sw_dependency_graph,
    expand_patch_candidates_with_closure,
)

__all__ = [
    "DocumentDescriptor",
    "DocumentNode",
    "RelationHint",
    "DomainPack",
    "DomainPackRegistry",
    "load_document_set_registry",
    "DependencyGraph",
    "build_ec_sw_dependency_graph",
    "expand_patch_candidates_with_closure",
]
