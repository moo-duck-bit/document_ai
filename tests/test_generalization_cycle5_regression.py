# -*- coding: utf-8 -*-
"""Cycle 5 Business Proposal generalization regression tests."""

from pathlib import Path

from document_ai.domain_packs.business_proposal.label_audit import run_business_proposal_label_audit
from document_ai.domain_packs.business_proposal.query_intent import parse_business_proposal_query_intent
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.domain_packs.generic.no_impact_policy import decide_no_impact
from document_ai.domain_packs.generic.query_intent import parse_generic_query_intent
from document_ai.domain_packs.generic.target_existence import decide_target_existence
from document_ai.evaluation.document_set_v2.metrics import domain_breakdown
from document_ai.workflow.analysis import analyze_generic_template_doc

FX_EC = Path("data/eval/document_set_benchmark_v2/fixtures/ec_sw")
FX_BP = Path("data/eval/document_set_benchmark_v2/fixtures/business_proposal/proposal_base.docx")
BENCH = Path("data/eval/document_set_benchmark_v2")

PRIOR = {
    "20260801T062321Z_c70af996",
    "20260801T072116Z_cbdca939",
    "20260801T143206Z_e6bd5201",
    "20260801T152942Z_03c260f2",
    "20260801T163826Z_ab762b81",
}


def test_prior_immutable_runs_include_cycle4():
    assert "20260801T163826Z_ab762b81" in PRIOR
    assert "20260801T152942Z_03c260f2" in PRIOR


def test_bp_label_audit_writes_reports_without_mutating_gold(tmp_path):
    """Cycle 5 shipped this audit as a *proposal-only* tool (it never auto-applies
    changes to gold). At Cycle 5 time every BP case was still placeholder OPTIONAL
    with no node gold, so the audit always proposed >=1 REQUIRED promotion.

    Cycle 6 closed that gap for real via independent structure-derived gold
    (``evaluation.business_proposal_gold``), so REQUIRED/AMBIGUOUS cases now
    already have real ``node_impacts`` gold and are no longer proposal
    candidates (the audit only proposes for ``OPTIONAL`` cases with zero gold
    nodes). The two still-legitimately-OPTIONAL cases (no canonical section /
    document-level requests) remain proposal candidates only if they also lack
    a resolvable template target — this test now asserts the *tool itself*
    still runs cleanly and never mutates gold, rather than asserting the
    stale Cycle 5 "always proposes something" behavior.
    """
    from document_ai.domain_packs.business_proposal.label_audit import write_business_proposal_label_audit

    payload = run_business_proposal_label_audit(benchmark_root=BENCH)
    paths = write_business_proposal_label_audit(tmp_path, benchmark_root=BENCH)
    assert (tmp_path / "business_proposal_node_label_audit.json").is_file()
    assert (tmp_path / "business_proposal_proposed_label_changes.json").is_file()
    assert payload.get("n_proposed_changes", 0) == 0, (
        "Cycle 6 gold already promotes every resolvable BP case to REQUIRED/AMBIGUOUS; "
        "any remaining proposal would indicate a case with real gold was not projected."
    )
    assert paths
    assert payload["notes"] == "Proposals only; gold files are not mutated by this audit."
    elig_before = (BENCH / "development" / "labels" / "node_evaluation_eligibility.jsonl").read_text(
        encoding="utf-8"
    )
    write_business_proposal_label_audit(tmp_path, benchmark_root=BENCH)
    elig_after = (BENCH / "development" / "labels" / "node_evaluation_eligibility.jsonl").read_text(
        encoding="utf-8"
    )
    assert elig_before == elig_after  # audit must never mutate gold
    # Two cases (market_add / style_overall) remain legitimately OPTIONAL (no
    # canonical section to pin gold to) — the file should still show OPTIONAL.
    assert "OPTIONAL" in elig_after


def test_bp_intent_grounding_schedule_top1(tmp_path):
    out = analyze_generic_template_doc(
        document_set="business_proposal",
        change_request="수행 일정 표를 수정",
        uploaded_docs=[
            {"document_id": "PROPOSAL_BASE", "path": str(FX_BP), "filename": "proposal_base.docx"}
        ],
        work_dir=tmp_path,
    )
    top = (out.get("review_required") or [{}])[0]
    assert top.get("node_id") in {
        "business_proposal_v1.schedule",
        "table_00",
        "heading_0001",
    }
    # Prefer template for eval grounding
    assert top.get("node_id") == "business_proposal_v1.schedule" or any(
        r.get("node_id") == "business_proposal_v1.schedule" for r in (out.get("review_required") or [])[:3]
    )


def test_bp_budget_not_confused_with_schedule(tmp_path):
    out = analyze_generic_template_doc(
        document_set="business_proposal",
        change_request="예산 표를 수정",
        uploaded_docs=[
            {"document_id": "PROPOSAL_BASE", "path": str(FX_BP), "filename": "proposal_base.docx"}
        ],
        work_dir=tmp_path,
    )
    top = (out.get("review_required") or [{}])[0]
    assert "schedule" not in str(top.get("node_id") or "").lower() or "budget" in str(top.get("node_id")).lower()
    assert top.get("node_id") == "business_proposal_v1.budget" or any(
        "budget" in str(r.get("node_id") or "") for r in (out.get("review_required") or [])[:2]
    )


def test_bp_artifacts_written(tmp_path):
    analyze_generic_template_doc(
        document_set="business_proposal",
        change_request="위험 관리 수정",
        uploaded_docs=[
            {"document_id": "PROPOSAL_BASE", "path": str(FX_BP), "filename": "proposal_base.docx"}
        ],
        work_dir=tmp_path,
    )
    root = tmp_path / "output" / "document_set" / "business_proposal"
    for name in (
        "business_proposal_query_intent.json",
        "business_proposal_node_ranking_results.json",
        "business_proposal_node_alignments.json",
        "business_proposal_table_analysis.json",
    ):
        assert (root / name).is_file(), name


def test_bp_not_general_report_fallback(tmp_path):
    out = analyze_generic_template_doc(
        document_set="business_proposal",
        change_request="조직 역할 수정",
        uploaded_docs=[
            {"document_id": "PROPOSAL_BASE", "path": str(FX_BP), "filename": "proposal_base.docx"}
        ],
        work_dir=tmp_path,
    )
    assert out.get("template_id") == "business_proposal_v1"
    assert "general_report_v1" not in str(out.get("template_id"))


def test_gr_conclusion_intent_still_works():
    i = parse_generic_query_intent("결론 문단을 수정")
    assert "CONCLUSION" in i.target_section_concepts


def test_ec_sw_stable_identity_still_1():
    names = ["mdtm_base.docx", "mdtm_cols_dtr.docx", "mdtm_note_col.docx"]
    bases = set()
    for name in names:
        idx = index_mdtm_document(source_path=FX_EC / name, document_id=name.upper())
        for n in idx["nodes"]:
            if any("11" in str(x) for x in (n.source_identifiers.get("requirement_ids") or [])):
                bases.add(n.source_identifiers.get("stable_node_id_base"))
                break
    assert len(bases) == 1


def test_gr_no_impact_maintained():
    t = decide_target_existence(
        document_id="D1",
        requested_concepts={"AUTHENTICATION"},
        document_heading_concepts={"SCHEDULE"},
        cr_tokens={"인증"},
        document_heading_tokens={"일정"},
    )
    d = decide_no_impact(document_id="D1", evidences=[], target=t)
    assert d.status == "UNRELATED"


def test_domain_breakdown_reports_required_case_count():
    rows = [
        {"domain": "business_proposal", "mode": "OPTIONAL", "required_top1_hit": False, "e2e_status": "SUCCESS"},
        {"domain": "business_proposal", "mode": "OPTIONAL", "required_top1_hit": False, "e2e_status": "SUCCESS"},
    ]
    out = domain_breakdown(rows)
    bp = out["business_proposal"]
    assert bp.get("required_case_count") == 0
    assert bp.get("required_top1_hit_rate") == 0.0


def test_writer_scope_unchanged_on_bp_nodes(tmp_path):
    out = analyze_generic_template_doc(
        document_set="business_proposal",
        change_request="일정 수정",
        uploaded_docs=[
            {"document_id": "PROPOSAL_BASE", "path": str(FX_BP), "filename": "proposal_base.docx"}
        ],
        work_dir=tmp_path,
    )
    for r in out.get("review_required") or []:
        meta = r.get("metadata") or {}
        assert meta.get("writer_executable") in (False, None)
        assert meta.get("supports_patch") in (False, None)


def test_no_gold_read_in_bp_intent():
    # Intent parser must not take case_id / gold
    i = parse_business_proposal_query_intent("예산 수정")
    assert "gold" not in i.to_dict()
    assert i.preferred_template_node_id == "business_proposal_v1.budget"


def test_bp_required_top1_honest_when_zero_required():
    """Until labels are promoted, REQUIRED Top-1 stays a zero-denominator metric."""
    rows = [{"domain": "business_proposal", "mode": "OPTIONAL", "e2e_status": "SUCCESS", "document_hit": True}]
    m = domain_breakdown(rows)["business_proposal"]
    assert m["required_case_count"] == 0
