# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — thin orchestrator over document_ai.workflow.

Pipeline: create_session -> upload_documents -> resolve_identity -> analyze ->
get_review_items -> apply_decisions -> run_writer_if_allowed -> save_human_review ->
get_result.

Reuses ``document_ai.workflow.orchestrator`` for the actual analysis engine (no
duplicated analysis logic) and ``document_ai.document_identity.orchestrator`` for
identity resolution. The writer stage is a copy-only gated writer: it never
applies textual patches and never opens a source upload path for writing.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from document_ai import workflow as wf
from document_ai.controlled_writer.capability_gate import is_controlled_writer_enabled
from document_ai.document_identity.orchestrator import resolve_uploaded_documents
from document_ai.pilot_v2 import format_check, reason_i18n, security, session_store
from document_ai.pilot_v2.schema import (
    HUMAN_REVIEW_SCORE_DIMENSIONS,
    HUMAN_REVIEW_VERDICTS,
    PilotSession,
    REVIEW_DECISIONS,
    ReviewItem,
)

ALLOWED_DOCUMENT_SETS: frozenset[str] = frozenset({"ec_sw", "general_report", "business_proposal"})

_DECISION_TO_WORKFLOW: dict[str, str] = {
    "PENDING": "PENDING",
    "APPROVE": "APPROVED",
    "APPROVED": "APPROVED",
    "REJECT": "REJECTED",
    "REJECTED": "REJECTED",
    "HOLD": "PENDING",
    "EDIT_PROPOSAL": "PENDING",
}


class PilotOrchestratorError(ValueError):
    def __init__(self, reason_code: str, message: str = ""):
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}" if message else reason_code)


def _load(session_id: str, *, root: Path | None = None) -> tuple[PilotSession, Path]:
    session_root = session_store.session_dir(session_id, root=root)
    raw = session_store.load_session_record(session_root)
    fields = set(PilotSession.__dataclass_fields__.keys())
    session = PilotSession(**{k: raw[k] for k in fields if k in raw})
    return session, session_root


def _save(session: PilotSession, session_root: Path) -> dict[str, Any]:
    session.touch()
    payload = session.to_dict()
    session_store.save_session_record(session_root, payload)
    session_store.register_session_summary(
        {
            "session_id": session.session_id,
            "scenario_id": session.scenario_id,
            "participant_id": session.participant_id,
            "document_set": session.document_set,
            "status": session.status,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        },
        root=session_root.parent.parent,
    )
    return payload


def _unique_doc_id(filename: str, used: set[str], idx: int) -> str:
    base = Path(filename).stem.upper()[:36] or f"DOC{idx}"
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    used.add(candidate)
    return candidate


def create_session(
    *,
    document_set: str,
    change_request: str,
    participant_id: str | None = None,
    scenario_id: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    if document_set not in ALLOWED_DOCUMENT_SETS:
        raise PilotOrchestratorError("UNKNOWN_DOCUMENT_SET", document_set)
    cr = security.sanitize_text(change_request)
    if not cr:
        raise PilotOrchestratorError("EMPTY_CHANGE_REQUEST", "change_request is empty")

    pid = security.safe_id(participant_id or session_store.default_participant_id(root=root), prefix="P", max_len=32)
    session_id = session_store.new_session_id(scenario_id=scenario_id, participant_id=pid)
    session_root = session_store.create_session_workspace(session_id, root=root)

    session = PilotSession(
        session_id=session_id,
        participant_id=pid,
        document_set=document_set,
        scenario_id=scenario_id,
        status="CREATED",
        change_request=cr,
    )
    session.add_event("created", f"document_set={document_set};scenario={scenario_id}")
    session_store.write_trace(
        session_root, "requests", "create_session",
        {"document_set": document_set, "change_request": cr, "scenario_id": scenario_id, "participant_id": pid},
    )
    return _save(session, session_root)


def upload_documents(
    session_id: str,
    files: list[tuple[str, bytes, str | None]],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    session, session_root = _load(session_id, root=root)
    if session.status not in {"CREATED", "UPLOADED"}:
        raise PilotOrchestratorError("INVALID_SESSION_STATE", f"upload requires CREATED, got {session.status}")
    if not files:
        raise PilotOrchestratorError("NO_DOCUMENTS", "at least one document is required")

    used_ids = {d["document_id"] for d in session.documents}
    seen_names = {d["filename"] for d in session.documents}
    new_docs: list[dict[str, Any]] = []
    for idx, (filename, content, role) in enumerate(files):
        descriptor = session_store.copy_upload_into_session(session_root, filename, content, role=role)
        if descriptor["filename"] in seen_names:
            raise PilotOrchestratorError("DUPLICATE_FILENAME", descriptor["filename"])
        seen_names.add(descriptor["filename"])
        descriptor["document_id"] = _unique_doc_id(descriptor["filename"], used_ids, idx)
        new_docs.append(descriptor)

    session.documents.extend(new_docs)
    session.add_event("uploaded", f"files={len(new_docs)}")
    session.touch("UPLOADED")
    session_store.write_trace(
        session_root, "requests", "upload",
        {"documents": [{"filename": d["filename"], "sha256": d["sha256"], "size_bytes": d["size_bytes"]} for d in new_docs]},
    )
    return _save(session, session_root)


def resolve_identity(
    session_id: str,
    *,
    routing_mode: str = "assisted",
    user_confirmed: bool = False,
    document_set_override: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    session, session_root = _load(session_id, root=root)
    if session.status not in {"UPLOADED", "IDENTITY_PENDING", "IDENTITY_RESOLVED"}:
        raise PilotOrchestratorError("INVALID_SESSION_STATE", f"resolve_identity requires UPLOADED, got {session.status}")
    if not session.documents:
        raise PilotOrchestratorError("NO_DOCUMENTS", "upload documents before resolving identity")

    uploaded = [
        {
            "document_id": d["document_id"],
            "filename": d["filename"],
            "path": d["path"],
            "role": d.get("role"),
            "user_hints": {"document_role": d.get("role")} if d.get("role") else None,
        }
        for d in session.documents
    ]
    identity = resolve_uploaded_documents(
        uploaded_docs=uploaded,
        routing_mode=routing_mode,
        explicit_document_set=document_set_override or (session.document_set if routing_mode == "explicit" else None),
        user_confirmed=user_confirmed or routing_mode in {"auto", "explicit"},
        artifact_dir=session_root / "output" / "document_identity",
    )
    enriched_by_id = {d["document_id"]: d for d in identity["uploaded_docs"]}
    for d in session.documents:
        extra = enriched_by_id.get(d["document_id"]) or {}
        for key in (
            "canonical_document_id", "short_id", "document_type", "document_role",
            "domain_pack_id", "template_id", "identity_status", "identity_auto_selected",
            "identity_score", "identity_reasons", "routing_status", "selected_pack_id",
            "recommended_document_set",
        ):
            if key in extra:
                d[key] = extra[key]

    needs_confirm = bool(identity.get("needs_user_confirmation")) and not user_confirmed
    resolved_set = session.document_set
    if document_set_override:
        resolved_set = document_set_override
    elif routing_mode == "auto" and identity.get("recommended_document_set"):
        routed = [r for r in identity.get("routings") or [] if r.get("routing_status") == "ROUTED"]
        if routed:
            resolved_set = identity["recommended_document_set"]
    if resolved_set not in ALLOWED_DOCUMENT_SETS:
        resolved_set = session.document_set

    session.document_set = resolved_set
    session.identity = {
        "routings": identity.get("routings") or [],
        "decisions": identity.get("decisions") or [],
        "duplicates": identity.get("duplicates") or [],
        "validation": identity.get("validation") or {},
        "recommended_document_set": identity.get("recommended_document_set"),
        "needs_user_confirmation": needs_confirm,
        "routing_mode": routing_mode,
    }
    session.add_event("identity_resolved", f"needs_confirmation={needs_confirm}")
    session.touch("IDENTITY_PENDING" if needs_confirm else "IDENTITY_RESOLVED")
    session_store.write_trace(session_root, "output", "identity_trace", session.identity)
    return _save(session, session_root)


def analyze(session_id: str, *, root: Path | None = None) -> dict[str, Any]:
    session, session_root = _load(session_id, root=root)
    if session.status != "IDENTITY_RESOLVED":
        raise PilotOrchestratorError("INVALID_SESSION_STATE", f"analyze requires IDENTITY_RESOLVED, got {session.status}")

    started = time.perf_counter()
    files: list[tuple[str, bytes, str | None]] = []
    for d in session.documents:
        content = Path(d["path"]).read_bytes()
        files.append((d["filename"], content, d.get("role")))

    workflow_root = session_root / "output" / "_workflow"
    wf_rec = wf.create_workflow(
        document_set=session.document_set,
        change_request=session.change_request,
        files=files,
        name="pilot",
        root=workflow_root,
        document_routing_mode="explicit",
    )
    workflow_id = wf_rec["workflow_id"]
    analyzed = wf.run_analysis(workflow_id, root=workflow_root)

    session.workflow_ref = {
        "workflow_id": workflow_id,
        "root": str(workflow_root).replace("\\", "/"),
        "documents": analyzed.get("documents") or [],
    }

    review_items: list[dict[str, Any]] = []
    candidates = analyzed.get("patch_candidates") or []
    reviews = analyzed.get("review_required") or []
    for kind, rows in (("PATCH_CANDIDATE", candidates), ("REVIEW_REQUIRED", reviews)):
        for row in rows:
            item_id = str(row.get("item_id") or row.get("candidate_id") or row.get("node_id") or "")
            codes = list(row.get("reason_codes") or [])
            item = ReviewItem(
                item_id=item_id,
                document_id=str(row.get("document_id") or "UNKNOWN"),
                kind=kind,
                node_id=row.get("node_id"),
                display_name=str(row.get("display_name") or row.get("node_id") or item_id),
                reason_codes=codes,
                reason_text_ko=reason_i18n.translate_codes(codes),
                evidence=list(row.get("evidence") or []),
            )
            review_items.append(item.to_dict())
    session.review_items = review_items

    elapsed = time.perf_counter() - started
    session.metadata["analysis"] = {
        "engine": analyzed.get("metadata", {}).get("analysis", {}).get("engine"),
        "impacted_documents": analyzed.get("impacted_documents") or [],
    }
    session.add_event("analyzed", f"review_items={len(review_items)};elapsed_s={elapsed:.3f}")
    session.touch("REVIEW_IN_PROGRESS" if review_items else "REVIEW_COMPLETE")

    session_store.write_trace(session_root, "output", "analysis_trace", {
        "workflow_id": workflow_id,
        "impacted_documents": analyzed.get("impacted_documents") or [],
        "n_patch_candidates": len(candidates),
        "n_review_required": len(reviews),
    })
    session_store.write_trace(session_root, "output", "validation_trace", analyzed.get("validation") or {})
    session_store.write_trace(session_root, "metrics", "timing_analysis", {"elapsed_seconds": elapsed})
    return _save(session, session_root)


def get_review_items(session_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    session, _ = _load(session_id, root=root)
    return list(session.review_items)


def apply_decisions(
    session_id: str,
    decisions: list[dict[str, Any]],
    *,
    decided_by: str = "reviewer",
    root: Path | None = None,
) -> dict[str, Any]:
    session, session_root = _load(session_id, root=root)
    if session.status not in {"REVIEW_IN_PROGRESS", "REVIEW_COMPLETE"}:
        raise PilotOrchestratorError(
            "INVALID_SESSION_STATE", f"apply_decisions requires REVIEW_IN_PROGRESS, got {session.status}"
        )
    if not session.workflow_ref:
        raise PilotOrchestratorError("NO_WORKFLOW", "analyze must run before decisions")

    by_item = {str(d.get("item_id")): d for d in decisions if d.get("item_id")}
    workflow_decisions: list[dict[str, Any]] = []
    now_items = []
    for item in session.review_items:
        incoming = by_item.get(item["item_id"])
        if incoming is not None:
            raw_decision = str(incoming.get("decision") or "PENDING").upper()
            if raw_decision not in REVIEW_DECISIONS and raw_decision not in {"APPROVED", "REJECTED"}:
                raise PilotOrchestratorError("INVALID_DECISION", raw_decision)
            item["decision"] = raw_decision
            item["edited_text"] = security.sanitize_text(incoming.get("edited_text") or "") or None
            item["notes"] = security.sanitize_text(incoming.get("notes") or "")
            item["decided_by"] = decided_by
            item["decided_at"] = session_store.utc_now()
            workflow_decisions.append(
                {"item_id": item["item_id"], "decision": _DECISION_TO_WORKFLOW.get(raw_decision, "PENDING")}
            )
        now_items.append(item)
    session.review_items = now_items
    session.decisions.append(
        {"decided_by": decided_by, "at": session_store.utc_now(), "items": list(by_item.keys())}
    )

    wf.approve_workflow(
        session.workflow_ref["workflow_id"],
        decisions=workflow_decisions,
        approved_by=decided_by,
        root=Path(session.workflow_ref["root"]),
    )

    all_decided = all(str(i.get("decision")) != "PENDING" for i in session.review_items)
    session.add_event("decisions_applied", f"n={len(workflow_decisions)};all_decided={all_decided}")
    session.touch("REVIEW_COMPLETE" if all_decided else "REVIEW_IN_PROGRESS")

    session_store.write_trace(session_root, "review", "decisions", {"decisions": decisions, "decided_by": decided_by})
    session_store.write_trace(
        session_root, "review", "approval_trace",
        {"workflow_decisions": workflow_decisions, "approved_by": decided_by},
    )
    return _save(session, session_root)


def _evaluate_writer_gates(
    session: PilotSession,
    *,
    enable_write: bool,
    env: dict[str, str] | None,
) -> tuple[bool, dict[str, bool], list[str]]:
    approved_items = [i for i in session.review_items if str(i.get("decision")) == "APPROVE"]
    routing_confirmed = not bool((session.identity or {}).get("needs_user_confirmation"))
    controlled_writer_env = is_controlled_writer_enabled(env=env)

    gates = {
        "explicit_approved_items": bool(approved_items),
        "routing_confirmed": routing_confirmed,
        "enable_write_flag": bool(enable_write),
        "controlled_writer_env_enabled": controlled_writer_env,
    }
    reason_codes: list[str] = []
    if not gates["explicit_approved_items"]:
        reason_codes.append("NOT_APPROVED")
    if not gates["routing_confirmed"]:
        reason_codes.append("ROUTING_NOT_CONFIRMED")
    if not gates["enable_write_flag"]:
        reason_codes.append("WRITE_DISABLED")
    if not gates["controlled_writer_env_enabled"]:
        reason_codes.append("CONTROLLED_WRITER_ENV_DISABLED")

    activation_allowed = all(gates.values())
    if activation_allowed:
        reason_codes = ["ACTIVATION_ALLOWED"]
    return activation_allowed, gates, reason_codes


def run_writer_if_allowed(
    session_id: str,
    *,
    enable_write: bool = False,
    decided_by: str = "reviewer",
    env: dict[str, str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    session, session_root = _load(session_id, root=root)
    if session.status not in {"REVIEW_COMPLETE", "REVIEW_IN_PROGRESS", "WRITER_BLOCKED"}:
        raise PilotOrchestratorError(
            "INVALID_SESSION_STATE", f"writer requires REVIEW_COMPLETE, got {session.status}"
        )

    input_dir = session_root / "input"
    preservation: list[dict[str, Any]] = []
    for d in session.documents:
        preservation.append(
            {"document_id": d["document_id"], **session_store.verify_original_preserved(Path(d["path"]), d["sha256"])}
        )
    all_preserved = all(p.get("ok") for p in preservation)

    activation_allowed, gates, reason_codes = _evaluate_writer_gates(session, enable_write=enable_write, env=env)
    if not all_preserved:
        activation_allowed = False
        reason_codes = list(dict.fromkeys(reason_codes + ["FINGERPRINT_MISMATCH"]))
    gates["fingerprint_ok"] = all_preserved

    approved_doc_ids = sorted(
        {i["document_id"] for i in session.review_items if str(i.get("decision")) == "APPROVE"}
    )
    wf_docs_by_id = {d["document_id"]: d for d in (session.workflow_ref or {}).get("documents") or []}
    session_docs_by_name = {d["filename"]: d for d in session.documents}

    copies_written: list[dict[str, Any]] = []
    format_checks: list[dict[str, Any]] = []
    output_copies_dir = session_root / "output" / "copies"

    if activation_allowed:
        output_copies_dir.mkdir(parents=True, exist_ok=True)
        for doc_id in approved_doc_ids:
            wf_doc = wf_docs_by_id.get(doc_id)
            if not wf_doc:
                continue
            src_session_doc = session_docs_by_name.get(wf_doc.get("filename"))
            if not src_session_doc:
                continue
            source_path = Path(src_session_doc["path"])
            dest_path = output_copies_dir / f"{doc_id}.docx"
            security.assert_source_copy_distinct(source_path, dest_path)
            security.assert_not_original_path(dest_path, forbidden_roots=(input_dir,))
            dest_path.write_bytes(source_path.read_bytes())
            copies_written.append(
                {"document_id": doc_id, "source": str(source_path).replace("\\", "/"), "output": str(dest_path).replace("\\", "/")}
            )
            format_checks.append(
                {"document_id": doc_id, **format_check.check_writer_output(source_path, dest_path)}
            )
        status = "WRITTEN_COPY_ONLY"
    else:
        status = "BLOCKED"

    writer_result = {
        "status": status,
        "reason_codes": reason_codes,
        "reason_text_ko": reason_i18n.translate_codes(reason_codes),
        "gates": gates,
        "approval_ok": gates.get("explicit_approved_items", False),
        "has_explicit_approval": gates.get("explicit_approved_items", False),
        "original_preservation": {"ok": all_preserved, "per_document": preservation},
        "copies_written": copies_written,
        "format_check": format_checks if format_checks else {"status": "N/A", "reason": "writer_not_run"},
        "note": "Copy-only controlled writer (MVP): copies approved documents verbatim; no textual patches applied.",
        "enable_write_requested": bool(enable_write),
    }
    session.writer_result = writer_result
    session.add_event("writer_" + status.lower(), ",".join(reason_codes))
    session.touch("WRITER_COMPLETED" if status == "WRITTEN_COPY_ONLY" else "WRITER_BLOCKED")

    # Advance the underlying workflow state machine (always enable_write=False —
    # the real, copy-only mutation is fully tracked in session.writer_result above;
    # this call never mutates any file, it only records per-item SKIPPED/BLOCKED status).
    if session.workflow_ref:
        try:
            wf.run_writer(session.workflow_ref["workflow_id"], enable_write=False, root=Path(session.workflow_ref["root"]))
        except Exception:  # noqa: BLE001 — best-effort state sync, session record is authoritative
            pass

    session_store.write_trace(session_root, "output", "writer_trace", writer_result)
    return _save(session, session_root)


def save_human_review(
    session_id: str,
    *,
    scores: dict[str, int],
    comments: str = "",
    verdict: str = "PENDING",
    participant_id: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    session, session_root = _load(session_id, root=root)
    verdict_u = str(verdict or "PENDING").upper()
    if verdict_u not in HUMAN_REVIEW_VERDICTS:
        raise PilotOrchestratorError("INVALID_VERDICT", verdict_u)
    clean_scores: dict[str, int] = {}
    for dim, val in (scores or {}).items():
        if dim not in HUMAN_REVIEW_SCORE_DIMENSIONS:
            continue
        try:
            iv = int(val)
        except (TypeError, ValueError) as exc:
            raise PilotOrchestratorError("INVALID_SCORE", f"{dim}={val}") from exc
        if not 1 <= iv <= 5:
            raise PilotOrchestratorError("SCORE_OUT_OF_RANGE", f"{dim}={iv}")
        clean_scores[dim] = iv
    if not clean_scores:
        raise PilotOrchestratorError("NO_SCORES", "at least one 1-5 score is required")

    from document_ai.pilot_v2.schema import HumanReviewRecord

    record = HumanReviewRecord(
        session_id=session.session_id,
        participant_id=security.safe_id(participant_id or session.participant_id, prefix="P", max_len=32),
        scores=clean_scores,
        comments=security.sanitize_text(comments),
        verdict=verdict_u,
    )
    session.human_review = record.to_dict()
    from document_ai.pilot_v2.metrics import build_pilot_scorecards

    session.metrics = build_pilot_scorecards([session.to_dict()])
    session.add_event("human_review_saved", f"verdict={verdict_u}")
    session.touch("COMPLETED")

    session_store.write_trace(session_root, "review", "human_review", session.human_review)
    session_store.write_trace(session_root, "metrics", "session_metrics", session.metrics)
    return _save(session, session_root)


def get_result(session_id: str, *, root: Path | None = None) -> dict[str, Any]:
    session, session_root = _load(session_id, root=root)
    workflow_result: dict[str, Any] | None = None
    if session.workflow_ref:
        try:
            workflow_result = wf.run_result(
                session.workflow_ref["workflow_id"], root=Path(session.workflow_ref["root"])
            )
        except FileNotFoundError:
            workflow_result = None
    return {
        "session": session.to_dict(),
        "workflow_result": workflow_result,
        "session_root": str(session_root).replace("\\", "/"),
    }


def download_artifact(session_id: str, relative_path: str, *, root: Path | None = None) -> Path:
    session_root = session_store.session_dir(session_id, root=root)
    return security.resolve_artifact_path(
        session_root, relative_path, allowed_subdirs=frozenset(session_store.SESSION_SUBDIRS)
    )


def list_sessions(*, root: Path | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return session_store.list_session_summaries(root, limit=limit)
