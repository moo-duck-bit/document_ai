# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — CLI helper functions (non-interactive session runs).

Exit code convention (mirrors ``eval-document-set-v2``'s hint pattern):
    0 — session progressed and reached the requested terminal step cleanly
    1 — runtime/pipeline error (analysis or writer step raised)
    2 — human input still required (review pending; neither --dry-review nor
        --approve-all was given, or identity confirmation could not be resolved
        automatically)
    3 — validation error (unknown scenario id, security/input violation)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.pilot_v2 import orchestrator, scenarios
from document_ai.pilot_v2.orchestrator import PilotOrchestratorError
from document_ai.pilot_v2.scenarios import ScenarioError
from document_ai.pilot_v2.security import PilotSecurityError


def run_pilot_session(
    scenario_id: str,
    *,
    participant_id: str | None = None,
    routing_mode: str = "assisted",
    dry_review: bool = False,
    approve_all: bool = False,
    writer_enabled: bool = False,
    root: Path | None = None,
) -> tuple[dict[str, Any], int]:
    try:
        scenario = scenarios.get_scenario(scenario_id)
        fixture_path = scenarios.ensure_fixture(scenario)
    except ScenarioError as exc:
        return {"error": str(exc), "reason_code": "UNKNOWN_SCENARIO"}, 3

    try:
        session = orchestrator.create_session(
            document_set=scenario.document_set,
            change_request=scenario.change_request,
            participant_id=participant_id,
            scenario_id=scenario.scenario_id,
            root=root,
        )
        session_id = session["session_id"]

        content = fixture_path.read_bytes()
        session = orchestrator.upload_documents(
            session_id, [(fixture_path.name, content, scenario.fixture_role)], root=root
        )

        session = orchestrator.resolve_identity(
            session_id,
            routing_mode=routing_mode,
            user_confirmed=routing_mode != "assisted",
            root=root,
        )
        if session["status"] == "IDENTITY_PENDING":
            # Non-interactive fallback: explicitly confirm so the pipeline can proceed,
            # never silently switching document_set without a recorded confirmation.
            session = orchestrator.resolve_identity(
                session_id, routing_mode=routing_mode, user_confirmed=True, root=root
            )

        session = orchestrator.analyze(session_id, root=root)
    except (PilotOrchestratorError, PilotSecurityError, ScenarioError) as exc:
        return {"error": str(exc), "reason_code": getattr(exc, "reason_code", "VALIDATION_ERROR")}, 3
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "reason_code": "PIPELINE_ERROR"}, 1

    try:
        pending_items = [i for i in session.get("review_items") or [] if i.get("decision") == "PENDING"]
        if approve_all:
            decisions = [{"item_id": i["item_id"], "decision": "APPROVE"} for i in pending_items]
            if decisions:
                session = orchestrator.apply_decisions(session_id, decisions, decided_by="cli-approve-all", root=root)
        elif dry_review:
            decisions = [{"item_id": i["item_id"], "decision": "HOLD"} for i in pending_items]
            if decisions:
                session = orchestrator.apply_decisions(session_id, decisions, decided_by="cli-dry-review", root=root)

        session_after_writer = orchestrator.run_writer_if_allowed(
            session_id,
            enable_write=bool(approve_all and writer_enabled),
            decided_by="cli",
            root=root,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "reason_code": "PIPELINE_ERROR", "session_id": session_id}, 1

    result = orchestrator.get_result(session_id, root=root)
    still_pending = any(
        i.get("decision") == "PENDING" for i in session_after_writer.get("review_items") or []
    )
    writer_status = (session_after_writer.get("writer_result") or {}).get("status")
    if still_pending and not dry_review and not approve_all:
        return result, 2
    if writer_status == "BLOCKED" and approve_all and writer_enabled:
        # Explicit write was requested but blocked for a substantive reason.
        return result, 2
    return result, 0


def evaluate_pilot(
    *,
    session_ids: list[str] | None = None,
    root: Path | None = None,
    output_dir: Path | None = None,
) -> tuple[dict[str, Any], int]:
    from document_ai.pilot_v2.evaluate_run import evaluate_pilot_run

    payload = evaluate_pilot_run(session_ids=session_ids, root=root, output_dir=output_dir)
    verdict = payload.get("verdict")
    if verdict == "INSUFFICIENT_DATA":
        return payload, 3
    if verdict == "NOT_READY_SAFETY":
        return payload, 1
    if verdict == "NOT_READY_COMPLETION":
        return payload, 2
    return payload, 0
