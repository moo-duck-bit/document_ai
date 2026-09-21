# -*- coding: utf-8 -*-
"""PR-14 / PR-14.1: Requirement Language Realizer tests."""

from __future__ import annotations

from document_ai.impact.language_realizer import (
    apply_language_realizations,
    realize_requirement_patches,
    realize_requirement_text,
    validate_language_realizations,
    validate_realization,
)
from document_ai.impact.requirement_patch import RequirementPatch

# ---------------------------------------------------------------------------
# Regression fixtures (PR-14.1)
# ---------------------------------------------------------------------------

FIXTURE_LOCKOUT = """API 요청 과다 방지 및 IP 차단
로그인 API는 연속된 인증 실패 횟수를 추적하고, 임계치를 초과한 계정에 대해 일정 시간 로그인 시도를 제한하도록 설계한다.
연속 로그인 실패 시인 경우 시스템은 계정을 잠그해야 한다."""

FIXTURE_LOCKOUT_EXPECTED = """API 요청 과다 방지 및 IP 차단
로그인 API는 연속된 인증 실패 횟수를 추적하고, 임계치를 초과한 계정에 대해 일정 시간 로그인 시도를 제한하도록 설계한다.
연속 로그인 실패 시 시스템은 계정을 잠가야 한다."""

FIXTURE_AUDIT = (
    "로그인 실패 및 계정 잠금 이벤트는 감사 로그로 저장할 수 있도록 설계한다."
)


def _patch(text: str, patch_id: str = "RP-1") -> RequirementPatch:
    return RequirementPatch(
        patch_id=patch_id,
        draft_id=f"SD-{patch_id}",
        contract_id="PC-1",
        atomic_change_id="ACU-001",
        requirement_id="Req. Auth",
        document="MDSR",
        field="description",
        operation="ADD",
        original_requirement="원문.",
        semantic_draft="draft",
        patched_requirement=text,
        changed_spans=[],
        unchanged_spans=[],
        validation_status="VALID",
        validation_issues=[],
        review_required=False,
        scope_preserved=True,
        provenance={},
    )


def _assert_no_corruptions(text: str) -> None:
    for bad in (
        "제한하야 한다",
        "있야 한다",
        "않야 한다",
        "비인이 접근",
        "연속 로그인 실패 시스템은",
        "잠그해야",
    ):
        assert bad not in text, f"corruption present: {bad!r}"


# ---------------------------------------------------------------------------
# PR-14 core (updated expectations for PR-14.1)
# ---------------------------------------------------------------------------


def test_grammar_correction_si_case():
    after, rules = realize_requirement_text(
        "연속 로그인 실패 시인 경우 시스템은 계정을 잠가야 한다."
    )
    assert "시인 경우" not in after
    assert "실패 시 시스템은" in after
    assert any("시인 경우" in r or "conditional_si" in r for r in rules)


def test_jamgeu_conjugation():
    after, rules = realize_requirement_text("시스템은 계정을 잠그해야 한다.")
    assert "잠가야 한다" in after
    assert "잠그해야" not in after
    assert rules


def test_duplicate_notification_phrase():
    after, rules = realize_requirement_text("시스템은 알림에 대한 알림")
    assert after == "시스템은 알림"
    assert "알림에 대한 알림" not in after
    assert rules


def test_target_unlock_phrase():
    after, rules = realize_requirement_text("관리자는 대상을 해제해야 한다.")
    assert "계정 잠금을 해제" in after
    assert "대상을 해제" not in after
    assert rules


def test_account_event_list_and_particle():
    after, rules = realize_requirement_text(
        "시스템은 계정, 기록 및 이벤트을 보존해야 한다."
    )
    assert "계정 잠금, 로그인 실패 및 관련 이벤트를" in after
    assert "이벤트을" not in after
    assert rules


def test_allowlisted_event_particle_only():
    after, _ = realize_requirement_text("시스템은 이벤트을 기록해야 한다.")
    assert "이벤트를" in after
    assert "이벤트을" not in after


def test_design_style_preserved_with_req_style():
    """Mixed styles must NOT be force-unified."""
    text = "시스템은 로그를 남겨야 한다. 또한 알림을 보내도록 설계한다."
    after, _ = realize_requirement_text(text)
    assert "도록 설계한다" in after
    assert "보내야 한다" not in after or "보내도록 설계한다" in after


def test_semantic_unchanged_flag():
    p = _patch("시스템은 재고를 조회해야 한다.")
    realizations, _ = apply_language_realizations([p])
    assert realizations[0].semantic_changed is False
    assert realizations[0].meaning_preserved is True


def test_multiple_rules_applied():
    text = "연속 로그인 실패 시인 경우 시스템은 계정을 잠그해야. 알림에 대한 알림"
    after, rules = realize_requirement_text(text)
    assert len(rules) >= 2
    assert "시인 경우" not in after
    assert "잠그해야" not in after
    assert "실패 시 시스템은" in after


def test_original_patch_not_mutated():
    original = "연속 로그인 실패 시인 경우 잠그해야"
    p = _patch(original)
    realizations, realized = apply_language_realizations([p])
    assert p.patched_requirement == original
    assert realizations[0].after_text != original
    assert realized[0].patched_requirement == realizations[0].after_text


def test_validation_invariants():
    patches = [
        _patch("연속 로그인 실패 시인 경우 시스템은 잠그해야", "RP-1"),
        _patch("시스템은 알림에 대한 알림", "RP-2"),
    ]
    payload = realize_requirement_patches(patches)
    v = payload["validation"]
    assert v["invariants"]["semantic_changed_false"] is True
    assert v["invariants"]["meaning_preserved"] is True
    assert v["invariants"]["actual_docx_unchanged"] is True
    assert payload["summary"]["actual_docx_changed"] is False
    assert payload["summary"]["actual_generation_changed"] is False


def test_language_vs_patch_artifact_shape():
    patches = [_patch("이벤트을 기록해야 한다.")]
    payload = realize_requirement_patches(patches)
    vs = payload["language_vs_patch"]
    assert vs["pair_count"] == 1
    assert vs["pairs"][0]["before_text"] == "이벤트을 기록해야 한다."
    assert "이벤트를" in vs["pairs"][0]["after_text"]


def test_duplicate_removal():
    after, rules = realize_requirement_text("시스템은 알림 알림을 제공해야 한다.")
    assert "알림 알림" not in after
    assert rules


def test_validate_language_realizations_direct():
    patches = [_patch("시스템은 조회해야 한다.")]
    realizations, _ = apply_language_realizations(patches)
    v = validate_language_realizations(realizations)
    assert v["status"] in ("VALID", "VALID_WITH_WARNINGS", "REVIEW_REQUIRED")
    assert v["invariants"]["grammar_normalized"] is True


# ---------------------------------------------------------------------------
# PR-14.1 regression cases
# ---------------------------------------------------------------------------


def test_r1_jehan_dourok_preserved():
    text = "제한하도록 설계한다."
    after, _ = realize_requirement_text(text)
    assert after == text
    assert "하야 한다" not in after


def test_r2_issdorok_preserved():
    text = "저장할 수 있도록 설계한다."
    after, _ = realize_requirement_text(text)
    assert after == text
    assert "있야 한다" not in after


def test_r3_anhdorok_preserved():
    text = "중단하지 않도록 설계한다."
    after, _ = realize_requirement_text(text)
    assert after == text
    assert "않야 한다" not in after


def test_r4_si_case_keeps_si_before_system():
    text = "연속 로그인 실패 시인 경우 시스템은 계정을 잠그해야 한다."
    after, _ = realize_requirement_text(text)
    assert after == "연속 로그인 실패 시 시스템은 계정을 잠가야 한다."
    assert "실패 시스템은" not in after


def test_r5_biinga_preserved():
    text = "비인가 접근"
    after, _ = realize_requirement_text(text)
    assert after == text
    assert "비인이" not in after


def test_r7_notification_only_safe():
    after, _ = realize_requirement_text("알림에 대한 알림")
    assert after == "알림"


def test_r8_target_unlock_exact_only():
    after, _ = realize_requirement_text("시스템은 대상을 해제해야 한다.")
    assert after == "시스템은 계정 잠금을 해제해야 한다."


def test_r9_normal_particles_in_words_untouched():
    text = "비인가 사용자가 시스템에 접근해야 한다."
    after, _ = realize_requirement_text(text)
    assert after == text
    assert "비인이" not in after


def test_r10_idempotency():
    samples = [
        FIXTURE_LOCKOUT,
        FIXTURE_AUDIT,
        "연속 로그인 실패 시인 경우 시스템은 계정을 잠그해야 한다.",
        "제한하도록 설계한다.",
        "비인가 접근",
        "알림에 대한 알림",
    ]
    for s in samples:
        once, _ = realize_requirement_text(s)
        twice, _ = realize_requirement_text(once)
        assert twice == once, repr(s)


def test_r11_unsafe_output_rolls_back():
    ok, reasons = validate_realization(
        "제한하도록 설계한다.",
        "제한하야 한다.",
    )
    assert ok is False
    assert any("unsafe" in r or "design_style" in r for r in reasons)


def test_r12_meaning_loss_not_applied():
    # Simulated unsafe candidate rejected by validate_realization path
    ok, reasons = validate_realization(
        "비인가 접근을 차단해야 한다.",
        "접근을 차단해야 한다.",  # lost 비인가
    )
    assert ok is False
    assert any("security_noun_lost" in r for r in reasons)


def test_r13_fixture_lockout_paragraph():
    after, _ = realize_requirement_text(FIXTURE_LOCKOUT)
    assert after == FIXTURE_LOCKOUT_EXPECTED
    _assert_no_corruptions(after)
    assert "제한하도록 설계한다" in after


def test_r14_fixture_audit_unchanged():
    after, _ = realize_requirement_text(FIXTURE_AUDIT)
    assert after == FIXTURE_AUDIT
    assert "있야 한다" not in after


def test_artifact_payload_has_no_corruptions():
    patches = [
        _patch(FIXTURE_LOCKOUT, "RP-L"),
        _patch(FIXTURE_AUDIT, "RP-A"),
        _patch("제한하도록 설계한다.", "RP-1"),
        _patch("저장할 수 있도록 설계한다.", "RP-2"),
        _patch("중단하지 않도록 설계한다.", "RP-3"),
        _patch("비인가 접근", "RP-4"),
    ]
    payload = realize_requirement_patches(patches)
    blob = str(payload["trace"]) + str(payload["language_vs_patch"])
    for bad in (
        "제한하야 한다",
        "있야 한다",
        "않야 한다",
        "비인이 접근",
        "연속 로그인 실패 시스템은",
    ):
        assert bad not in blob
    assert payload["summary"]["actual_docx_changed"] is False
    assert payload["summary"]["actual_generation_changed"] is False
    # realized after texts
    for r in payload["realizations"]:
        _assert_no_corruptions(r.after_text)
