# -*- coding: utf-8 -*-
"""Document role classification from identity decision."""

from __future__ import annotations

from document_ai.document_identity.schema import DocumentIdentityDecision


def classify_document_role(decision: DocumentIdentityDecision) -> str | None:
    return decision.document_role
