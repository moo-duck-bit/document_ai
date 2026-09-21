# -*- coding: utf-8 -*-
"""B5 staged PR-3: evidence provenance / lineage — observational, actual path parity."""

from __future__ import annotations

from document_ai.impact.consistency_gate import ConsistencyDecision
from document_ai.impact.evidence_provenance import (
    EvidenceItem,
    build_alignment_provenance,
    independent_group_for_span,
    is_low_specificity_concept,
    local_token_df,
    summarize_evidence_items,
)
from document_ai.impact.propagation import (
    WEAK_TOKENS,
    align_design_candidate,
    assess_design_propagation,
    build_propagation_plan,
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


def _decision(req_id: str, **kwargs) -> ConsistencyDecision:
    return ConsistencyDecision(
        req_id=req_id,
        document="MDSR",
        status=kwargs.get("status", "CONSISTENT"),
        reason=kwargs.get("reason", "synthetic"),
        allow_auto_patch=kwargs.get("allow_auto_patch", True),
        fields={"description": kwargs.get("description", "기존 설명")},
        evidence={
            "compatible_facets": kwargs.get("compatible_facets", ["actor", "object"]),
            "conflicting_facets": kwargs.get("conflicting_facets", []),
            "missing_information": [],
        },
        confidence=0.5,
    )


def _prior_bleed_fixture():
    """Generic actor/object overlap projected B3→B4→B5."""
    cr = "의료진이 해당 환자의 상태를 확인하고 기록을 관리한다."
    mdsr = _block(
        "Req. Bleed",
        "환자 상태 관리",
        "시스템은 환자의 상태를 관리하고 기록을 제공한다.",
    )
    mddr = _block(
        "Req. Bleed",
        "환자 상태 관리",
        "설계는 환자 상태 데이터를 관리하고 기록을 제공한다.",
        "MDDR",
    )
    decision = _decision(
        "Req. Bleed",
        compatible_facets=["actor", "object", "action"],
    )
    b3 = {
        "matched_concepts": ["환자", "상태", "기록"],
        "behavioral_overlap": {"actor": ["의료진", "환자"], "object": ["상태", "기록"]},
        "candidate_spans": ["의료진이 해당 환자의 상태를 확인하고 기록을 관리한다."],
    }
    return cr, mdsr, mddr, decision, b3


# ---------------------------------------------------------------------------
# A–D: lineage / independent counting
# ---------------------------------------------------------------------------


def test_a_same_source_shares_lineage_across_stages():
    cr, mdsr, mddr, decision, b3 = _prior_bleed_fixture()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    items = align.provenance.get("evidence_items") or []
    # Find CR root for 환자 and B3/B4/B5 derived sharing group
    patient_items = [i for i in items if i.get("concept") == "환자"]
    assert patient_items
    groups = {i["independent_group"] for i in patient_items}
    # Same concept lineage should collapse to few groups (typically 1 span group)
    assert len(groups) <= 2
    derived = [
        i
        for i in items
        if i.get("source_type") in ("B3_DERIVED", "B4_DERIVED")
        and i.get("derived_from")
    ]
    assert derived


def test_b_derived_not_counted_as_independent_direct():
    cr, mdsr, mddr, decision, b3 = _prior_bleed_fixture()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    summary = align.provenance.get("summary") or {}
    derived_n = summary.get("derived_prior_count", 0)
    direct_n = summary.get("direct_independent_count", 0)
    assert derived_n >= 1
    # Derived projections must not inflate direct independent count beyond unique groups
    assert direct_n <= summary.get("unique_independent_group_count", 99)


def test_c_duplicate_concept_same_span_no_inflate():
    span = "의료진이 해당 환자의 상태를 확인하고 기록을 관리한다."
    g1 = independent_group_for_span(span)
    g2 = independent_group_for_span(span)
    assert g1 == g2
    items = [
        EvidenceItem(
            evidence_id="a",
            concept="환자",
            facet="object",
            source_type="CR_DIRECT",
            source_span=span,
            document="CR",
            candidate_id="R",
            independent_group=g1,
            evidence_class="DIRECT",
        ),
        EvidenceItem(
            evidence_id="b",
            concept="환자",
            facet="matched_concept",
            source_type="B3_DERIVED",
            source_span=span,
            document="B3",
            candidate_id="R",
            derived_from=["a"],
            independent_group=g1,
            evidence_class="DERIVED",
        ),
        EvidenceItem(
            evidence_id="c",
            concept="actor",
            facet="actor",
            source_type="B4_DERIVED",
            source_span=span,
            document="B4",
            candidate_id="R",
            derived_from=["a"],
            independent_group=g1,
            evidence_class="DERIVED",
        ),
    ]
    summary = summarize_evidence_items(items)
    assert summary["direct_independent_count"] == 1
    assert summary["derived_prior_count"] == 2


def test_d_two_independent_spans_count_separately():
    g1 = independent_group_for_span("창고 재고가 안전 재고 미만이면 보충 요청을 생성한다.")
    g2 = independent_group_for_span("이벤트 발생 시 구독자에게 알림을 전송한다.")
    assert g1 != g2
    items = [
        EvidenceItem(
            evidence_id="1",
            concept="재고",
            facet="object",
            source_type="CR_DIRECT",
            source_span="창고 재고가 안전 재고 미만이면 보충 요청을 생성한다.",
            document="CR",
            candidate_id="A",
            independent_group=g1,
            evidence_class="DIRECT",
        ),
        EvidenceItem(
            evidence_id="2",
            concept="알림",
            facet="object",
            source_type="CR_DIRECT",
            source_span="이벤트 발생 시 구독자에게 알림을 전송한다.",
            document="CR",
            candidate_id="B",
            independent_group=g2,
            evidence_class="DIRECT",
        ),
    ]
    summary = summarize_evidence_items(items)
    assert summary["direct_independent_count"] == 2


# ---------------------------------------------------------------------------
# E / F: generic + traceability
# ---------------------------------------------------------------------------


def test_e_generic_only_identifiable():
    texts = [
        "환자는 상태를 기록한다.",
        "환자는 상태를 기록한다.",
        "환자는 상태를 기록한다.",
    ]
    df = local_token_df(texts)
    assert is_low_specificity_concept(
        "기록",
        weak_tokens=WEAK_TOKENS,
        local_df=df,
        n_docs=3,
    )
    cr, mdsr, mddr, decision, b3 = _prior_bleed_fixture()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    summary = align.provenance.get("summary") or {}
    assert summary.get("generic_count", 0) >= 1


def test_f_traceability_separate_from_ownership():
    cr, mdsr, mddr, decision, b3 = _prior_bleed_fixture()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    items = align.provenance.get("evidence_items") or []
    trace_items = [i for i in items if i.get("source_type") == "TRACEABILITY"]
    assert trace_items
    assert all("traceability_not_ownership" in (i.get("notes") or []) for i in trace_items)
    assert all(str(i.get("independent_group", "")).startswith("traceability:") for i in trace_items)


# ---------------------------------------------------------------------------
# G: shadow cross-ID provenance
# ---------------------------------------------------------------------------


def test_g_shadow_cross_id_provenance_recorded():
    cr = "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 목록에서 식별한다."
    mdsr = _block("Req. A", "인증 코드 관리", "인증 코드를 저장하고 감사 기록으로 남긴다.")
    same = _block(
        "Req. A",
        "인증 코드 관리",
        "patient_code를 관리하고 감사 기록으로 남긴다.",
        "MDDR",
    )
    cross = _block(
        "Req. B",
        "비활성 대상 분류",
        "최근 활동 기록이 없는 대상을 별도 상태로 분류하고 목록에서 식별한다.",
        "MDDR",
    )
    decision = _decision("Req. A", compatible_facets=["object"])
    b3 = [
        {
            "candidate_id": "Req. B",
            "document": "MDDR",
            "judgment": "IMPACTED",
            "retrieval_rank": 2,
            "confidence": 0.7,
            "evidence": {"matched_concepts": ["활동", "상태"]},
        }
    ]
    _traces, staged = build_propagation_plan(
        cr, [decision], [mdsr, same, cross], b3_decisions=b3, return_stages=True
    )
    comparison = staged["design_candidate_shadow_comparison"][0]
    cross_row = next(
        c for c in comparison["shadow_candidates"] if c["design_id"] == "Req. B"
    )
    assert "direct_independent_count" in cross_row
    assert "derived_prior_count" in cross_row
    assert "unique_independent_groups" in cross_row
    assert "evidence_lineage_summary" in cross_row
    assert staged.get("evidence_provenance", {}).get("evidence_items")


# ---------------------------------------------------------------------------
# H / I / J: actual parity + façade
# ---------------------------------------------------------------------------


def test_h_i_actual_propagation_and_patch_eligibility_parity():
    cr, mdsr, mddr, decision, b3 = _prior_bleed_fixture()
    prop, pev, conf, reason = assess_design_propagation(
        cr, mdsr, mddr, decision=decision, b3_prior=b3
    )
    traces = build_propagation_plan(
        cr,
        [decision],
        [mdsr, mddr],
        b3_decisions=[
            {
                "candidate_id": "Req. Bleed",
                "document": "MDSR",
                "judgment": "IMPACTED",
                "evidence": {
                    "matched_concepts": b3["matched_concepts"],
                    "behavioral_overlap": b3["behavioral_overlap"],
                    "candidate_spans": b3["candidate_spans"],
                },
            }
        ],
    )
    assert traces[0].propagation_decision == prop
    assert abs(traces[0].confidence - conf) < 1e-9
    # Patch eligibility follows actual outcome only
    allow = traces[0].allow_mdsr_patch
    expected_allow = prop in ("PATCH_EXISTING", "EXTEND_EXISTING") and bool(
        traces[0].after_snippet or allow
    )
    # Mirror plan logic: allow only when PATCHED outcome with after snippet
    if traces[0].outcome == "PATCHED":
        assert traces[0].allow_mdsr_patch is True
    else:
        assert traces[0].allow_mdsr_patch is False
    # Provenance present but decision fields intact
    assert "provenance" in (traces[0].structured_evidence or {})


def test_j_legacy_façade_compatibility():
    cr, mdsr, mddr, decision, b3 = _prior_bleed_fixture()
    prop, pev, conf, reason = assess_design_propagation(
        cr, mdsr, mddr, decision=decision, b3_prior=b3
    )
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    from document_ai.impact.propagation import decide_propagation

    decided = decide_propagation(
        requirement_id=mdsr.req_id,
        design_id=mddr.req_id,
        alignment=align,
        decision=decision,
    )
    assert prop == decided.decision
    assert abs(conf - decided.confidence) < 1e-9
    assert reason == decided.reason
    # PropagationEvidence parity (provenance is sidecar on AlignmentResult only)
    assert pev.matched_facets == decided.evidence.get("matched_facets")


# ---------------------------------------------------------------------------
# Synthetic prior-bleed + false-friend
# ---------------------------------------------------------------------------


def test_synthetic_prior_bleed_lineage_not_inflating_direct():
    cr, mdsr, mddr, decision, b3 = _prior_bleed_fixture()
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior=b3)
    summary = align.provenance["summary"]
    items = align.provenance["evidence_items"]
    # b3_prior_* facets exist in matched_facets but are DERIVED in provenance
    prior_proj = [
        i
        for i in items
        if str(i.get("facet", "")).startswith("b3_prior_")
        or "prior_projection" in str(i.get("notes") or [])
    ]
    assert prior_proj
    assert all(i.get("evidence_class") == "DERIVED" for i in prior_proj)
    # Independent direct count must be << raw item count
    assert summary["direct_independent_count"] < len(items)
    assert summary["derived_prior_count"] >= len(prior_proj)


def test_false_friend_surface_match_tracked():
    cr = "최근 활동 기록이 없으면 별도 상태로 표시한다."
    mdsr = _block("Req. FF", "인증 코드 관리", "코드를 저장한다.")
    mddr = _block(
        "Req. FF",
        "인증 코드 관리",
        "조회 이력은 감사 기록으로 남긴다.",
        "MDDR",
    )
    decision = _decision("Req. FF", compatible_facets=["action"])
    align = align_design_candidate(cr, mdsr, mddr, decision=decision, b3_prior={})
    items = align.provenance.get("evidence_items") or []
    # 기록 may appear; divergent spans should be noted when both sides hit
    noted = [i for i in items if "surface_match_divergent_spans" in (i.get("notes") or [])]
    # If action overlap on 기록 exists, notes should flag ambiguity; else still no strong merge
    record_items = [i for i in items if i.get("concept") == "기록"]
    if record_items:
        # Must not all be DIRECT independent without notes/GENERIC/SUPPORTING demotion
        assert any(
            i.get("evidence_class") in ("GENERIC", "SUPPORTING", "DERIVED")
            or i.get("notes")
            for i in record_items
        )
    # Traceability remains separate ownership-wise
    assert any(i.get("source_type") == "TRACEABILITY" for i in items)


def test_build_alignment_provenance_api_direct():
    bundle = build_alignment_provenance(
        cr_text="창고 재고 보충 요청을 생성한다.",
        mdsr_text="재고 모니터링",
        mddr_text="재고 조회 및 보충 요청 생성",
        requirement_id="Req. X",
        design_id="Req. X",
        b3_prior={"matched_concepts": ["재고"], "behavioral_overlap": {"action": ["생성"]}},
        b4_prior={"compatible_facets": ["object"], "conflicting_facets": []},
        matched_facets=["object", "b3_prior_action"],
        matched_responsibilities=["재고"],
        direct_traceability=["same_req_id"],
        conflicts=[],
        actor_shared=[],
        action_cr_mddr=["생성"],
        cr_mddr_content=["재고", "보충"],
        weak_tokens=WEAK_TOKENS,
    )
    assert bundle.summary["derived_prior_count"] >= 1
    assert any(i.source_type == "TRACEABILITY" for i in bundle.evidence_items)
