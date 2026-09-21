# -*- coding: utf-8 -*-
"""Document AI v2 Real User Document Pilot (Product Validation Cycle 1).

Thin orchestration layer over ``document_ai.workflow`` + ``document_ai.document_identity``
that adds a session-scoped, human-in-the-loop review/approval/writer-gating flow for
real user document pilots. No new domain packs, LLM calls, MDVP, or KG are introduced
here; the writer path is a copy-only controlled writer gated behind explicit approval
and the ``CONTROLLED_WRITER_ENABLED`` environment flag.
"""

from document_ai.pilot_v2.orchestrator import (
    analyze,
    apply_decisions,
    create_session,
    download_artifact,
    get_result,
    get_review_items,
    list_sessions,
    resolve_identity,
    run_writer_if_allowed,
    save_human_review,
    upload_documents,
)
from document_ai.pilot_v2.schema import (
    HumanReviewRecord,
    PilotSession,
    ReviewItem,
    SESSION_STATUSES,
)

__all__ = [
    "PilotSession",
    "HumanReviewRecord",
    "ReviewItem",
    "SESSION_STATUSES",
    "create_session",
    "upload_documents",
    "resolve_identity",
    "analyze",
    "get_review_items",
    "apply_decisions",
    "run_writer_if_allowed",
    "save_human_review",
    "get_result",
    "download_artifact",
    "list_sessions",
]
