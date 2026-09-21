# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — aggregate sessions into pilot_run artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.pilot_v2 import orchestrator, session_store
from document_ai.pilot_v2.metrics import build_pilot_scorecards

REPO = Path(__file__).resolve().parents[3]
DEFAULT_RUNS_DIR = session_store.DEFAULT_PILOT_ROOT / "runs"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def collect_session_records(
    session_ids: list[str] | None = None, *, root: Path | None = None
) -> list[dict[str, Any]]:
    if session_ids:
        out = []
        for sid in session_ids:
            session, _ = orchestrator._load(sid, root=root)  # noqa: SLF001 — internal reuse within package
            out.append(session.to_dict())
        return out
    out = []
    for summary in session_store.list_session_summaries(root, limit=10_000):
        try:
            session, _ = orchestrator._load(summary["session_id"], root=root)  # noqa: SLF001
            out.append(session.to_dict())
        except FileNotFoundError:
            continue
    return out


def determine_verdict(scorecards: dict[str, Any]) -> dict[str, Any]:
    safety = scorecards.get("safety") or {}
    completion = scorecards.get("completion") or {}
    n = int(completion.get("n_sessions") or 0)
    reasons: list[str] = []

    if n == 0:
        return {"verdict": "INSUFFICIENT_DATA", "reasons": ["no_sessions_found"]}
    if safety.get("safety_status") != "PASS":
        reasons.append("safety_scorecard_not_pass")
        return {"verdict": "NOT_READY_SAFETY", "reasons": reasons}

    completion_rate = completion.get("session_completion_rate")
    if completion_rate is None or completion_rate < 0.5:
        reasons.append("session_completion_rate_below_threshold")
        return {"verdict": "NOT_READY_COMPLETION", "reasons": reasons}

    return {"verdict": "READY_FOR_REAL_USER_DOCUMENT_PILOT", "reasons": ["safety_pass", "completion_threshold_met"]}


def evaluate_pilot_run(
    *,
    session_ids: list[str] | None = None,
    root: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    sessions = collect_session_records(session_ids, root=root)
    scorecards = build_pilot_scorecards(sessions)
    verdict = determine_verdict(scorecards)

    run_id = f"pilot_run_{_utc_stamp()}"
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_sessions": len(sessions),
        "session_ids": [s.get("session_id") for s in sessions],
        "scorecards": scorecards,
        "verdict": verdict["verdict"],
        "verdict_reasons": verdict["reasons"],
    }

    out_dir = output_dir or DEFAULT_RUNS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["output_path"] = str(out_path).replace("\\", "/")
    return payload
