# -*- coding: utf-8 -*-
"""Document identity orchestrator — artifacts + workflow helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from document_ai.document_identity.identity_resolver import resolve_document_identity
from document_ai.document_identity.pack_router import (
    document_set_for_identity,
    route_domain_pack,
)
from document_ai.document_identity.schema import (
    DocumentIdentityCandidate,
    DocumentIdentityDecision,
    DomainPackRoutingDecision,
    DocumentSignal,
)
from document_ai.document_identity.validation import validate_identity_invariants


def file_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def analyze_duplicates(
    *,
    decisions: list[DocumentIdentityDecision],
    content_hashes: dict[str, str],
) -> list[dict[str, Any]]:
    by_canonical: dict[str, list[str]] = {}
    for d in decisions:
        if not d.canonical_document_id:
            continue
        by_canonical.setdefault(d.canonical_document_id, []).append(d.source_document_id)
    out: list[dict[str, Any]] = []
    for canon, sources in by_canonical.items():
        if len(sources) < 2:
            continue
        hashes = [content_hashes.get(s) for s in sources]
        if len(set(h for h in hashes if h)) == 1 and all(hashes):
            status = "DUPLICATE_EXACT"
        elif len(set(h for h in hashes if h)) > 1:
            status = "DUPLICATE_VARIANT"
        else:
            status = "MULTIPLE_VALID_DOCUMENTS"
        out.append(
            {
                "canonical_document_id": canon,
                "source_document_ids": sources,
                "status": status,
                "content_hashes": {s: content_hashes.get(s) for s in sources},
            }
        )
    return out


def write_identity_artifacts(
    out_dir: Path,
    *,
    signals: list[DocumentSignal],
    candidates: list[DocumentIdentityCandidate],
    decisions: list[DocumentIdentityDecision],
    routings: list[DomainPackRoutingDecision],
    duplicates: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    conflicts = [
        {
            "source_document_id": d.source_document_id,
            "reason_codes": d.reason_codes,
            "decision_status": d.decision_status,
        }
        for d in decisions
        if d.decision_status == "REVIEW_REQUIRED"
        and any("CONFLICT" in r or "conflict" in r or "AMBIGUOUS" in r for r in d.reason_codes)
    ]
    payload = {
        "document_signals.json": [s.to_dict() for s in signals],
        "identity_candidates.json": [c.to_dict() for c in candidates],
        "identity_decisions.json": [d.to_dict() for d in decisions],
        "pack_routing_candidates.json": [
            {"source_document_id": r.source_document_id, "candidate_pack_ids": r.candidate_pack_ids}
            for r in routings
        ],
        "pack_routing_decisions.json": [r.to_dict() for r in routings],
        "identity_conflicts.json": conflicts,
        "duplicate_document_analysis.json": duplicates or [],
        "identity_summary.json": {
            "n_documents": len(decisions),
            "auto_selected": sum(1 for d in decisions if d.auto_selected),
            "review_required": sum(1 for d in decisions if d.decision_status == "REVIEW_REQUIRED"),
            "unresolved": sum(1 for d in decisions if d.decision_status == "UNRESOLVED"),
            "routed": sum(1 for r in routings if r.routing_status == "ROUTED"),
        },
        "identity_validation.json": validation or {},
    }
    for name, data in payload.items():
        (out_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return out_dir


def resolve_uploaded_documents(
    *,
    uploaded_docs: list[dict[str, Any]],
    routing_mode: str = "assisted",
    explicit_document_set: str | None = None,
    user_confirmed: bool = False,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """Resolve identity for each uploaded doc; enrich docs with canonical descriptors."""
    all_signals: list[DocumentSignal] = []
    all_candidates: list[DocumentIdentityCandidate] = []
    decisions: list[DocumentIdentityDecision] = []
    routings: list[DomainPackRoutingDecision] = []
    hashes: dict[str, str] = {}
    enriched: list[dict[str, Any]] = []

    for doc in uploaded_docs:
        source_id = str(doc.get("document_id") or doc.get("source_document_id") or "")
        filename = str(doc.get("filename") or "")
        path = doc.get("path")
        docx_path = Path(path) if path else None
        hints = doc.get("user_hints") or {}
        if doc.get("role_hint"):
            hints = {**hints, "document_role": doc["role_hint"]}
        signals, candidates, decision = resolve_document_identity(
            source_document_id=source_id,
            filename=filename,
            docx_path=docx_path if docx_path and docx_path.is_file() else None,
            user_hints=hints or None,
        )
        routing = route_domain_pack(
            identity=decision,
            candidates=candidates,
            routing_mode=routing_mode,
            explicit_document_set=explicit_document_set,
            user_confirmed=user_confirmed,
        )
        all_signals.extend(signals)
        all_candidates.extend(candidates)
        decisions.append(decision)
        routings.append(routing)

        if docx_path and docx_path.is_file():
            hashes[source_id] = file_content_hash(docx_path.read_bytes())

        row = dict(doc)
        row["source_document_id"] = source_id
        row["canonical_document_id"] = decision.canonical_document_id
        row["short_id"] = decision.short_id
        row["document_type"] = decision.document_type
        row["document_role"] = decision.document_role or doc.get("role")
        row["domain_pack_id"] = decision.domain_pack_id
        row["template_id"] = decision.template_id
        row["identity_status"] = decision.decision_status
        row["identity_auto_selected"] = decision.auto_selected
        row["identity_score"] = decision.top_score
        row["identity_reasons"] = decision.reason_codes
        row["routing_status"] = routing.routing_status
        row["selected_pack_id"] = routing.selected_pack_id
        row["recommended_document_set"] = document_set_for_identity(decision)
        # Keep temporary document_id for gold/fixture alignment; expose registry short_id separately
        if decision.short_id and decision.document_role:
            row["role"] = decision.document_role
            row["registry_document_id"] = decision.short_id  # e.g. MDTM for EC-SW indexing
        enriched.append(row)

    duplicates = analyze_duplicates(decisions=decisions, content_hashes=hashes)
    validation_rows = [
        validate_identity_invariants(signals=all_signals, decision=d, routing=r)
        for d, r in zip(decisions, routings)
    ]
    validation = {
        "ok": all(v["ok"] for v in validation_rows) if validation_rows else True,
        "per_document": validation_rows,
    }
    if artifact_dir is not None:
        write_identity_artifacts(
            artifact_dir,
            signals=all_signals,
            candidates=all_candidates,
            decisions=decisions,
            routings=routings,
            duplicates=duplicates,
            validation=validation,
        )

    # Workflow-level pack: prefer unanimous routed pack / document_set
    recommended_sets = [d.get("recommended_document_set") for d in enriched if d.get("recommended_document_set")]
    workflow_document_set = None
    if recommended_sets and len(set(recommended_sets)) == 1:
        workflow_document_set = recommended_sets[0]
    needs_confirm = any(
        r.routing_status != "ROUTED" or r.human_review_required for r in routings
    ) and routing_mode != "explicit"

    return {
        "uploaded_docs": enriched,
        "signals": [s.to_dict() for s in all_signals],
        "candidates": [c.to_dict() for c in all_candidates],
        "decisions": [d.to_dict() for d in decisions],
        "routings": [r.to_dict() for r in routings],
        "duplicates": duplicates,
        "validation": validation,
        "recommended_document_set": workflow_document_set,
        "needs_user_confirmation": bool(needs_confirm and routing_mode == "assisted"),
        "routing_mode": routing_mode,
    }
