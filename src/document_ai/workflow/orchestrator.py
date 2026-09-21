# -*- coding: utf-8 -*-
"""PR-27/28 Workflow orchestrator with hardening."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from document_ai.workflow.analysis import run_workflow_analysis
from document_ai.workflow.artifacts import load_workflow_json, write_workflow_artifacts
from document_ai.workflow.catalog import get_catalog, list_document_sets
from document_ai.workflow.input_validation import WorkflowInputError, validate_uploaded_documents
from document_ai.workflow.schema import ApprovalItem, DocumentResultRow, WorkflowRecord, utc_now
from document_ai.workflow.state_machine import (
    WorkflowStateError,
    assert_can_analyze,
    assert_can_approve,
    assert_can_write,
    transition_record,
)
from document_ai.workflow.validation import validate_workflow_record

REPO = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = REPO / "data" / "user_scenarios" / "_workflow"


def _safe(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip())
    return (cleaned.strip("-._") or "wf")[:64]


def ensure_root(root: Path | None = None) -> Path:
    path = root or DEFAULT_ROOT
    path.mkdir(parents=True, exist_ok=True)
    return path


def workflow_path(workflow_id: str, *, root: Path | None = None) -> Path:
    wid = _safe(workflow_id)
    if ".." in workflow_id or "/" in workflow_id.replace("\\", "/") or "\\" in workflow_id:
        # allow only safe ids
        if wid != workflow_id.replace("\\", "/").split("/")[-1]:
            from document_ai.workflow.paths import WorkflowPathError

            raise WorkflowPathError("PATH_TRAVERSAL_BLOCKED", workflow_id)
    return ensure_root(root) / wid


def _save(record: WorkflowRecord, root: Path) -> WorkflowRecord:
    record.validation = {
        **(record.validation or {}),
        **validate_workflow_record(record, workflow_root=root),
    }
    write_workflow_artifacts(root, record)
    meta = {
        "workflow_id": record.workflow_id,
        "document_set": record.document_set,
        "state": record.state,
        "updated_at": record.updated_at,
    }
    (root / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def _load_record(workflow_id: str, *, root: Path | None = None) -> WorkflowRecord:
    base = workflow_path(workflow_id, root=root)
    raw = load_workflow_json(base)
    if not raw:
        raise FileNotFoundError(f"workflow not found: {workflow_id}")
    fields = set(WorkflowRecord.__dataclass_fields__.keys())
    return WorkflowRecord(**{k: raw[k] for k in fields if k in raw})


def _unique_doc_id(filename: str, used: set[str], idx: int) -> str:
    base = Path(filename).stem.upper()[:36] or f"DOC{idx}"
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    used.add(candidate)
    return candidate


def create_workflow(
    *,
    document_set: str,
    change_request: str,
    files: list[tuple[str, bytes, str | None]] | None = None,
    name: str = "workflow",
    root: Path | None = None,
    document_routing_mode: str = "assisted",
    identity_user_confirmed: bool = False,
    user_hints_by_filename: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    get_catalog(document_set)
    cr = (change_request or "").strip()
    if not cr:
        raise ValueError("change_request is empty")

    base_root = ensure_root(root)
    stamp = utc_now().replace(":", "").replace("-", "")
    workflow_id = f"{_safe(name)}_{_safe(document_set)}_{stamp}"
    work = base_root / workflow_id
    if work.exists():
        raise FileExistsError(workflow_id)
    input_dir = work / "input"
    input_dir.mkdir(parents=True)
    (work / "output").mkdir(parents=True)
    (work / "copies").mkdir(parents=True)
    (input_dir / "change_request.txt").write_text(cr + "\n", encoding="utf-8")

    documents: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    seen_names: set[str] = set()
    for idx, (filename, content, role) in enumerate(files or []):
        safe_name = Path(filename or f"doc_{idx}.docx").name
        if safe_name in seen_names:
            raise WorkflowInputError("DUPLICATE_FILENAME", safe_name)
        seen_names.add(safe_name)
        if not content:
            raise WorkflowInputError("EMPTY_DOCUMENT", safe_name)
        dest = input_dir / safe_name
        dest.write_bytes(content)
        copy_dest = work / "copies" / safe_name
        shutil.copy2(dest, copy_dest)
        hints = (user_hints_by_filename or {}).get(safe_name)
        documents.append(
            {
                "document_id": _unique_doc_id(safe_name, used_ids, idx),
                "source_document_id": None,  # filled after identity; temporary id is document_id
                "filename": safe_name,
                "role": role or "custom",
                "path": str(dest).replace("\\", "/"),
                "copy_path": str(copy_dest).replace("\\", "/"),
                "user_hints": hints,
            }
        )

    # Temporary upload IDs → identity resolution (canonical separate from filename stem)
    from document_ai.document_identity.orchestrator import resolve_uploaded_documents

    for d in documents:
        d["source_document_id"] = d["document_id"]
    identity = resolve_uploaded_documents(
        uploaded_docs=documents,
        routing_mode=document_routing_mode,
        explicit_document_set=document_set if document_routing_mode == "explicit" else None,
        user_confirmed=identity_user_confirmed
        or document_routing_mode == "auto"
        or document_routing_mode == "explicit",
        artifact_dir=work / "output" / "document_identity",
    )
    documents = identity["uploaded_docs"]

    resolved_set = document_set
    if document_routing_mode == "auto" and identity.get("recommended_document_set"):
        # Only switch pack when identity AUTO and routing ROUTED — never on conflict
        routed = [
            r
            for r in identity.get("routings") or []
            if r.get("routing_status") == "ROUTED" and r.get("actual_pack_invoked")
        ]
        if routed and identity.get("recommended_document_set"):
            resolved_set = identity["recommended_document_set"]
            get_catalog(resolved_set)

    record = WorkflowRecord(
        workflow_id=workflow_id,
        document_set=resolved_set,
        state="CREATED",
        change_request=cr,
        documents=documents,
        metadata={
            "legacy_pair_untouched": True,
            "writer_enabled_default": False,
            "document_routing_mode": document_routing_mode,
            "requested_document_set": document_set,
            "identity_summary": identity.get("identity_summary")
            if isinstance(identity.get("identity_summary"), dict)
            else (identity.get("validation") or {}),
            "needs_identity_confirmation": bool(identity.get("needs_user_confirmation")),
            "identity_decisions": identity.get("decisions") or [],
            "pack_routings": identity.get("routings") or [],
        },
    )
    record.add_event(
        "created",
        f"document_set={resolved_set};routing_mode={document_routing_mode}",
    )
    if documents:
        transition_record(record, "UPLOADED", event="uploaded", detail=f"files={len(documents)}")
    _save(record, work)
    return record.to_dict()


def run_analysis(workflow_id: str, *, root: Path | None = None) -> dict[str, Any]:
    work = workflow_path(workflow_id, root=root)
    record = _load_record(workflow_id, root=root)
    try:
        assert_can_analyze(record.state)
        validate_uploaded_documents(
            record.documents, document_set=record.document_set, workflow_root=work
        )
    except (WorkflowStateError, WorkflowInputError) as exc:
        record.errors.append(str(exc))
        record.validation = {
            "ok": False,
            "status": "INVALID",
            "issues": [str(exc)],
            "reason_code": getattr(exc, "reason_code", "INPUT_VALIDATION_ERROR"),
        }
        # do not enter ANALYZING on validation failure
        if isinstance(exc, WorkflowInputError):
            _save(record, work)
            raise
        raise

    transition_record(record, "ANALYZING", event="analysis_started")
    _save(record, work)
    try:
        result = run_workflow_analysis(
            document_set=record.document_set,
            work_dir=work,
            change_request=record.change_request,
            uploaded_docs=record.documents,
        )
        record.impacted_documents = list(result.get("impacted_documents") or [])
        record.patch_candidates = list(result.get("patch_candidates") or [])
        record.review_required = list(result.get("review_required") or [])
        record.metadata["analysis"] = {
            "engine": result.get("engine"),
            "ok": result.get("ok"),
            "note": result.get("note"),
        }
        if result.get("document_impact_decisions") is not None:
            record.metadata["document_impact_decisions"] = list(
                result.get("document_impact_decisions") or []
            )
        if result.get("identifier_analysis") is not None:
            record.metadata["identifier_analysis"] = list(result.get("identifier_analysis") or [])
        if result.get("node_alignments") is not None:
            record.metadata["node_alignments"] = list(result.get("node_alignments") or [])
        if result.get("structural_equivalence_groups") is not None:
            record.metadata["structural_equivalence_groups"] = list(
                result.get("structural_equivalence_groups") or []
            )
        if result.get("generic_query_intent") is not None:
            record.metadata["generic_query_intent"] = result.get("generic_query_intent")
        if result.get("generic_ranking") is not None:
            record.metadata["generic_ranking"] = result.get("generic_ranking")
        approvals: list[dict[str, Any]] = []
        for c in record.patch_candidates + record.review_required:
            item_id = c.get("item_id") or c.get("candidate_id") or c.get("node_id")
            approvals.append(
                ApprovalItem(
                    item_id=str(item_id),
                    document_id=str(c.get("document_id") or "UNKNOWN"),
                    node_id=c.get("node_id"),
                    decision="PENDING",
                ).to_dict()
            )
        record.approvals = approvals
        transition_record(
            record,
            "REVIEW_READY",
            event="analysis_completed",
            detail=f"impacted={len(record.impacted_documents)}",
        )
        transition_record(record, "WAITING_APPROVAL", event="waiting_approval")
    except Exception as exc:  # noqa: BLE001
        record.errors.append(str(exc))
        try:
            transition_record(record, "FAILED", event="analysis_failed", detail=str(exc))
        except WorkflowStateError:
            record.touch("FAILED")
            record.add_event("analysis_failed", str(exc))
    _save(record, work)
    return record.to_dict()


def approve_workflow(
    workflow_id: str,
    *,
    decisions: list[dict[str, Any]] | None = None,
    document_decisions: dict[str, str] | None = None,
    approve_all_pending: bool = False,
    approved_by: str = "pilot",
    root: Path | None = None,
) -> dict[str, Any]:
    work = workflow_path(workflow_id, root=root)
    record = _load_record(workflow_id, root=root)
    assert_can_approve(record.state)

    by_item = {d["item_id"]: d for d in (decisions or []) if d.get("item_id")}
    doc_dec = document_decisions or {}
    updated = []
    for ap in record.approvals:
        item_id = ap["item_id"]
        doc_id = ap.get("document_id")
        decision = ap.get("decision", "PENDING")
        if approve_all_pending and decision == "PENDING":
            decision = "APPROVED"
        if item_id in by_item:
            decision = str(by_item[item_id].get("decision") or decision).upper()
            ap["reason"] = by_item[item_id].get("reason") or ap.get("reason") or ""
        if doc_id in doc_dec:
            decision = str(doc_dec[doc_id]).upper()
        if decision not in {"PENDING", "APPROVED", "REJECTED", "BLOCKED"}:
            decision = "PENDING"
        if decision != ap.get("decision"):
            ap["decision"] = decision
            ap["decided_by"] = approved_by
            ap["decided_at"] = utc_now()
        updated.append(ap)

    record.approvals = updated
    if record.state == "REVIEW_READY":
        transition_record(record, "WAITING_APPROVAL", event="approval_updated")
    else:
        record.add_event(
            "approval_updated",
            f"approved={sum(1 for a in updated if a['decision']=='APPROVED')}",
        )
        record.touch("WAITING_APPROVAL")
    _save(record, work)
    return record.to_dict()


def _aggregate_writer_by_document(
    record: WorkflowRecord,
    details: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    by_doc: dict[str, dict[str, int]] = {}

    def bucket(doc_id: str) -> dict[str, int]:
        return by_doc.setdefault(
            doc_id,
            {"applied": 0, "rejected": 0, "blocked": 0, "skipped": 0, "pending": 0},
        )

    item_to_doc = {}
    for c in record.patch_candidates + record.review_required:
        iid = str(c.get("item_id") or c.get("candidate_id") or c.get("node_id"))
        item_to_doc[iid] = str(c.get("document_id") or "UNKNOWN")
    for ap in record.approvals:
        item_to_doc[str(ap.get("item_id"))] = str(ap.get("document_id") or "UNKNOWN")
        b = bucket(str(ap.get("document_id") or "UNKNOWN"))
        dec = ap.get("decision")
        if dec == "REJECTED":
            b["rejected"] += 1
        elif dec == "BLOCKED":
            b["blocked"] += 1
        elif dec == "PENDING":
            b["pending"] += 1

    for d in details:
        doc_id = str(d.get("document_id") or item_to_doc.get(str(d.get("item_id")), "UNKNOWN"))
        b = bucket(doc_id)
        st = str(d.get("status") or "")
        if st.startswith("APPLIED"):
            b["applied"] += 1
        elif "BLOCKED" in st:
            b["blocked"] += 1
        elif st.startswith("SKIPPED"):
            b["skipped"] += 1
    return by_doc


def run_writer(
    workflow_id: str,
    *,
    enable_write: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    work = workflow_path(workflow_id, root=root)
    record = _load_record(workflow_id, root=root)
    assert_can_write(record.state)
    transition_record(record, "WRITING", event="writer_started", detail=f"enable_write={enable_write}")

    approved_ids = {a["item_id"] for a in record.approvals if a.get("decision") == "APPROVED"}
    details: list[dict[str, Any]] = []

    for c in record.patch_candidates:
        item_id = c.get("item_id") or c.get("candidate_id") or c.get("node_id")
        doc_id = str(c.get("document_id") or "UNKNOWN")
        if str(item_id) not in approved_ids:
            details.append(
                {
                    "item_id": item_id,
                    "document_id": doc_id,
                    "status": "SKIPPED_NOT_APPROVED",
                }
            )
            continue
        if not enable_write:
            details.append(
                {
                    "item_id": item_id,
                    "document_id": doc_id,
                    "status": "SKIPPED_WRITE_DISABLED",
                }
            )
            continue
        details.append(
            {
                "item_id": item_id,
                "document_id": doc_id,
                "status": "BLOCKED_ENGINE_GATE",
            }
        )

    for c in record.review_required:
        item_id = c.get("item_id") or c.get("candidate_id") or c.get("node_id")
        doc_id = str(c.get("document_id") or "UNKNOWN")
        if str(item_id) in approved_ids and enable_write:
            details.append(
                {"item_id": item_id, "document_id": doc_id, "status": "BLOCKED_REVIEW_ITEM"}
            )
        else:
            details.append(
                {"item_id": item_id, "document_id": doc_id, "status": "SKIPPED_REVIEW_ITEM"}
            )

    by_doc = _aggregate_writer_by_document(record, details)
    applied = sum(v["applied"] for v in by_doc.values())
    skipped = sum(v["skipped"] for v in by_doc.values())
    blocked = sum(v["blocked"] for v in by_doc.values())
    rejected = sum(v["rejected"] for v in by_doc.values())

    transition_record(record, "VALIDATING", event="writer_completed", detail=f"applied={applied}")
    record.writer_result = {
        "status": "COMPLETED_PREVIEW" if not enable_write else "GATED",
        "applied": applied,
        "skipped": skipped,
        "rejected": rejected,
        "blocked": blocked,
        "enable_write": enable_write,
        "details": details[:500],
        "by_document": by_doc,
        "controlled_writer_invoked": False,
    }
    _save(record, work)
    return run_result(workflow_id, root=root)


def _build_result_rows(record: WorkflowRecord) -> list[dict[str, Any]]:
    by_doc_writer = (record.writer_result or {}).get("by_document") or {}
    by_doc_appr: dict[str, dict[str, int]] = {}
    for ap in record.approvals:
        doc = ap.get("document_id") or "UNKNOWN"
        by_doc_appr.setdefault(doc, {"APPROVED": 0, "REJECTED": 0, "BLOCKED": 0, "PENDING": 0})
        by_doc_appr[doc][ap.get("decision", "PENDING")] = (
            by_doc_appr[doc].get(ap.get("decision", "PENDING"), 0) + 1
        )

    rows: list[dict[str, Any]] = []
    doc_ids = {d["document_id"] for d in record.documents} | set(record.impacted_documents) | set(
        by_doc_appr
    ) | set(by_doc_writer)
    for doc_id in sorted(doc_ids):
        counts = by_doc_appr.get(doc_id, {"APPROVED": 0, "REJECTED": 0, "BLOCKED": 0, "PENDING": 0})
        wcounts = by_doc_writer.get(
            doc_id, {"applied": 0, "rejected": 0, "blocked": 0, "skipped": 0, "pending": 0}
        )
        status = "UNCHANGED"
        if doc_id in record.impacted_documents:
            status = "IMPACTED"
        if any(r.get("document_id") == doc_id for r in record.review_required):
            status = "REVIEW_REQUIRED"
        if counts.get("APPROVED", 0) and int(wcounts.get("applied") or 0) == 0:
            status = "APPROVED_PENDING_WRITE"
        if counts.get("BLOCKED", 0) and not counts.get("APPROVED", 0):
            status = "BLOCKED"
        if counts.get("REJECTED", 0) and not counts.get("APPROVED", 0):
            status = "REJECTED"
        if int(wcounts.get("applied") or 0) > 0:
            status = "APPLIED" if int(wcounts.get("blocked") or 0) == 0 else "PARTIAL"
        upload = next((d for d in record.documents if d["document_id"] == doc_id), None)
        rows.append(
            DocumentResultRow(
                document_id=doc_id,
                status=status,
                review="Y"
                if any(r.get("document_id") == doc_id for r in record.review_required)
                else "N",
                applied=int(wcounts.get("applied") or 0),
                rejected=int(wcounts.get("rejected") or counts.get("REJECTED") or 0),
                blocked=int(wcounts.get("blocked") or counts.get("BLOCKED") or 0),
                validation="PASS"
                if (record.validation or {}).get("ok", True)
                or (record.validation or {}).get("status") != "INVALID"
                else "FAIL",
                diff_available=False,
                download=(upload.get("copy_path") if upload else None),
            ).to_dict()
        )
        rows[-1]["skipped"] = int(wcounts.get("skipped") or 0)
        rows[-1]["pending"] = int(wcounts.get("pending") or counts.get("PENDING") or 0)
    return rows


def run_result(workflow_id: str, *, root: Path | None = None) -> dict[str, Any]:
    work = workflow_path(workflow_id, root=root)
    record = _load_record(workflow_id, root=root)

    # Idempotent projection for COMPLETED
    if record.state == "COMPLETED" and record.result_rows:
        return {
            "workflow": record.to_dict(),
            "result": {
                "rows": record.result_rows,
                "summary": {
                    "state": record.state,
                    "document_set": record.document_set,
                    "impacted_documents": record.impacted_documents,
                    "writer": record.writer_result,
                    "validation": record.validation,
                },
            },
            "idempotent": True,
        }

    rows = _build_result_rows(record)
    record.result_rows = rows

    if record.state == "FAILED":
        _save(record, work)
    elif record.state == "VALIDATING":
        transition_record(record, "COMPLETED", event="completed")
        _save(record, work)
    elif record.state == "COMPLETED":
        # already completed but empty rows filled once
        if not any(e.get("event") == "completed" for e in record.timeline):
            record.add_event("completed")
        _save(record, work)
    else:
        # allow projection without forcing complete from early states
        pass

    return {
        "workflow": record.to_dict(),
        "result": {
            "rows": rows,
            "summary": {
                "state": record.state,
                "document_set": record.document_set,
                "impacted_documents": record.impacted_documents,
                "writer": record.writer_result,
                "validation": record.validation,
            },
        },
        "idempotent": False,
    }


def get_workflow(workflow_id: str, *, root: Path | None = None) -> dict[str, Any]:
    record = _load_record(workflow_id, root=root)
    work = workflow_path(workflow_id, root=root)
    return {
        "workflow": record.to_dict(),
        "artifacts": {
            "workflow.json": str(work / "workflow" / "workflow.json").replace("\\", "/"),
            "workflow_summary.json": str(work / "workflow" / "workflow_summary.json").replace(
                "\\", "/"
            ),
            "workflow_validation.json": str(work / "workflow" / "workflow_validation.json").replace(
                "\\", "/"
            ),
            "workflow_timeline.json": str(work / "workflow" / "workflow_timeline.json").replace(
                "\\", "/"
            ),
        },
        "catalog": get_catalog(record.document_set),
    }


def list_workflows(*, root: Path | None = None, limit: int = 30) -> list[dict[str, Any]]:
    base = ensure_root(root)
    rows = []
    for p in sorted(base.iterdir(), reverse=True):
        if not p.is_dir():
            continue
        meta_path = p / "meta.json"
        state = "unknown"
        document_set = None
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            state = meta.get("state", state)
            document_set = meta.get("document_set")
        rows.append({"workflow_id": p.name, "state": state, "document_set": document_set})
        if len(rows) >= limit:
            break
    return rows


def catalog_payload() -> dict[str, Any]:
    return {"document_sets": list_document_sets()}
