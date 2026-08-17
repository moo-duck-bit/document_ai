import json
from pathlib import Path

from document_ai.impact.orchestrator import apply_change, compute_impact
from document_ai.intake.change_intake import draft_change_from_request
from document_ai.learn.import_srs import import_srs_markdown
from document_ai.learn.req_ids import normalize_requirement_id


def test_import_srs_markdown():
    path = Path("data/cases/stt_srs/source_srs.md")
    data = import_srs_markdown(path)
    assert len(data["requirements"]) >= 10
    assert any(r["req_id"] == "FR-01" for r in data["requirements"])
    assert any(t["requirement"] == "FR-02" for t in data["traceability"])


def test_fr02_draft_and_impact():
    case_dir = Path("data/cases/stt_srs")
    payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    change = draft_change_from_request(
        "FR-02: 한국어·영어·일본어 STT 지원, 정확도 92% 목표",
        requirements_payload=payload,
    )
    assert change["requirement_changes"][0]["req_id"] == "FR-02"
    impact = compute_impact(case_dir, change)
    assert impact["impact"]["linked_test_ids"] == ["TC-02"]
    assert impact["impact"]["documents"]["test_cases"]["action"] == "review"


def test_apply_change_updates_requirements_json(tmp_path):
    case_dir = tmp_path / "stt"
    case_dir.mkdir()
    payload = json.loads(Path("data/cases/stt_srs/requirements.json").read_text(encoding="utf-8"))
    (case_dir / "requirements.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    change = {
        "change_id": "test-fr02",
        "requirement_changes": [
            {
                "req_id": "FR-02",
                "description": "UPDATED FR-02 description for test.",
            }
        ],
    }
    change_path = case_dir / "change.json"
    change_path.write_text(json.dumps(change, ensure_ascii=False, indent=2), encoding="utf-8")

    result = apply_change(case_dir, change_path)
    updated = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    fr02 = next(r for r in updated["requirements"] if r["req_id"] == "FR-02")
    assert fr02["description"] == "UPDATED FR-02 description for test."
    assert result["impact"]["linked_test_ids"] == ["TC-02"]


def test_normalize_fr_nfr_ids():
    assert normalize_requirement_id("FR-2") == "FR-02"
    assert normalize_requirement_id("NFR-03") == "NFR-03"
    assert normalize_requirement_id("TC-7") == "TC-07"
    assert normalize_requirement_id("Req. 6") == "Req. 6"
