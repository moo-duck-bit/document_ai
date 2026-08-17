import json
from pathlib import Path

import pytest

from document_ai.intake.change_intake import (
    draft_change_from_request,
    expand_security_ids_to_reqs,
    parse_req_ids_from_text,
    parse_security_ids_from_text,
)


@pytest.fixture(scope="module")
def requirements_payload():
    path = Path("data/cases/mindrium_xa/requirements.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_parse_req_ids():
    assert parse_req_ids_from_text("Req. 6 로그인 제한 강화") == ["Req. 6"]
    assert parse_req_ids_from_text("요구사항 6과 Req.102 변경") == ["Req. 6", "Req. 102"]


def test_parse_security_ids():
    assert parse_security_ids_from_text("IA-04 인증정보 변경") == ["IA-04"]


def test_expand_security_to_reqs(requirements_payload):
    linked = expand_security_ids_to_reqs(["IA-04"], requirements_payload["traceability"])
    assert "Req. 6" in linked


def test_draft_change_explicit_req_and_description():
    change = draft_change_from_request(
        "ignored",
        explicit_req_id="Req. 6",
        explicit_description="연속 로그인 실패 시 계정 잠금.",
    )
    assert change["intake"]["confirmed"] is True
    assert change["requirement_changes"] == [
        {"req_id": "Req. 6", "description": "연속 로그인 실패 시 계정 잠금."}
    ]


def test_draft_change_natural_language(requirements_payload):
    text = (
        "Req. 6 설명을 다음과 같이 변경: "
        "연속 로그인 실패 시 계정 잠금 및 관리자 알림을 수행해야 한다."
    )
    change = draft_change_from_request(text, requirements_payload=requirements_payload)
    assert change["requirement_changes"][0]["req_id"] == "Req. 6"
    assert "계정 잠금" in change["requirement_changes"][0]["description"]
    assert change["intake"]["confirmed"] is True


def test_draft_change_ia_expansion_requires_explicit_req(requirements_payload):
    text = (
        "IA-04 관련 요구사항 설명: "
        "인증정보는 암호화 저장하고 실패 시 잠금 정책을 적용한다."
    )
    change = draft_change_from_request(text, requirements_payload=requirements_payload)
    assert change["requirement_changes"] == []
    assert change["intake"]["confirmed"] is False
    assert any("IA-04" in q for q in change["intake"]["clarifying_questions"])


def test_draft_change_ia_with_explicit_req(requirements_payload):
    text = (
        "Req. 6 IA-04 관련 설명: "
        "인증정보는 암호화 저장하고 실패 시 잠금 정책을 적용한다."
    )
    change = draft_change_from_request(text, requirements_payload=requirements_payload)
    assert any(item["req_id"] == "Req. 6" for item in change["requirement_changes"])
    assert change["intake"]["confirmed"] is True


def test_draft_change_missing_description():
    change = draft_change_from_request("Req. 6 변경해줘")
    assert change["requirement_changes"] == []
    assert change["intake"]["confirmed"] is False
    assert change["intake"]["clarifying_questions"]


def test_draft_change_impact_preview(requirements_payload):
    from document_ai.impact.orchestrator import compute_impact

    change = draft_change_from_request(
        "Req. 6: 로그인 제한 정책 강화.",
        requirements_payload=requirements_payload,
    )
    case_dir = Path("data/cases/mindrium_xa")
    impact = compute_impact(case_dir, change)
    assert "IA-04" in impact["impact"]["linked_security_ids"]
