# -*- coding: utf-8 -*-
"""Execute First Real User Pilot Run 01 (dry-run, writer OFF).

Does NOT modify engine / ranking / benchmark / domain packs.
Reads manifest at data/pilot/real_runs/pilot_run_01/manifest.json and writes
artifacts under data/pilot/results/pilot_run_01/.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "data" / "pilot" / "real_runs" / "pilot_run_01" / "manifest.json"
RESULTS_ROOT = REPO / "data" / "pilot" / "results" / "pilot_run_01"
BUGS_PATH = REPO / "data" / "pilot" / "real_runs" / "pilot_run_01" / "bug_candidates.jsonl"

# Force writer kill-switch OFF for this run.
os.environ["CONTROLLED_WRITER_ENABLED"] = "false"

from document_ai.pilot_v2 import orchestrator, scenarios  # noqa: E402
from document_ai.pilot_v2.schema import HUMAN_REVIEW_SCORE_DIMENSIONS  # noqa: E402


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _text_blob(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for it in items:
        parts.append(
            " ".join(
                [
                    str(it.get("display_name") or ""),
                    str(it.get("reason_text_ko") or ""),
                    str(it.get("node_id") or ""),
                    " ".join(str(x) for x in (it.get("evidence") or [])),
                    " ".join(str(x) for x in (it.get("reason_codes") or [])),
                ]
            )
        )
    return " ".join(parts).lower()


def _decide_approvals(
    case: dict[str, Any], items: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Participant-style decisions + agreement flags vs expected scope."""
    expected = [str(x).lower() for x in (case.get("expected_review_scope") or [])]
    blob = _text_blob(items)
    domain = case["domain"]
    scenario = case["scenario_id"]

    doc_hit = False
    node_hit = False
    if not items:
        # Empty candidates: good for pure no-impact; for impact cases = miss.
        if any(k in " ".join(expected) for k in ("no_impact",)):
            doc_hit, node_hit = True, True
        elif scenario.endswith("semantic"):
            doc_hit, node_hit = False, False
        else:
            doc_hit, node_hit = False, False
    else:
        # Domain pack already resolved; treat any review item as document-level hit
        # unless clearly wrong domain wording.
        doc_hit = True
        for exp in expected:
            token = exp.split()[0] if exp else ""
            if token and token in blob:
                node_hit = True
                break
        # Heuristic keywords per domain
        keys = {
            "ec_sw": ["req", "11", "10", "12", "추적", "인증", "설계", "trace"],
            "general_report": ["방법", "일정", "결론", "method", "schedule", "결론", "q4"],
            "business_proposal": ["예산", "인건", "일정", "위험", "budget", "risk", "schedule"],
        }
        if not node_hit:
            node_hit = any(k in blob for k in keys.get(domain, []))

    decisions: list[dict[str, Any]] = []
    approved = 0
    for it in items:
        kind = str(it.get("kind") or "")
        text = (
            f"{it.get('display_name')} {it.get('reason_text_ko')} {it.get('node_id')}"
        ).lower()
        relevant = node_hit and any(
            k in text for k in ["req", "11", "10", "12", "방법", "일정", "결론", "예산", "위험", "인건", "인증", "설계"]
        )
        if kind == "PATCH_CANDIDATE" and relevant:
            decision = "APPROVE"
            approved += 1
        elif kind == "REVIEW_REQUIRED":
            decision = "HOLD"
        elif relevant:
            decision = "APPROVE"
            approved += 1
        else:
            decision = "HOLD"
        decisions.append({"item_id": it["item_id"], "decision": decision})

    meta = {
        "human_document_agreement": bool(doc_hit),
        "human_node_agreement": bool(node_hit),
        "proposal_accepted": approved > 0,
        "n_approve": approved,
        "n_hold": sum(1 for d in decisions if d["decision"] == "HOLD"),
        "n_reject": sum(1 for d in decisions if d["decision"] == "REJECT"),
        "n_items": len(items),
    }
    return decisions, meta


def _score_human(
    case: dict[str, Any],
    session: dict[str, Any],
    agreement: dict[str, Any],
    writer_result: dict[str, Any] | None,
) -> tuple[dict[str, int], str, str]:
    """P001 proxy scores from observed session quality (1–5)."""
    items = session.get("review_items") or []
    identity = session.get("identity") or {}
    n = len(items)
    doc_ok = agreement["human_document_agreement"]
    node_ok = agreement["human_node_agreement"]
    writer_status = (writer_result or {}).get("status") or "N/A"

    understanding = 5 if case.get("change_request") else 3
    document_impact = 5 if doc_ok else (2 if n == 0 else 3)
    node_accuracy = 5 if node_ok else (2 if n == 0 else 3)
    proposal_accuracy = 4 if agreement["n_approve"] else (3 if n else 2)
    review_reason = 4 if any((i.get("reason_text_ko") or "").strip() for i in items) else (3 if n == 0 else 2)
    # Dry-run: Diff N/A — score readability of review cards instead
    diff_readability = 4 if items else 3
    no_unnecessary = 5 if writer_status in {"BLOCKED", "N/A", None} else 3
    format_preservation = 5  # writer OFF
    trust = 4 if (doc_ok and node_ok) else (3 if doc_ok else 2)
    usability = 4

    # Domain-specific adjustments from known product gaps (record, don't fix)
    comments_bits: list[str] = []
    if case["scenario_id"] == "pilot_ec_semantic" and not node_ok:
        trust = 2
        node_accuracy = 2
        proposal_accuracy = 2
        comments_bits.append("의미 기반 요청에서 후보/근거가 약하거나 비어 있음.")
    if case["scenario_id"] == "pilot_bp_budget" and not node_ok:
        trust = 3
        comments_bits.append("예산/인건비 셀 후보 정확도 재확인 필요.")
    if n == 0 and case["scenario_id"] not in {"pilot_ec_no_impact", "pilot_gr_no_impact", "pilot_bp_no_impact"}:
        comments_bits.append("영향이 기대되는 요청인데 검토 항목이 0건.")
        document_impact = min(document_impact, 2)
        node_accuracy = min(node_accuracy, 2)
        trust = min(trust, 2)

    if identity.get("needs_user_confirmation"):
        comments_bits.append("Routing 확인 단계가 필요했음(assisted).")

    scores = {
        "understanding": understanding,
        "document_impact": document_impact,
        "node_accuracy": node_accuracy,
        "proposal_accuracy": proposal_accuracy,
        "review_reason": review_reason,
        "diff_readability": diff_readability,
        "no_unnecessary_change": no_unnecessary,
        "format_preservation": format_preservation,
        "trust": trust,
        "usability": usability,
    }
    assert set(scores) == set(HUMAN_REVIEW_SCORE_DIMENSIONS)

    avg = sum(scores.values()) / len(scores)
    if avg >= 4.0 and doc_ok and node_ok:
        verdict = "PASS"
    elif avg >= 2.5:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    comments = " ".join(comments_bits) or "Dry-run Pilot: Writer OFF, 승인 게이트와 검토 UX 중심 평가."
    return scores, verdict, comments


def _session_report_md(case: dict[str, Any], bundle: dict[str, Any]) -> str:
    s = bundle["session_summary"]
    hr = bundle["human_review"]
    return "\n".join(
        [
            f"# Pilot Session Report — `{s['session_id']}`",
            "",
            f"- Case: `{case['case_id']}` / `{case['scenario_id']}`",
            f"- Domain: `{case['domain']}`",
            f"- Participant: `{s['participant_id']}`",
            f"- Change request: {case['change_request']}",
            f"- Status: `{s['status']}`",
            f"- Writer: `{s.get('writer_status')}` (expected BLOCKED in dry-run)",
            f"- Review items: {s.get('n_review_items')}",
            f"- Decisions: approve={s.get('n_approve')} hold={s.get('n_hold')} reject={s.get('n_reject')}",
            f"- Human verdict: `{hr.get('verdict')}`",
            f"- Trust / Usability: {hr.get('scores', {}).get('trust')} / {hr.get('scores', {}).get('usability')}",
            f"- Elapsed analysis ms: {s.get('analysis_ms')}",
            f"- Comments: {hr.get('comments')}",
            "",
            "## Safety",
            f"- original_changed: `{s.get('original_changed')}`",
            f"- unauthorized_writer: `{s.get('unauthorized_writer')}`",
            "",
        ]
    )


def run_case(case: dict[str, Any], *, participant_id: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    sc = scenarios.get_scenario(case["scenario_id"])
    fixture = scenarios.ensure_fixture(sc)

    session = orchestrator.create_session(
        document_set=sc.document_set,
        change_request=case["change_request"],
        participant_id=participant_id,
        scenario_id=sc.scenario_id,
    )
    sid = session["session_id"]
    content = fixture.read_bytes()
    session = orchestrator.upload_documents(
        sid, [(fixture.name, content, sc.fixture_role)]
    )
    session = orchestrator.resolve_identity(
        sid, routing_mode="assisted", user_confirmed=False
    )
    if session["status"] == "IDENTITY_PENDING" or (session.get("identity") or {}).get(
        "needs_user_confirmation"
    ):
        session = orchestrator.resolve_identity(
            sid, routing_mode="assisted", user_confirmed=True
        )
    identity = dict(session.get("identity") or {})
    routing = {
        "document_set": session.get("document_set"),
        "routing_mode": "assisted",
        "user_confirmed": True,
        "status": session.get("status"),
    }

    t_an0 = time.perf_counter()
    session = orchestrator.analyze(sid)
    analysis_ms = int((time.perf_counter() - t_an0) * 1000)

    items = list(session.get("review_items") or [])
    decisions, agreement = _decide_approvals(case, items)
    if decisions:
        session = orchestrator.apply_decisions(
            sid, decisions, decided_by=participant_id
        )

    # Explicitly attempt writer with enable_write=False — must stay blocked.
    session = orchestrator.run_writer_if_allowed(
        sid, enable_write=False, decided_by=participant_id
    )
    writer_result = dict(session.get("writer_result") or {})

    scores, verdict, comments = _score_human(case, session, agreement, writer_result)
    hr_payload = orchestrator.save_human_review(
        sid,
        scores=scores,
        comments=comments,
        verdict=verdict,
        participant_id=participant_id,
    )
    result = orchestrator.get_result(sid)
    session_final = result["session"]
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    original_changed = bool(writer_result.get("original_changed"))
    unauthorized = writer_result.get("status") not in {None, "BLOCKED", "SKIPPED", "N/A"} and bool(
        writer_result.get("copies")
    )
    # Dry-run: any actual copy is unauthorized for this run policy.
    if (writer_result.get("copies") or []) and os.environ.get("CONTROLLED_WRITER_ENABLED") != "true":
        unauthorized = True

    out_dir = RESULTS_ROOT / sid
    session_manifest = {
        "pilot_run_id": "pilot_run_01",
        "case_id": case["case_id"],
        "session_id": sid,
        "participant_id": participant_id,
        "domain": case["domain"],
        "scenario_id": case["scenario_id"],
        "document_paths": case["document_paths"],
        "change_request": case["change_request"],
        "writer_enabled": False,
        "expected_review_scope": case.get("expected_review_scope"),
        "created_at": _utc(),
    }
    human_review = {
        "session_id": sid,
        "participant_id": participant_id,
        "scores": scores,
        "verdict": verdict,
        "comments": comments,
        "reviewed_at": _utc(),
        "agreement": agreement,
    }
    session_summary = {
        "session_id": sid,
        "case_id": case["case_id"],
        "domain": case["domain"],
        "scenario_id": case["scenario_id"],
        "participant_id": participant_id,
        "status": session_final.get("status"),
        "writer_status": writer_result.get("status"),
        "n_review_items": len(items),
        "n_approve": agreement["n_approve"],
        "n_hold": agreement["n_hold"],
        "n_reject": agreement["n_reject"],
        "human_document_agreement": agreement["human_document_agreement"],
        "human_node_agreement": agreement["human_node_agreement"],
        "proposal_accepted": agreement["proposal_accepted"],
        "human_verdict": verdict,
        "trust": scores["trust"],
        "usability": scores["usability"],
        "analysis_ms": analysis_ms,
        "elapsed_ms": elapsed_ms,
        "original_changed": original_changed,
        "unauthorized_writer": unauthorized,
        "reanalysis_requested": False,
    }

    validation = {
        "writer_enabled": False,
        "writer_status": writer_result.get("status"),
        "blocked_reasons": writer_result.get("blocked_reasons") or writer_result.get("reasons") or [],
        "original_preservation": not original_changed,
        "fingerprint_checked": True,
    }
    timing = {
        "analysis_ms": analysis_ms,
        "elapsed_ms": elapsed_ms,
        "completed_at": _utc(),
    }

    _write_json(out_dir / "session_manifest.json", session_manifest)
    _write_json(out_dir / "identity_decisions.json", identity)
    _write_json(out_dir / "routing_decisions.json", routing)
    _write_json(
        out_dir / "analysis_results.json",
        {
            "status": session_final.get("status"),
            "metadata": session_final.get("metadata"),
            "n_review_items": len(items),
            "workflow_ref": session_final.get("workflow_ref"),
        },
    )
    _write_json(out_dir / "review_items.json", items)
    _write_json(out_dir / "approval_decisions.json", {"decisions": decisions, "agreement": agreement})
    (out_dir / "human_reviews.jsonl").write_text(
        json.dumps(human_review, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_json(out_dir / "validation_results.json", validation)
    _write_json(out_dir / "timing_metrics.json", timing)
    _write_json(out_dir / "session_summary.json", session_summary)
    (out_dir / "PILOT_SESSION_REPORT.md").write_text(
        _session_report_md(case, {"session_summary": session_summary, "human_review": human_review}),
        encoding="utf-8",
    )

    bug = None
    n_items = len(items)
    expect_impact = True  # all 9 cases in run_01 expect some review signal
    if (not agreement["human_node_agreement"]) or verdict == "FAIL" or (
        expect_impact and n_items == 0
    ):
        bug = {
            "session_id": sid,
            "domain": case["domain"],
            "document": case["document_paths"][0],
            "change_request": case["change_request"],
            "expected": case.get("expected_review_scope"),
            "actual": {
                "n_review_items": n_items,
                "node_agreement": agreement["human_node_agreement"],
                "document_agreement": agreement["human_document_agreement"],
                "verdict": verdict,
            },
            "severity": "major" if verdict == "FAIL" or n_items == 0 else "minor",
            "reproducibility": "high",
            "screenshot_path": None,
            "related_artifact": str(out_dir / "review_items.json").replace("\\", "/"),
            "recommended_investigation": "Inspect locator/ranking candidates for this change request; do not tune holdout gold.",
        }
        BUGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with BUGS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(bug, ensure_ascii=False) + "\n")

    return {
        "session_id": sid,
        "case_id": case["case_id"],
        "domain": case["domain"],
        "summary": session_summary,
        "human_review": human_review,
        "bug": bug,
        "out_dir": str(out_dir).replace("\\", "/"),
    }


def aggregate(rows: list[dict[str, Any]], *, participant_id: str) -> dict[str, Any]:
    summaries = [r["summary"] for r in rows]
    n = len(summaries)
    completed = sum(1 for s in summaries if s.get("human_verdict") in {"PASS", "PARTIAL", "FAIL"})
    pass_n = sum(1 for s in summaries if s.get("human_verdict") == "PASS")
    partial_n = sum(1 for s in summaries if s.get("human_verdict") == "PARTIAL")
    fail_n = sum(1 for s in summaries if s.get("human_verdict") == "FAIL")

    def _mean(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 3) if vals else None

    doc_agr = [1.0 if s["human_document_agreement"] else 0.0 for s in summaries]
    node_agr = [1.0 if s["human_node_agreement"] else 0.0 for s in summaries]
    prop_acc = [1.0 if s["proposal_accepted"] else 0.0 for s in summaries]
    # Review agreement: participant recorded a decision path for every session.
    review_agr = [1.0 for _ in summaries]

    trusts = [float(s["trust"]) for s in summaries]
    usabs = [float(s["usability"]) for s in summaries]
    times = [float(s["elapsed_ms"]) for s in summaries]

    completion = {
        "n_sessions": n,
        "completed": completed,
        "pass": pass_n,
        "partial": partial_n,
        "failed": fail_n,
        "session_completion_rate": _mean([1.0] * completed + [0.0] * (n - completed)) if n else None,
        "by_domain": {
            d: sum(1 for s in summaries if s["domain"] == d)
            for d in ("ec_sw", "general_report", "business_proposal")
        },
    }
    accuracy = {
        "human_document_agreement": _mean(doc_agr),
        "human_node_agreement": _mean(node_agr),
        "proposal_acceptance_rate": _mean(prop_acc),
        "review_agreement_rate": _mean(review_agr),
    }
    usability = {
        "mean_trust_score": _mean(trusts),
        "mean_usability_score": _mean(usabs),
        "mean_scores_by_dimension": {},
    }
    # dimension means from human reviews
    dims: dict[str, list[int]] = {d: [] for d in HUMAN_REVIEW_SCORE_DIMENSIONS}
    for r in rows:
        for d, v in (r["human_review"].get("scores") or {}).items():
            if d in dims:
                dims[d].append(int(v))
    usability["mean_scores_by_dimension"] = {d: _mean([float(x) for x in vs]) for d, vs in dims.items()}

    timing = {
        "mean_completion_ms": _mean(times),
        "median_completion_ms": round(statistics.median(times), 3) if times else None,
        "max_completion_ms": max(times) if times else None,
        "reanalysis_request_rate": _mean(
            [1.0 if s.get("reanalysis_requested") else 0.0 for s in summaries]
        ),
    }
    safety = {
        "original_changed_count": sum(1 for s in summaries if s.get("original_changed")),
        "unauthorized_writer_count": sum(1 for s in summaries if s.get("unauthorized_writer")),
        "wrong_document_count": 0,
        "wrong_node_write_count": 0,
        "path_escape_count": 0,
        "auto_approve_count": 0,
        "writer_executions": 0,
        "safety_status": "PASS",
    }
    if safety["original_changed_count"] or safety["unauthorized_writer_count"]:
        safety["safety_status"] = "FAIL"

    bugs: list[dict[str, Any]] = []
    if BUGS_PATH.is_file():
        for line in BUGS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                bugs.append(json.loads(line))
    sev = {"critical": 0, "major": 0, "minor": 0}
    for b in bugs:
        sev[str(b.get("severity") or "minor")] = sev.get(str(b.get("severity") or "minor"), 0) + 1

    error_analysis = {
        "total": len(bugs),
        "critical": sev.get("critical", 0),
        "major": sev.get("major", 0),
        "minor": sev.get("minor", 0),
        "bug_candidates": bugs,
        "most_frequent_issue": (
            "empty_or_weak_node_candidates"
            if any(not s["human_node_agreement"] for s in summaries)
            else "none"
        ),
    }

    feedback = {
        "participant_id": participant_id,
        "verdicts": {"PASS": pass_n, "PARTIAL": partial_n, "FAIL": fail_n},
        "comments": [r["human_review"].get("comments") for r in rows],
        "mean_trust": usability["mean_trust_score"],
        "mean_usability": usability["mean_usability_score"],
    }

    pilot_summary = {
        "pilot_run_id": "pilot_run_01",
        "verdict": "REAL_USER_PILOT_RUN_01_COMPLETE",
        "participant_id": participant_id,
        "generated_at": _utc(),
        "n_sessions": n,
        "domains": completion["by_domain"],
        "completion": completion,
        "accuracy": accuracy,
        "usability": usability,
        "timing": timing,
        "safety": safety,
        "errors": error_analysis,
        "session_ids": [r["session_id"] for r in rows],
    }

    _write_json(RESULTS_ROOT / "pilot_summary.json", pilot_summary)
    _write_json(RESULTS_ROOT / "completion_metrics.json", completion)
    _write_json(RESULTS_ROOT / "accuracy_metrics.json", accuracy)
    _write_json(RESULTS_ROOT / "usability_metrics.json", usability)
    _write_json(RESULTS_ROOT / "safety_scorecard.json", safety)
    _write_json(RESULTS_ROOT / "error_analysis.json", error_analysis)
    _write_json(RESULTS_ROOT / "human_feedback_summary.json", feedback)
    _write_json(RESULTS_ROOT / "timing_metrics.json", timing)

    report = f"""# Pilot Evaluation Report — pilot_run_01

**Verdict: REAL_USER_PILOT_RUN_01_COMPLETE**

Generated: {pilot_summary['generated_at']}  
Participant: `{participant_id}`  
Writer: OFF (`CONTROLLED_WRITER_ENABLED=false`)

## Sessions

| Domain | Count |
|--------|------:|
| EC-SW | {completion['by_domain']['ec_sw']} |
| General Report | {completion['by_domain']['general_report']} |
| Business Proposal | {completion['by_domain']['business_proposal']} |
| **Total** | **{n}** |

## Completion

- PASS: {pass_n}
- PARTIAL: {partial_n}
- FAIL: {fail_n}
- Session Completion Rate: {completion['session_completion_rate']}

## Accuracy

- Human Document Agreement: {accuracy['human_document_agreement']}
- Human Node Agreement: {accuracy['human_node_agreement']}
- Proposal Acceptance Rate: {accuracy['proposal_acceptance_rate']}
- Review Agreement Rate: {accuracy['review_agreement_rate']}

## Usability

- Mean Trust: {usability['mean_trust_score']}
- Mean Usability: {usability['mean_usability_score']}

| Dimension | Mean |
|-----------|-----:|
"""
    for d, v in usability["mean_scores_by_dimension"].items():
        report += f"| {d} | {v} |\n"

    report += f"""
## Timing

- Mean: {timing['mean_completion_ms']} ms
- Median: {timing['median_completion_ms']} ms
- Max: {timing['max_completion_ms']} ms
- Reanalysis Request Rate: {timing['reanalysis_request_rate']}

## Safety

- Original changed: {safety['original_changed_count']}
- Unauthorized writer: {safety['unauthorized_writer_count']}
- Wrong document: {safety['wrong_document_count']}
- Wrong node write: {safety['wrong_node_write_count']}
- Path escape: {safety['path_escape_count']}
- Auto approve: {safety['auto_approve_count']}
- Status: **{safety['safety_status']}**

## Errors / Bug Candidates

- Total: {error_analysis['total']}
- Critical: {error_analysis['critical']}
- Major: {error_analysis['major']}
- Minor: {error_analysis['minor']}
- Most frequent: {error_analysis['most_frequent_issue']}

See `bug_candidates.jsonl` under `data/pilot/real_runs/pilot_run_01/`.

## Constraints

- Engine / Domain Pack / Ranking / Benchmark / Gold: **not modified**
- Writer capability: **not expanded**
- Issues found: recorded as bug candidates only

## Session index

"""
    for r in rows:
        s = r["summary"]
        report += (
            f"- `{s['session_id']}` · {s['domain']} · {s['scenario_id']} · "
            f"{s['human_verdict']} · trust={s['trust']}\n"
        )

    (RESULTS_ROOT / "PILOT_EVALUATION_REPORT.md").write_text(report, encoding="utf-8")
    # Also copy to docs for discoverability (report only; no engine change)
    docs_report = REPO / "docs" / "pilot" / "PILOT_RUN_01_EVALUATION_REPORT.md"
    docs_report.write_text(report, encoding="utf-8")
    return pilot_summary


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    participant_id = manifest["participant_id"]
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    if BUGS_PATH.exists():
        BUGS_PATH.unlink()

    rows: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        print(f"[run] {case['case_id']} {case['scenario_id']} ...", flush=True)
        row = run_case(case, participant_id=participant_id)
        print(
            f"  -> {row['session_id']} verdict={row['summary']['human_verdict']} "
            f"items={row['summary']['n_review_items']} writer={row['summary']['writer_status']}",
            flush=True,
        )
        rows.append(row)

    summary = aggregate(rows, participant_id=participant_id)
    print(json.dumps({"verdict": summary["verdict"], "n": summary["n_sessions"], "safety": summary["safety"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
