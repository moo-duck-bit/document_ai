# -*- coding: utf-8 -*-
"""Workflow input document validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

SUPPORTED_EXTENSIONS = frozenset({".docx", ".md", ".markdown", ".txt"})

REQUIRED_ROLES: dict[str, frozenset[str]] = {
    # EC-SW E2E can run with traceability alone for MDTM POC; soft-require none hard
    "ec_sw": frozenset(),
    "general_report": frozenset(),
    "business_proposal": frozenset(),
}


class WorkflowInputError(ValueError):
    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}")


def validate_uploaded_documents(
    documents: list[dict[str, Any]],
    *,
    document_set: str,
    workflow_root: Path,
) -> dict[str, Any]:
    issues: list[str] = []
    if not documents:
        raise WorkflowInputError("NO_DOCUMENTS", "at least one document is required for analysis")

    names: set[str] = set()
    ids: set[str] = set()
    root = workflow_root.resolve()

    for d in documents:
        path = Path(d.get("path") or "")
        filename = str(d.get("filename") or path.name)
        doc_id = str(d.get("document_id") or "")
        if not path.is_file():
            raise WorkflowInputError("EMPTY_DOCUMENT", f"missing file: {filename}")
        if path.stat().st_size <= 0:
            raise WorkflowInputError("EMPTY_DOCUMENT", f"empty file: {filename}")
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise WorkflowInputError("UNSUPPORTED_FORMAT", f"unsupported format: {ext}")
        if filename in names:
            raise WorkflowInputError("DUPLICATE_FILENAME", f"duplicate filename: {filename}")
        names.add(filename)
        if doc_id in ids:
            raise WorkflowInputError("DUPLICATE_DOCUMENT_ID", f"duplicate document_id: {doc_id}")
        ids.add(doc_id)
        try:
            resolved = path.resolve()
        except OSError as exc:
            raise WorkflowInputError("INVALID_DOCUMENT_PATH", str(exc)) from exc
        if root not in resolved.parents and resolved != root:
            # allow files under workflow_root/input or copies
            raise WorkflowInputError(
                "INVALID_DOCUMENT_PATH",
                f"document path outside workflow root: {resolved}",
            )

    required = REQUIRED_ROLES.get(document_set, frozenset())
    roles = {str(d.get("role") or "") for d in documents}
    missing = sorted(required - roles)
    if missing:
        raise WorkflowInputError(
            "MISSING_REQUIRED_ROLE",
            f"missing required roles: {', '.join(missing)}",
        )

    return {"ok": True, "issues": issues, "document_count": len(documents)}
