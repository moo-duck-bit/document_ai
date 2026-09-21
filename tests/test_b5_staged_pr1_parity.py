# -*- coding: utf-8 -*-
"""B5 staged PR-1: structural split parity with B5v2 semantics (synthetic fixtures)."""

from __future__ import annotations

from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.propagation import (
    AlignmentResult,
    DesignCandidate,
    PropagationDecisionResult,
    align_design_candidate,
    assess_design_propagation,
    build_propagation_plan,
    decide_propagation,
    discover_design_candidates,
)
from document_ai.impact.semantic_index import RequirementBlock


def _block(req_id: str, title: str, body: str, doc: str = "MDSR") -> RequirementBlock:
    return RequirementBlock(
        req_id=req_id,
        title=title,
        body_text=f"{title}\n{body}",
        document_type=doc,
        source_path="synthetic",
        source_locator="t",
        keywords=[],
    )


def _decision(
    req_id: str,
    *,
    status: str = "CONSISTENT",
    allow_auto_patch: bool = True,
    **kwargs,
) -> ConsistencyDecision:
    return ConsistencyDecision(
        req_id=req_id,
        document="MDSR",
        status=status,  # type: ignore[arg-type]
        reason=kwargs.get("reason", "synthetic"),
        allow_auto_patch=allow_auto_patch,
        fields={"description": kwargs.get("description", "기존 설명")},
        evidence={
            "compatible_facets": kwargs.get("compatible_facets", ["responsibility", "object"]),
            "conflicting_facets": [],
            "missing_information": [],
            "cr_spans": [],
            "candidate_spans": [],
        },
        b3_prior=kwargs.get("b3_prior", {}),
        confidence=kwargs.get("confidence", 0.5),
    )


# ---------------------------------------------------------------------------
# A. B5a same-ID candidate discovery parity
# ---------------------------------------------------------------------------


def test_b5a_same_id_discovery_parity():
    mdsr = _block("Req. SynA", "창고", "재고 모니터링")
    mddr = _block("Req. SynA", "창고", "재고 조회 및 보충", "MDDR")
    other = _block("Req. Other", "다른", "다른 설계", "MDDR")
    by_key = {
        (mdsr.req_id, "MDSR"): mdsr,
        (mddr.req_id, "MDDR"): mddr,
        (other.req_id, "MDDR"): other,
    }
    cands = discover_design_candidates("Req. SynA", by_key)
    assert len(cands) == 1
    assert isinstance(cands[0], DesignCandidate)
    assert cands[0].design_id == "Req. SynA"
    assert cands[0].sources == ["same_id"]
    assert cands[0].document == "MDDR"
    # Cross-ID intentionally not discovered in PR-1
    assert all(c.design_id != "Req. Other" for c in cands)


def test_b5a_missing_same_id_returns_empty():
    mdsr = _block("Req. Only", "제목", "본문")
    by_key = {(mdsr.req_id, "MDSR"): mdsr}
    assert discover_design_candidates("Req. Only", by_key) == []


# ---------------------------------------------------------------------------
# Shared fixtures for B–E decision cases
# ---------------------------------------------------------------------------


def _patch_case():
    cr = "창고 재고가 안전 재고 미만이면 보충 요청을 생성한다."
    mdsr = _block(
        "Req. SynA",
        "창고 재고 모니터링 및 보충 관리",
        "시스템은 창고 재고 수준을 모니터링하고 보충 요청을 생성해야 한다.",
    )
    mddr = _block(
        "Req. SynA",
        "창고 재고 모니터링 및 보충 관리",
        "재고 서비스는 창고 재고를 조회하고 안전 재고 미만일 때 보충 요청을 생성하도록 구현한다.",
        "MDDR",
    )
    return cr, mdsr, mddr, _decision("Req. SynA"), {"matched_concepts": ["재고", "보충"]}


def _extend_case():
    cr = "예약 가능 좌석에 대기열 등록을 추가하고 대기 순번을 표시한다."
    mdsr = _block("Req. SynB", "예약 가능 여부 조회", "좌석별 예약 가능 여부를 조회한다.")
    mddr = _block(
        "Req. SynB",
        "예약 가능 여부 조회",
        "예약 서비스는 좌석 상태를 조회하여 예약 가능 여부를 반환한다.",
        "MDDR",
    )
    return cr, mdsr, mddr, _decision("Req. SynB"), {"matched_concepts": ["예약", "좌석"]}


def _skip_case():
    cr = "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 목록에서 식별 가능하게 표시한다."
    mdsr = _block(
        "Req. SynC",
        "인증 코드의 안전한 저장 및 관리",
        "일회성 인증 코드를 생성·저장하고 사용 후 재사용을 금지한다. 코드 조회 이력은 감사 기록으로 남긴다.",
    )
    mddr = _block(
        "Req. SynC",
        "인증 코드의 안전한 저장 및 관리",
        "patient_code를 생성해 회원가입 검증에 쓰고 사용 상태를 관리한다. 조회 이력은 감사 기록으로 남긴다.",
        "MDDR",
    )
    return cr, mdsr, mddr, _decision("Req. SynC"), {}


def _needs_review_b4_case():
    cr = "창고 재고가 안전 재고 미만이면 보충 요청을 생성한다."
    mdsr = _block(
        "Req. SynR",
        "창고 재고 모니터링 및 보충 관리",
        "시스템은 창고 재고 수준을 모니터링하고 보충 요청을 생성해야 한다.",
    )
    mddr = _block(
        "Req. SynR",
        "창고 재고 모니터링 및 보충 관리",
        "재고 서비스는 창고 재고를 조회하고 안전 재고 미만일 때 보충 요청을 생성하도록 구현한다.",
        "MDDR",
    )
    return (
        cr,
        mdsr,
        mddr,
        _decision("Req. SynR", status="NEEDS_REVIEW", allow_auto_patch=False),
        {"matched_concepts": ["재고", "보충"]},
    )


def _new_design_case():
    cr = "신규 결제 수단으로 계좌이체를 추가한다."
    mdsr = _block("Req. SynN", "결제 수단 관리", "카드 결제를 지원한다.")
    return cr, mdsr, None, _decision("Req. SynN"), {}


# ---------------------------------------------------------------------------
# B. B5b alignment parity (evidence compatible with assess façade)
# ---------------------------------------------------------------------------


def test_b5b_alignment_parity_with_assess():
    cr, mdsr, mddr, decision, b3 = _patch_case()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    assert isinstance(align, AlignmentResult)
    assert align.alignment == "EVIDENCE_COMPUTED"
    prop, pev, conf, _reason = assess_design_propagation(
        cr, mdsr, mddr, decision=decision, b3_prior=b3
    )
    assert prop == "PATCH_EXISTING"
    # Facet detail computed in B5b; confidence formula unchanged vs façade
    assert align.evidence["facet_detail"] == pev.facet_detail
    assert abs(align.confidence - conf) < 1e-9
    assert "object" in align.evidence["matched_facets"] or align.evidence[
        "matched_responsibilities"
    ]


# ---------------------------------------------------------------------------
# C. B5c decision parity — PATCH / EXTEND / SKIP / NEEDS_REVIEW / NEW_DESIGN
# ---------------------------------------------------------------------------


def test_b5c_patch_case():
    cr, mdsr, mddr, decision, b3 = _patch_case()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    decided = decide_propagation(
        requirement_id=mdsr.req_id,
        design_id=mddr.req_id,
        alignment=align,
        decision=decision,
    )
    assert isinstance(decided, PropagationDecisionResult)
    assert decided.decision == "PATCH_EXISTING"


def test_b5c_extend_or_patch_case():
    cr, mdsr, mddr, decision, b3 = _extend_case()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    decided = decide_propagation(
        requirement_id=mdsr.req_id,
        design_id=mddr.req_id,
        alignment=align,
        decision=decision,
    )
    assert decided.decision in {"EXTEND_EXISTING", "PATCH_EXISTING"}
    assert decided.decision != "SKIP"


def test_b5c_skip_case():
    cr, mdsr, mddr, decision, b3 = _skip_case()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    decided = decide_propagation(
        requirement_id=mdsr.req_id,
        design_id=mddr.req_id,
        alignment=align,
        decision=decision,
    )
    assert decided.decision == "SKIP"
    assert "responsibility_mismatch" in (decided.evidence.get("conflicts") or [])


def test_b5c_needs_review_from_b4():
    cr, mdsr, mddr, decision, b3 = _needs_review_b4_case()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    decided = decide_propagation(
        requirement_id=mdsr.req_id,
        design_id=mddr.req_id,
        alignment=align,
        decision=decision,
    )
    assert decided.decision == "NEEDS_REVIEW"


def test_b5c_new_design_case():
    cr, mdsr, mddr, decision, b3 = _new_design_case()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    decided = decide_propagation(
        requirement_id=mdsr.req_id,
        design_id="",
        alignment=align,
        decision=decision,
    )
    assert decided.decision == "NEW_DESIGN_CANDIDATE"
    assert decided.confidence == 0.35


# ---------------------------------------------------------------------------
# D. Legacy façade parity — assess_design_propagation == B5b+B5c
# ---------------------------------------------------------------------------


def test_legacy_assess_façade_parity_all_cases():
    for factory in (
        _patch_case,
        _extend_case,
        _skip_case,
        _needs_review_b4_case,
        _new_design_case,
    ):
        cr, mdsr, mddr, decision, b3 = factory()
        align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
        decided = decide_propagation(
            requirement_id=mdsr.req_id,
            design_id=(mddr.req_id if mddr else ""),
            alignment=align,
            decision=decision,
        )
        prop, pev, conf, reason = assess_design_propagation(
            cr, mdsr, mddr, decision=decision, b3_prior=b3
        )
        assert prop == decided.decision
        assert abs(conf - decided.confidence) < 1e-9
        assert reason == decided.reason
        assert pev.to_dict() == decided.evidence


# ---------------------------------------------------------------------------
# E. build_propagation_plan parity (trace decisions)
# ---------------------------------------------------------------------------


def test_build_propagation_plan_decision_parity():
    cr, mdsr, mddr, decision, b3 = _patch_case()
    blocks = [mdsr, mddr]
    b3_row = {
        "candidate_id": "Req. SynA",
        "document": "MDSR",
        "evidence": {"matched_concepts": b3.get("matched_concepts") or []},
    }
    traces = build_propagation_plan(
        cr, [decision], blocks, b3_decisions=[b3_row], owner_selection_mode="legacy"
    )
    assert len(traces) == 1
    prop, _pev, conf, reason = assess_design_propagation(
        cr, mdsr, mddr, decision=decision, b3_prior=b3
    )
    assert traces[0].propagation_decision == prop
    assert abs(traces[0].confidence - conf) < 1e-9
    # Plan may append no-delta suffix only when aligned without text delta; patch case has delta
    assert traces[0].propagation_reason.startswith(reason.split(" | ")[0])


def test_build_propagation_plan_skip_parity():
    cr, mdsr, mddr, decision, b3 = _skip_case()
    traces = build_propagation_plan(
        cr, [decision], [mdsr, mddr], owner_selection_mode="legacy"
    )
    prop, _, _, reason = assess_design_propagation(
        cr, mdsr, mddr, decision=decision, b3_prior=b3
    )
    assert traces[0].propagation_decision == prop == "SKIP"
    assert traces[0].allow_mdsr_patch is False
    assert traces[0].propagation_reason == reason


# ---------------------------------------------------------------------------
# F. Trace serialization (staged artifacts)
# ---------------------------------------------------------------------------


def test_staged_trace_serialization():
    cr, mdsr, mddr, decision, b3 = _patch_case()
    result = build_propagation_plan(
        cr, [decision], [mdsr, mddr], return_stages=True, owner_selection_mode="legacy"
    )
    assert isinstance(result, tuple)
    traces, staged = result
    assert len(traces) == 1

    cand_entries = staged["design_candidates"]
    assert cand_entries[0]["requirement_id"] == "Req. SynA"
    assert cand_entries[0]["candidate_count"] == 1
    assert cand_entries[0]["candidates"][0]["sources"] == ["same_id"]
    assert cand_entries[0]["candidates"][0]["design_id"] == "Req. SynA"

    align_entries = staged["responsibility_alignment"]
    assert align_entries[0]["requirement_id"] == "Req. SynA"
    assert "evidence" in align_entries[0]
    assert "matched_facets" in align_entries[0]
    assert "confidence" in align_entries[0]
    assert "reason" in align_entries[0]

    dec_entries = staged["propagation_decisions"]
    assert dec_entries[0]["propagation_decision"] == traces[0].propagation_decision
    assert "confidence" in dec_entries[0]
    assert "reason" in dec_entries[0]


def test_default_build_propagation_plan_return_type_unchanged():
    cr, mdsr, mddr, decision, _b3 = _patch_case()
    out = build_propagation_plan(cr, [decision], [mdsr, mddr])
    assert isinstance(out, list)
