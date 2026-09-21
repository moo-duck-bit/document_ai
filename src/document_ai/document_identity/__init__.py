# -*- coding: utf-8 -*-
"""Document Identity Resolution + Domain Pack Auto Routing."""

from document_ai.document_identity.identity_resolver import resolve_document_identity
from document_ai.document_identity.orchestrator import resolve_uploaded_documents, write_identity_artifacts
from document_ai.document_identity.pack_router import route_domain_pack, document_set_for_identity
from document_ai.document_identity.schema import (
    DocumentIdentityCandidate,
    DocumentIdentityDecision,
    DocumentSignal,
    DomainPackRoutingDecision,
)

__all__ = [
    "DocumentSignal",
    "DocumentIdentityCandidate",
    "DocumentIdentityDecision",
    "DomainPackRoutingDecision",
    "resolve_document_identity",
    "resolve_uploaded_documents",
    "route_domain_pack",
    "document_set_for_identity",
    "write_identity_artifacts",
]
