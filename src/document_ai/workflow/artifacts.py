# -*- coding: utf-8 -*-
"""Workflow artifact writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.workflow.schema import WorkflowRecord


def workflow_dir(root: Path) -> Path:
    d = root / "workflow"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_workflow_artifacts(root: Path, record: WorkflowRecord) -> dict[str, str]:
    wdir = workflow_dir(root)
    paths = {
        "workflow.json": wdir / "workflow.json",
        "workflow_summary.json": wdir / "workflow_summary.json",
        "workflow_validation.json": wdir / "workflow_validation.json",
        "workflow_timeline.json": wdir / "workflow_timeline.json",
    }
    payload = record.to_dict()
    paths["workflow.json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "workflow_id": record.workflow_id,
        "document_set": record.document_set,
        "state": record.state,
        "documents": [
            {
                "document_id": d.get("document_id"),
                "filename": d.get("filename"),
                "role": d.get("role"),
            }
            for d in record.documents
        ],
        "impacted_documents": record.impacted_documents,
        "review_required_count": len(record.review_required),
        "patch_candidate_count": len(record.patch_candidates),
        "writer_result": {
            "status": (record.writer_result or {}).get("status"),
            "applied": (record.writer_result or {}).get("applied", 0),
            "skipped": (record.writer_result or {}).get("skipped", 0),
        },
        "validation": record.validation,
        "result_rows": record.result_rows,
    }
    paths["workflow_summary.json"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    paths["workflow_validation.json"].write_text(
        json.dumps(record.validation or {"ok": True, "issues": []}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    paths["workflow_timeline.json"].write_text(
        json.dumps({"timeline": record.timeline}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {k: str(v).replace("\\", "/") for k, v in paths.items()}


def load_workflow_json(root: Path) -> dict[str, Any] | None:
    path = root / "workflow" / "workflow.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
