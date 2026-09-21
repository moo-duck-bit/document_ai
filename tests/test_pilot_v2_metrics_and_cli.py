# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — metrics, evaluate_run verdict, and CLI (cli_support) tests."""

from __future__ import annotations

from document_ai.pilot_v2 import cli_support, evaluate_run, metrics, orchestrator as pv2


# --- metrics: zero denominator -> None -----------------------------------------------


def test_completion_scorecard_empty_sessions_all_none():
    sc = metrics.compute_completion_scorecard([])
    assert sc["n_sessions"] == 0
    assert sc["analysis_completion_rate"] is None
    assert sc["review_reached_rate"] is None
    assert sc["session_completion_rate"] is None
    assert sc["failure_rate"] is None


def test_accuracy_scorecard_empty_sessions_all_none():
    sc = metrics.compute_accuracy_scorecard([])
    assert sc["n_review_items"] == 0
    assert sc["approval_rate"] is None
    assert sc["human_verdict_pass_rate"] is None


def test_writer_scorecard_empty_sessions_all_none():
    sc = metrics.compute_writer_scorecard([])
    assert sc["n_writer_attempts"] == 0
    assert sc["written_copy_rate"] is None
    assert sc["blocked_rate"] is None
    assert sc["original_preservation_rate"] is None


def test_usability_scorecard_no_responses_is_none():
    sc = metrics.compute_usability_scorecard([])
    assert sc["n_responses"] == 0
    assert sc["overall_average_score"] is None
    assert sc["avg_trust"] is None


def test_safety_scorecard_empty_sessions_passes_vacuously():
    sc = metrics.compute_safety_scorecard([])
    assert sc["safety_status"] == "PASS"
    assert sc["pass"] is True


# --- metrics: mixed session data ------------------------------------------------------


def test_completion_scorecard_computes_rates():
    sessions = [
        {"status": "COMPLETED", "review_items": [{"decision": "APPROVE"}]},
        {"status": "CREATED", "review_items": None},
        {"status": "FAILED", "review_items": None},
        {"status": "REVIEW_COMPLETE", "review_items": [{"decision": "PENDING"}]},
    ]
    sc = metrics.compute_completion_scorecard(sessions)
    assert sc["n_sessions"] == 4
    assert sc["session_completion_rate"] == 0.25
    assert sc["failure_rate"] == 0.25


def test_accuracy_scorecard_counts_decisions_and_verdicts():
    sessions = [
        {
            "review_items": [{"decision": "APPROVE"}, {"decision": "REJECT"}, {"decision": "HOLD"}],
            "human_review": {"verdict": "PASS"},
        },
        {"review_items": [{"decision": "APPROVE"}], "human_review": {"verdict": "FAIL"}},
    ]
    sc = metrics.compute_accuracy_scorecard(sessions)
    assert sc["n_review_items"] == 4
    assert sc["approval_rate"] == 0.5
    assert sc["n_sessions_with_human_review"] == 2
    assert sc["human_verdict_pass_rate"] == 0.5


def test_writer_scorecard_counts_written_and_blocked():
    sessions = [
        {"writer_result": {"status": "WRITTEN_COPY_ONLY", "original_preservation": {"ok": True}, "format_check": {"status": "N/A"}}},
        {"writer_result": {"status": "BLOCKED", "reason_codes": ["NOT_APPROVED"], "original_preservation": {"ok": True}}},
    ]
    sc = metrics.compute_writer_scorecard(sessions)
    assert sc["n_writer_attempts"] == 2
    assert sc["written_copy_rate"] == 0.5
    assert sc["blocked_rate"] == 0.5
    assert sc["original_preservation_rate"] == 1.0
    assert sc["blocked_reason_counts"] == {"NOT_APPROVED": 1}


def test_usability_scorecard_averages_dimensions():
    sessions = [
        {"human_review": {"scores": {"trust": 4, "usability": 2}}},
        {"human_review": {"scores": {"trust": 2}}},
    ]
    sc = metrics.compute_usability_scorecard(sessions)
    assert sc["avg_trust"] == 3.0
    assert sc["avg_usability"] == 2.0
    assert sc["n_responses"] == 2


def test_safety_scorecard_flags_original_changed():
    sessions = [{"writer_result": {"original_preservation": {"ok": False}}}]
    sc = metrics.compute_safety_scorecard(sessions)
    assert sc["original_changed_count"] == 1
    assert sc["safety_status"] == "INVALID"
    assert sc["pass"] is False


def test_safety_scorecard_flags_write_without_approval():
    sessions = [{"writer_result": {"status": "WRITTEN_COPY_ONLY", "has_explicit_approval": False, "approval_ok": True, "original_preservation": {"ok": True}}}]
    sc = metrics.compute_safety_scorecard(sessions)
    assert sc["write_without_approval_count"] == 1
    assert sc["safety_status"] == "INVALID"


def test_build_pilot_scorecards_has_all_five_sections():
    scorecards = metrics.build_pilot_scorecards([])
    assert set(scorecards.keys()) == {"completion", "accuracy", "writer", "usability", "safety"}


# --- evaluate_run: verdict logic -------------------------------------------------------


def test_determine_verdict_insufficient_data_when_no_sessions():
    result = evaluate_run.determine_verdict(metrics.build_pilot_scorecards([]))
    assert result["verdict"] == "INSUFFICIENT_DATA"


def test_determine_verdict_not_ready_safety():
    sessions = [{"status": "COMPLETED", "writer_result": {"original_preservation": {"ok": False}}}]
    scorecards = metrics.build_pilot_scorecards(sessions)
    result = evaluate_run.determine_verdict(scorecards)
    assert result["verdict"] == "NOT_READY_SAFETY"


def test_determine_verdict_not_ready_completion():
    sessions = [{"status": "CREATED"}, {"status": "CREATED"}, {"status": "COMPLETED"}]
    scorecards = metrics.build_pilot_scorecards(sessions)
    result = evaluate_run.determine_verdict(scorecards)
    assert result["verdict"] == "NOT_READY_COMPLETION"


def test_determine_verdict_ready_when_safe_and_complete():
    sessions = [{"status": "COMPLETED"}, {"status": "COMPLETED"}]
    scorecards = metrics.build_pilot_scorecards(sessions)
    result = evaluate_run.determine_verdict(scorecards)
    assert result["verdict"] == "READY_FOR_REAL_USER_DOCUMENT_PILOT"


def test_evaluate_pilot_run_writes_artifact(tmp_path):
    pv2.create_session(document_set="ec_sw", change_request="x", root=tmp_path)
    out_dir = tmp_path / "runs"
    payload = evaluate_run.evaluate_pilot_run(root=tmp_path, output_dir=out_dir)
    assert payload["run_id"].startswith("pilot_run_")
    assert payload["n_sessions"] == 1
    out_path = out_dir / f"{payload['run_id']}.json"
    assert out_path.is_file()


# --- cli_support.run_pilot_session -----------------------------------------------------


def test_run_pilot_session_unknown_scenario_returns_exit_3(tmp_path):
    result, code = cli_support.run_pilot_session("pilot_does_not_exist", root=tmp_path)
    assert code == 3
    assert "error" in result


def test_run_pilot_session_dry_review_never_writes(tmp_path):
    result, code = cli_support.run_pilot_session("pilot_gr_schedule_table", dry_review=True, root=tmp_path)
    assert code == 0
    session = result["session"]
    assert session["status"] in {"WRITER_BLOCKED", "REVIEW_COMPLETE"}
    assert (session.get("writer_result") or {}).get("status") != "WRITTEN_COPY_ONLY"
    for item in session.get("review_items") or []:
        assert item["decision"] != "APPROVE"


def test_run_pilot_session_default_leaves_pending_returns_exit_2_when_items_exist(tmp_path, monkeypatch):
    result, code = cli_support.run_pilot_session("pilot_gr_schedule_table", root=tmp_path)
    session = result["session"]
    if session.get("review_items"):
        assert code == 2
    else:
        assert code == 0


def test_run_pilot_session_approve_all_without_writer_enabled_stays_blocked(tmp_path):
    result, code = cli_support.run_pilot_session(
        "pilot_gr_schedule_table", approve_all=True, writer_enabled=False, root=tmp_path
    )
    session = result["session"]
    assert (session.get("writer_result") or {}).get("status") != "WRITTEN_COPY_ONLY"
    assert code == 0


def test_run_pilot_session_approve_all_and_writer_enabled_without_env_var_blocked(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTROLLED_WRITER_ENABLED", raising=False)
    result, code = cli_support.run_pilot_session(
        "pilot_gr_schedule_table", approve_all=True, writer_enabled=True, root=tmp_path
    )
    session = result["session"]
    assert (session.get("writer_result") or {}).get("status") != "WRITTEN_COPY_ONLY"


def test_run_pilot_session_full_approval_with_env_completes(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLLED_WRITER_ENABLED", "true")
    result, code = cli_support.run_pilot_session(
        "pilot_gr_schedule_table", approve_all=True, writer_enabled=True, root=tmp_path
    )
    session = result["session"]
    if (session.get("review_items") or []):
        assert (session.get("writer_result") or {}).get("status") == "WRITTEN_COPY_ONLY"
        assert code == 0


# --- cli_support.evaluate_pilot ---------------------------------------------------------


def test_evaluate_pilot_insufficient_data_exit_3(tmp_path):
    payload, code = cli_support.evaluate_pilot(root=tmp_path, output_dir=tmp_path / "runs")
    assert code == 3
    assert payload["verdict"] == "INSUFFICIENT_DATA"


def test_evaluate_pilot_not_ready_completion_exit_2(tmp_path):
    cli_support.run_pilot_session("pilot_gr_schedule_table", dry_review=True, root=tmp_path)
    payload, code = cli_support.evaluate_pilot(root=tmp_path, output_dir=tmp_path / "runs")
    assert code == 2
    assert payload["verdict"] == "NOT_READY_COMPLETION"


def test_evaluate_pilot_ready_exit_0_after_human_review(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLLED_WRITER_ENABLED", "true")
    result, _ = cli_support.run_pilot_session(
        "pilot_gr_schedule_table", approve_all=True, writer_enabled=True, root=tmp_path
    )
    sid = result["session"]["session_id"]
    pv2.save_human_review(sid, scores={"trust": 5, "usability": 5}, verdict="PASS", root=tmp_path)
    payload, code = cli_support.evaluate_pilot(root=tmp_path, output_dir=tmp_path / "runs")
    assert code == 0
    assert payload["verdict"] == "READY_FOR_REAL_USER_DOCUMENT_PILOT"
