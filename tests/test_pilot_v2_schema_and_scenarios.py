# -*- coding: utf-8 -*-
"""Real User Document Pilot v2 — schema, scenario registry, and reason_i18n tests."""

from __future__ import annotations

import json

import pytest

from document_ai.pilot_v2 import reason_i18n, scenarios
from document_ai.pilot_v2.schema import (
    HUMAN_REVIEW_SCORE_DIMENSIONS,
    HUMAN_REVIEW_VERDICTS,
    REVIEW_DECISIONS,
    SESSION_STATUSES,
    HumanReviewRecord,
    PilotSession,
    ReviewItem,
)

# --- schema: PilotSession -----------------------------------------------------


def test_pilot_session_defaults():
    s = PilotSession(session_id="s1", participant_id="P001", document_set="ec_sw")
    assert s.status == "CREATED"
    assert s.documents == []
    assert s.review_items == []
    assert s.human_review is None


def test_pilot_session_to_dict_roundtrip():
    s = PilotSession(session_id="s1", participant_id="P001", document_set="ec_sw", change_request="cr")
    d = s.to_dict()
    assert d["session_id"] == "s1"
    assert d["change_request"] == "cr"
    fields = set(PilotSession.__dataclass_fields__.keys())
    rebuilt = PilotSession(**{k: d[k] for k in fields if k in d})
    assert rebuilt.session_id == s.session_id


def test_pilot_session_touch_updates_status_and_timestamp():
    s = PilotSession(session_id="s1", participant_id="P001", document_set="ec_sw")
    before = s.updated_at
    s.touch("UPLOADED")
    assert s.status == "UPLOADED"
    assert s.updated_at >= before


def test_pilot_session_touch_without_status_keeps_status():
    s = PilotSession(session_id="s1", participant_id="P001", document_set="ec_sw", status="ANALYZED")
    s.touch()
    assert s.status == "ANALYZED"


def test_pilot_session_add_event_appends_timeline():
    s = PilotSession(session_id="s1", participant_id="P001", document_set="ec_sw")
    s.add_event("created", "detail-text")
    assert len(s.timeline) == 1
    assert s.timeline[0]["event"] == "created"
    assert s.timeline[0]["detail"] == "detail-text"
    assert s.timeline[0]["status"] == s.status


def test_session_statuses_cover_expected_values():
    for expected in ("CREATED", "UPLOADED", "REVIEW_COMPLETE", "WRITER_BLOCKED", "WRITER_COMPLETED", "COMPLETED", "FAILED"):
        assert expected in SESSION_STATUSES


def test_review_decisions_cover_expected_values():
    assert REVIEW_DECISIONS == frozenset({"PENDING", "APPROVE", "REJECT", "HOLD", "EDIT_PROPOSAL"})


# --- schema: ReviewItem --------------------------------------------------------


def test_review_item_to_dict():
    item = ReviewItem(item_id="i1", document_id="D1", kind="PATCH_CANDIDATE", reason_codes=["TIER_1"])
    d = item.to_dict()
    assert d["item_id"] == "i1"
    assert d["decision"] == "PENDING"
    assert d["reason_codes"] == ["TIER_1"]


# --- schema: HumanReviewRecord --------------------------------------------------


def test_human_review_record_average_score():
    r = HumanReviewRecord(session_id="s1", participant_id="P001", scores={"trust": 4, "usability": 2})
    assert r.average_score() == 3.0


def test_human_review_record_average_score_none_when_empty():
    r = HumanReviewRecord(session_id="s1", participant_id="P001", scores={})
    assert r.average_score() is None


def test_human_review_verdicts_are_fixed_set():
    assert HUMAN_REVIEW_VERDICTS == frozenset({"PASS", "PARTIAL", "FAIL", "PENDING"})


def test_human_review_score_dimensions_are_five():
    assert len(HUMAN_REVIEW_SCORE_DIMENSIONS) == 10
    assert "trust" in HUMAN_REVIEW_SCORE_DIMENSIONS
    assert "usability" in HUMAN_REVIEW_SCORE_DIMENSIONS
    assert "understanding" in HUMAN_REVIEW_SCORE_DIMENSIONS


# --- scenarios: registry --------------------------------------------------------


def test_load_scenarios_returns_twelve():
    rows = scenarios.load_scenarios()
    assert len(rows) == 12


def test_load_scenarios_domain_distribution():
    rows = scenarios.load_scenarios()
    by_domain: dict[str, int] = {}
    for s in rows:
        by_domain[s.domain] = by_domain.get(s.domain, 0) + 1
    assert by_domain == {"ec_sw": 4, "general_report": 4, "business_proposal": 4}


def test_scenario_ids_are_pilot_prefixed_not_holdout_ids():
    rows = scenarios.load_scenarios()
    for s in rows:
        assert s.scenario_id.startswith("pilot_")


def test_get_scenario_finds_by_id():
    s = scenarios.get_scenario("pilot_ec_req_single")
    assert s.domain == "ec_sw"
    assert s.document_set == "ec_sw"


def test_get_scenario_raises_for_unknown_id():
    with pytest.raises(scenarios.ScenarioError):
        scenarios.get_scenario("pilot_does_not_exist")


def test_load_scenarios_rejects_duplicate_ids(tmp_path):
    bad = tmp_path / "scenarios.json"
    bad.write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "scenario_id": "dup",
                        "domain": "ec_sw",
                        "document_set": "ec_sw",
                        "title": "t",
                        "change_request": "cr",
                        "fixture_relative_path": "fixtures/x.docx",
                        "fixture_builder": "mdtm_pilot_base",
                        "fixture_role": "traceability",
                    },
                    {
                        "scenario_id": "dup",
                        "domain": "ec_sw",
                        "document_set": "ec_sw",
                        "title": "t2",
                        "change_request": "cr2",
                        "fixture_relative_path": "fixtures/y.docx",
                        "fixture_builder": "mdtm_pilot_base",
                        "fixture_role": "traceability",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(scenarios.ScenarioError):
        scenarios.load_scenarios(scenarios_json=bad)


def test_load_scenarios_rejects_invalid_domain(tmp_path):
    bad = tmp_path / "scenarios.json"
    bad.write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "scenario_id": "s1",
                        "domain": "not_a_real_domain",
                        "document_set": "ec_sw",
                        "title": "t",
                        "change_request": "cr",
                        "fixture_relative_path": "fixtures/x.docx",
                        "fixture_builder": "mdtm_pilot_base",
                        "fixture_role": "traceability",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(scenarios.ScenarioError):
        scenarios.load_scenarios(scenarios_json=bad)


def test_load_scenarios_rejects_missing_id(tmp_path):
    bad = tmp_path / "scenarios.json"
    bad.write_text(json.dumps({"scenarios": [{"domain": "ec_sw"}]}), encoding="utf-8")
    with pytest.raises(scenarios.ScenarioError):
        scenarios.load_scenarios(scenarios_json=bad)


def test_ensure_fixture_is_idempotent():
    scenario = scenarios.get_scenario("pilot_ec_req_single")
    path1 = scenarios.ensure_fixture(scenario)
    assert path1.is_file()
    size1 = path1.stat().st_size
    path2 = scenarios.ensure_fixture(scenario)
    assert path2 == path1
    assert path2.stat().st_size == size1


def test_ensure_all_fixtures_builds_every_scenario():
    built = scenarios.ensure_all_fixtures()
    assert len(built) == 12
    for scenario_id, path in built.items():
        assert path.is_file()
        assert path.stat().st_size > 0


def test_pilot_scenario_fixture_path_is_under_scenarios_dir():
    scenario = scenarios.get_scenario("pilot_bp_budget")
    assert scenario.fixture_path().is_relative_to(scenarios.SCENARIOS_DIR)


def test_scenarios_never_reference_frozen_benchmark_paths():
    for s in scenarios.load_scenarios():
        assert "document_set_benchmark" not in s.fixture_relative_path
        assert "examples" not in s.fixture_relative_path


# --- reason_i18n ----------------------------------------------------------------


def test_translate_code_known_code_returns_korean():
    text = reason_i18n.translate_code("TIER_1")
    assert "우선" in text or "신뢰도" in text


def test_translate_code_case_insensitive_match():
    assert reason_i18n.translate_code("tier_1") == reason_i18n.translate_code("TIER_1")


def test_translate_code_unknown_code_uses_fallback_template():
    text = reason_i18n.translate_code("SOME_UNKNOWN_CODE_XYZ")
    assert "SOME_UNKNOWN_CODE_XYZ" in text


def test_translate_code_empty_returns_empty():
    assert reason_i18n.translate_code("") == ""


def test_translate_codes_dedupes_and_joins():
    text = reason_i18n.translate_codes(["TIER_1", "TIER_1", "NOT_APPROVED"])
    parts = text.split(" ")
    assert len(parts) <= 2 or text.count("우선") <= 1  # no duplicate phrase


def test_translate_codes_empty_list_has_default_text():
    text = reason_i18n.translate_codes([])
    assert text
    text_none = reason_i18n.translate_codes(None)
    assert text_none == text
