# -*- coding: utf-8 -*-
"""B5 staged PR-2: shadow cross-ID discovery — observation only, actual path parity."""

from __future__ import annotations

from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.propagation import (
    SHADOW_CANDIDATE_CAP,
    SOURCE_B3_IMPACTED_MDDR,
    SOURCE_B3_UNCERTAIN_MDDR,
    SOURCE_SAME_ID,
    apply_shadow_candidate_cap,
    assess_design_propagation,
    build_propagation_plan,
    discover_design_candidates,
    discover_design_candidates_shadow,
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
        },
        confidence=kwargs.get("confidence", 0.5),
    )


def _b3_mddr(
    rid: str,
    *,
    judgment: str = "IMPACTED",
    rank: int | None = 3,
    confidence: float = 0.6,
    concepts: list[str] | None = None,
) -> dict:
    return {
        "candidate_id": rid,
        "document": "MDDR",
        "judgment": judgment,
        "retrieval_rank": rank,
        "confidence": confidence,
        "reason": f"synthetic {judgment}",
        "evidence": {"matched_concepts": concepts or ["기록", "상태"]},
    }


# Shared weak same-ID + stronger cross-ID fixture (case K)
def _weak_same_strong_cross():
    cr = (
        "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 "
        "대시보드 목록에서 식별 가능하게 표시한다."
    )
    # same-ID design: auth-code / audit theme — weak CR↔design ownership
    mdsr = _block(
        "Req. SameWeak",
        "인증 코드의 안전한 저장 및 관리",
        "일회성 인증 코드를 생성·저장하고 사용 후 재사용을 금지한다. 조회 이력은 감사 기록으로 남긴다.",
    )
    same_mddr = _block(
        "Req. SameWeak",
        "인증 코드의 안전한 저장 및 관리",
        "patient_code를 생성해 회원가입 검증에 쓰고 사용 상태를 관리한다. 조회 이력은 감사 기록으로 남긴다.",
        "MDDR",
    )
    # cross-ID design: inactivity / dashboard — stronger semantic overlap with CR
    cross_mddr = _block(
        "Req. CrossStrong",
        "비활성 대상 분류 및 대시보드 식별 표시",
        "시스템은 최근 활동 기록이 없는 대상을 별도 상태로 분류하고 대시보드 목록에서 식별 가능하게 표시한다.",
        "MDDR",
    )
    decision = _decision("Req. SameWeak")
    b3 = [
        _b3_mddr("Req. CrossStrong", judgment="IMPACTED", rank=2, concepts=["활동", "기록", "상태", "표시"]),
        {
            "candidate_id": "Req. SameWeak",
            "document": "MDSR",
            "judgment": "IMPACTED",
            "retrieval_rank": 1,
            "confidence": 0.5,
            "evidence": {"matched_concepts": ["기록"]},
        },
    ]
    blocks = [mdsr, same_mddr, cross_mddr]
    return cr, mdsr, same_mddr, cross_mddr, decision, b3, blocks


# ---------------------------------------------------------------------------
# A. same-ID actual path parity
# ---------------------------------------------------------------------------


def test_a_same_id_actual_path_unchanged():
    cr, mdsr, same_mddr, cross_mddr, decision, b3, blocks = _weak_same_strong_cross()
    by_key = {(b.req_id, b.document_type): b for b in blocks}
    actual = discover_design_candidates("Req. SameWeak", by_key)
    assert len(actual) == 1
    assert actual[0].design_id == "Req. SameWeak"
    assert actual[0].sources == [SOURCE_SAME_ID]
    # cross-ID must not appear in actual discovery
    assert all(c.design_id != "Req. CrossStrong" for c in actual)


# ---------------------------------------------------------------------------
# B. B3 IMPACTED MDDR enters shadow pool
# ---------------------------------------------------------------------------


def test_b_b3_impacted_mddr_in_shadow_pool():
    cr, mdsr, same_mddr, cross_mddr, decision, b3, blocks = _weak_same_strong_cross()
    by_key = {(b.req_id, b.document_type): b for b in blocks}
    shadow = discover_design_candidates_shadow(
        "Req. SameWeak", by_key, b3_decisions=b3
    )
    ids = {c.design_id for c in shadow}
    assert "Req. CrossStrong" in ids
    cross = next(c for c in shadow if c.design_id == "Req. CrossStrong")
    assert SOURCE_B3_IMPACTED_MDDR in cross.sources


# ---------------------------------------------------------------------------
# C / D. dedupe + sources merge
# ---------------------------------------------------------------------------


def test_c_d_same_id_and_b3_dedupe_merges_sources():
    mdsr = _block("Req. X", "제목", "본문")
    mddr = _block("Req. X", "제목", "설계 본문", "MDDR")
    by_key = {(mdsr.req_id, "MDSR"): mdsr, (mddr.req_id, "MDDR"): mddr}
    b3 = [_b3_mddr("Req. X", judgment="IMPACTED", rank=1)]
    shadow = discover_design_candidates_shadow("Req. X", by_key, b3_decisions=b3)
    assert len(shadow) == 1
    assert shadow[0].design_id == "Req. X"
    assert SOURCE_SAME_ID in shadow[0].sources
    assert SOURCE_B3_IMPACTED_MDDR in shadow[0].sources


# ---------------------------------------------------------------------------
# E. cross-ID alignment executed in shadow
# ---------------------------------------------------------------------------


def test_e_cross_id_shadow_alignment_executed():
    cr, mdsr, same_mddr, cross_mddr, decision, b3, blocks = _weak_same_strong_cross()
    traces, staged = build_propagation_plan(
        cr, [decision], blocks, b3_decisions=b3, return_stages=True
    )
    aligns = staged["responsibility_alignment_shadow"]
    cross_rows = [a for a in aligns if a["design_id"] == "Req. CrossStrong"]
    assert len(cross_rows) == 1
    assert cross_rows[0]["is_actual_candidate"] is False
    assert "alignment" in cross_rows[0]
    assert "confidence" in cross_rows[0]
    assert "evidence" in cross_rows[0]


# ---------------------------------------------------------------------------
# F / G / H. cross-ID cannot modify actual decision / allow_mdsr_patch / patches
# ---------------------------------------------------------------------------


def test_f_g_h_cross_id_cannot_affect_actual_or_patches():
    cr, mdsr, same_mddr, cross_mddr, decision, b3, blocks = _weak_same_strong_cross()

    # Baseline without B3 MDDR IMPACTED
    traces_no_shadow_src = build_propagation_plan(cr, [decision], [mdsr, same_mddr])
    # With cross-ID in shadow sources
    traces_with, staged = build_propagation_plan(
        cr, [decision], blocks, b3_decisions=b3, return_stages=True
    )
    t0 = traces_no_shadow_src[0]
    t1 = traces_with[0]
    # F: actual propagation decision unchanged
    assert t1.propagation_decision == t0.propagation_decision
    # G: allow_mdsr_patch unchanged
    assert t1.allow_mdsr_patch == t0.allow_mdsr_patch
    # Actual design candidate remains same-ID
    assert "Req. SameWeak" in (t1.design_candidate or t1.impacted_mddr_candidate)
    assert "Req. CrossStrong" not in (t1.design_candidate or "")

    # Shadow still lists cross-ID
    shadow_ids = {
        c["design_id"]
        for entry in staged["design_candidates_shadow"]
        for c in entry["candidates"]
    }
    assert "Req. CrossStrong" in shadow_ids

    # H: patch-eligible Req IDs unchanged
    eligible_no = {t.source_mdsr_req_id for t in traces_no_shadow_src if t.allow_mdsr_patch}
    eligible_yes = {t.source_mdsr_req_id for t in traces_with if t.allow_mdsr_patch}
    assert eligible_no == eligible_yes


# ---------------------------------------------------------------------------
# I. candidate cap
# ---------------------------------------------------------------------------


def test_i_candidate_cap_works():
    mdsr = _block("Req. Cap", "캡", "본문")
    same = _block("Req. Cap", "캡", "설계", "MDDR")
    extras = [
        _block(f"Req. Extra{i}", f"E{i}", f"설계 {i}", "MDDR") for i in range(12)
    ]
    by_key = {(mdsr.req_id, "MDSR"): mdsr, (same.req_id, "MDDR"): same}
    for e in extras:
        by_key[(e.req_id, "MDDR")] = e
    b3 = [
        _b3_mddr(f"Req. Extra{i}", judgment="IMPACTED", rank=i + 1)
        for i in range(12)
    ]
    shadow = discover_design_candidates_shadow(
        "Req. Cap", by_key, b3_decisions=b3, max_candidates=SHADOW_CANDIDATE_CAP
    )
    assert len(shadow) <= SHADOW_CANDIDATE_CAP
    # same_id always retained
    assert any(SOURCE_SAME_ID in c.sources for c in shadow)
    # Cap helper alone
    many = [
        type(shadow[0])(
            requirement_id="Req. Cap",
            design_id=f"Req. Extra{i}",
            document="MDDR",
            sources=[SOURCE_B3_IMPACTED_MDDR],
            retrieval_rank=i,
            block=extras[i] if i < len(extras) else None,
        )
        for i in range(12)
    ]
    capped = apply_shadow_candidate_cap(many, max_candidates=5)
    assert len(capped) == 5


# ---------------------------------------------------------------------------
# J. legacy façade parity
# ---------------------------------------------------------------------------


def test_j_legacy_assess_façade_parity():
    cr, mdsr, same_mddr, _cross, decision, b3, blocks = _weak_same_strong_cross()
    prop_a, pev_a, conf_a, reason_a = assess_design_propagation(
        cr, mdsr, same_mddr, decision=decision
    )
    traces, _staged = build_propagation_plan(
        cr, [decision], blocks, b3_decisions=b3, return_stages=True
    )
    assert traces[0].propagation_decision == prop_a
    assert abs(traces[0].confidence - conf_a) < 1e-9
    # façade result independent of shadow B3 MDDR presence
    traces_plain = build_propagation_plan(cr, [decision], [mdsr, same_mddr])
    assert traces_plain[0].propagation_decision == prop_a
    assert traces_plain[0].allow_mdsr_patch == traces[0].allow_mdsr_patch


# ---------------------------------------------------------------------------
# K. synthetic: weak same-ID + stronger cross-ID → actual unchanged, shadow only
# ---------------------------------------------------------------------------


def test_k_weak_same_strong_cross_shadow_only():
    cr, mdsr, same_mddr, cross_mddr, decision, b3, blocks = _weak_same_strong_cross()
    traces, staged = build_propagation_plan(
        cr, [decision], blocks, b3_decisions=b3, return_stages=True
    )
    # Actual: same-ID decision path (typically SKIP for this mismatch fixture)
    assert traces[0].propagation_decision in {"SKIP", "NEEDS_REVIEW", "EXTEND_EXISTING", "PATCH_EXISTING"}
    # Actual candidate is still same-ID
    assert traces[0].source_mdsr_req_id == "Req. SameWeak"
    assert "Req. CrossStrong" not in (traces[0].design_candidate or "")

    comparison = staged["design_candidate_shadow_comparison"][0]
    assert comparison["actual_candidate"] == "Req. SameWeak"
    assert "does not select a new owner" in comparison["note"].lower()
    shadow_ids = {c["design_id"] for c in comparison["shadow_candidates"]}
    assert "Req. CrossStrong" in shadow_ids
    assert "Req. SameWeak" in shadow_ids

    # Stronger cross may show higher observational confidence — still not selected
    same_row = next(c for c in comparison["shadow_candidates"] if c["design_id"] == "Req. SameWeak")
    cross_row = next(c for c in comparison["shadow_candidates"] if c["design_id"] == "Req. CrossStrong")
    assert same_row["is_actual_candidate"] is True
    assert cross_row["is_actual_candidate"] is False
    # Cross appears only in shadow (already checked); confidence may be higher
    assert "confidence" in cross_row


def test_optional_uncertain_requires_retrieval_evidence():
    mdsr = _block("Req. U", "U", "본문")
    mddr = _block("Req. Ux", "Ux", "설계", "MDDR")
    by_key = {(mdsr.req_id, "MDSR"): mdsr, (mddr.req_id, "MDDR"): mddr}
    # No retrieval_rank → excluded
    weak = [
        {
            "candidate_id": "Req. Ux",
            "document": "MDDR",
            "judgment": "UNCERTAIN",
            "retrieval_rank": None,
            "confidence": 0.9,
            "evidence": {"matched_concepts": ["설계"]},
        }
    ]
    shadow = discover_design_candidates_shadow("Req. U", by_key, b3_decisions=weak)
    assert all(c.design_id != "Req. Ux" for c in shadow)

    strong = [
        _b3_mddr("Req. Ux", judgment="UNCERTAIN", rank=4, confidence=0.4, concepts=["설계"])
    ]
    shadow2 = discover_design_candidates_shadow("Req. U", by_key, b3_decisions=strong)
    hit = next(c for c in shadow2 if c.design_id == "Req. Ux")
    assert SOURCE_B3_UNCERTAIN_MDDR in hit.sources


def test_shadow_trace_serialization_schema():
    cr, mdsr, same_mddr, cross_mddr, decision, b3, blocks = _weak_same_strong_cross()
    _traces, staged = build_propagation_plan(
        cr, [decision], blocks, b3_decisions=b3, return_stages=True
    )
    assert "design_candidates_shadow" in staged
    assert "responsibility_alignment_shadow" in staged
    assert "design_candidate_shadow_comparison" in staged
    assert staged["design_candidates"][0]["path"] == "actual"
    assert staged["design_candidates_shadow"][0]["path"] == "shadow"
