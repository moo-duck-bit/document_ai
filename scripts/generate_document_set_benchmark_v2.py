# -*- coding: utf-8 -*-
"""
Generate Document Set Benchmark v2 dataset (development + sealed holdout).

Labels are written from document structure / CR intent BEFORE any benchmark prediction.
Does not read v1.4 prediction artifacts to invent gold.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt

from document_ai.evaluation.document_set_v2.holdout_protocol import write_seal_manifest
from document_ai.evaluation.document_set_v2.robustness import req_format_variants, whitespace_variant

REPO = Path(__file__).resolve().parents[1]
V1 = REPO / "data" / "eval" / "document_set_benchmark"
V2 = REPO / "data" / "eval" / "document_set_benchmark_v2"
NOW = datetime.now(timezone.utc).isoformat()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def _mdtm_like(path: Path, rows: list[tuple[str, str, str]], *, title: str = "MDTM") -> None:
    doc = Document()
    doc.add_heading(title, level=1)
    table = doc.add_table(rows=1 + len(rows), cols=4)
    hdr = table.rows[0].cells
    hdr[0].text = "Requirement"
    hdr[1].text = "Design"
    hdr[2].text = "Test"
    hdr[3].text = "Note"
    for i, (req, des, test) in enumerate(rows, start=1):
        cells = table.rows[i].cells
        cells[0].text = req
        cells[1].text = des
        cells[2].text = test
        cells[3].text = ""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def _report_doc(
    path: Path,
    *,
    headings: list[tuple[int, str]],
    include_schedule_table: bool = False,
    schedule_as_list: bool = False,
    schedule_as_paragraph: bool = False,
) -> None:
    doc = Document()
    for level, text in headings:
        doc.add_heading(text, level=level)
        doc.add_paragraph(f"{text} 본문 내용입니다.")
    if include_schedule_table:
        doc.add_heading("일정", level=1)
        t = doc.add_table(rows=3, cols=2)
        t.rows[0].cells[0].text = "단계"
        t.rows[0].cells[1].text = "기간"
        t.rows[1].cells[0].text = "분석"
        t.rows[1].cells[1].text = "2026-Q3"
        t.rows[2].cells[0].text = "구현"
        t.rows[2].cells[1].text = "2026-Q4"
    if schedule_as_list:
        doc.add_heading("추진 일정", level=1)
        doc.add_paragraph("1. 2026-Q3 요구사항", style="List Number")
        doc.add_paragraph("2. 2026-Q4 개발", style="List Number")
    if schedule_as_paragraph:
        doc.add_heading("Schedule", level=1)
        doc.add_paragraph("프로젝트 일정은 2026-Q3부터 2026-Q4까지입니다.")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def _proposal_doc(path: Path, sections: list[str]) -> None:
    doc = Document()
    doc.add_heading("사업 제안서", level=0)
    for s in sections:
        doc.add_heading(s, level=1)
        doc.add_paragraph(f"{s}에 대한 설명입니다.")
        if "예산" in s or "Budget" in s:
            t = doc.add_table(rows=3, cols=2)
            t.rows[0].cells[0].text = "항목"
            t.rows[0].cells[1].text = "금액"
            t.rows[1].cells[0].text = "인건비"
            t.rows[1].cells[1].text = "100"
            t.rows[2].cells[0].text = "장비"
            t.rows[2].cells[1].text = "50"
        if "일정" in s or "Schedule" in s:
            doc.add_paragraph("2026-Q3 착수, 2026-Q4 완료")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def _case(
    *,
    case_id: str,
    domain: str,
    split: str,
    cr: str,
    docs: list[dict],
    enabled: list[str],
    tags: list[str],
    source_type: str = "GENERATED",
    transformation: str | None = None,
    base_case_id: str | None = None,
    notes: str = "",
    fixture_fp: str | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "domain": domain,
        "document_set_id": domain,
        "change_request": cr,
        "split": split,
        "input_documents": docs,
        "enabled_documents": enabled,
        "expected_status": "SUCCESS",
        "tags": tags,
        "difficulty": "medium",
        "notes": notes,
        "source_type": source_type,
        "transformation": transformation,
        "base_case_id": base_case_id,
        "fixture_fingerprint": fixture_fp,
        "sanitization_status": "N/A",
    }


def _doc_label(case_id: str, document_id: str, status: str) -> dict:
    return {
        "case_id": case_id,
        "document_id": document_id,
        "gold_status": status,
        "review_notes": "structure_based_pre_prediction_label",
    }


def _elig(case_id: str, domain: str, document_id: str, mode: str, primary: str | None = None, groups=None) -> dict:
    return {
        "case_id": case_id,
        "domain": domain,
        "document_id": document_id,
        "node_evaluation_mode": mode,
        "primary_node_id": primary,
        "acceptable_node_ids": [primary] if primary and mode == "AMBIGUOUS" else [],
        "acceptable_node_groups": groups or ([] if mode != "AMBIGUOUS" else [[primary] if primary else []]),
        "label_rationale": "pre_prediction_fixture_structure",
        "labeled_by": "benchmark_v2_generator",
        "labeled_at": NOW,
        "confidence": 0.85,
    }


def _writer(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "should_write": False,
        "expected_result_status": "GATED",
        "original_must_remain_unchanged": True,
        "expected_changed_document_ids": [],
        "format_preservation_required": True,
    }


def _node(case_id: str, document_id: str, node_id: str, status: str, mode: str) -> dict:
    return {
        "case_id": case_id,
        "document_id": document_id,
        "node_id": node_id,
        "gold_status": status,
        "node_evaluation_mode": mode,
        "primary_node_id": node_id,
        "acceptable_node_ids": [],
        "acceptable_node_groups": [],
        "label_rationale": "pre_prediction_fixture_structure",
        "labeled_by": "benchmark_v2_generator",
        "labeled_at": NOW,
        "confidence": 0.85,
    }


def main() -> None:
    if V2.exists():
        shutil.rmtree(V2)
    fx = V2 / "fixtures"
    # --- shared fixtures ---
    mdtm_rows = [
        ("Req. 10", "5.1.1", "TC-10"),
        ("Req. 11", "5.1.2", "TC-11"),
        ("Req. 12", "5.1.3", "TC-12"),
        ("Req. 101", "6.0.1", "TC-101"),
    ]
    _mdtm_like(fx / "ec_sw" / "mdtm_base.docx", mdtm_rows, title="Traceability Matrix")
    _mdtm_like(
        fx / "ec_sw" / "mdtm_reordered_cols.docx",
        mdtm_rows,
        title="Traceability Matrix Reordered",
    )
    # empty row variant: insert blank requirement row in middle via extra empty-ish
    _mdtm_like(
        fx / "ec_sw" / "mdtm_with_gap.docx",
        [("Req. 10", "5.1.1", "TC-10"), ("", "", ""), ("Req. 11", "5.1.2", "TC-11")],
        title="MDTM Gap",
    )
    _mdtm_like(
        fx / "ec_sw" / "mdtm_dup_req.docx",
        [("Req. 11", "5.1.2", "TC-11"), ("Req. 11", "5.1.2b", "TC-11B")],
        title="MDTM Dup",
    )
    shutil.copy2(fx / "ec_sw" / "mdtm_base.docx", fx / "ec_sw" / "uploaded_trace_matrix.docx")
    shutil.copy2(fx / "ec_sw" / "mdtm_base.docx", fx / "ec_sw" / "copy_a.docx")
    shutil.copy2(fx / "ec_sw" / "mdtm_base.docx", fx / "ec_sw" / "copy_b.docx")

    _report_doc(
        fx / "general_report" / "report_std.docx",
        headings=[(1, "요약"), (1, "방법론"), (1, "결과"), (1, "결론")],
    )
    _report_doc(
        fx / "general_report" / "report_schedule_table.docx",
        headings=[(1, "배경"), (1, "목표")],
        include_schedule_table=True,
    )
    _report_doc(
        fx / "general_report" / "report_schedule_list.docx",
        headings=[(1, "배경")],
        schedule_as_list=True,
    )
    _report_doc(
        fx / "general_report" / "report_schedule_para.docx",
        headings=[(1, "Background")],
        schedule_as_paragraph=True,
    )
    _report_doc(
        fx / "general_report" / "report_en_headings.docx",
        headings=[(1, "Methodology"), (1, "Results"), (1, "Conclusion"), (1, "Schedule")],
    )
    _report_doc(
        fx / "general_report" / "report_dup_results.docx",
        headings=[(1, "결과"), (2, "세부 결과"), (1, "결과")],
    )
    _report_doc(
        fx / "general_report" / "report_mixed.docx",
        headings=[(1, "방법론 Methodology"), (1, "Results 결과")],
    )

    _proposal_doc(
        fx / "business_proposal" / "proposal_base.docx",
        ["실행 일정", "예산", "위험 관리", "수행 조직", "기대 효과"],
    )
    _proposal_doc(
        fx / "business_proposal" / "proposal_dup_schedule.docx",
        ["실행 일정", "예산", "추진 일정"],
    )
    _proposal_doc(
        fx / "business_proposal" / "proposal_en.docx",
        ["Execution Schedule", "Budget", "Risk Management"],
    )

    mdtm_fp = _sha(fx / "ec_sw" / "mdtm_base.docx")

    # Index node ids for labeling (structure only — not change POC prediction)
    from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document

    indexed = index_mdtm_document(
        source_path=fx / "ec_sw" / "mdtm_base.docx", document_id="MDTM"
    )
    nodes = list(indexed.get("nodes") or [])
    by_req = {}
    for n in nodes:
        for r in n.source_identifiers.get("requirement_ids") or []:
            by_req[r] = n.node_id
    req11 = by_req.get("Req. 11")
    req10 = by_req.get("Req. 10")
    req101 = by_req.get("Req. 101")
    design_node = None
    for n in nodes:
        if "5.1.2" in (n.source_identifiers.get("design_ids") or []):
            design_node = n.node_id
            break
    test_node = None
    for n in nodes:
        if "TC-12" in [str(x).upper() for x in (n.source_identifiers.get("test_ids") or [])]:
            test_node = n.node_id
            break

    # --- Development cases (20+) ---
    dev_cases: list[dict] = []
    hold_cases: list[dict] = []
    metamorphic: list[dict] = []

    def add_ec(split: str, case_id: str, cr: str, fixture: str, tags: list[str], **kw):
        docs = [
            {
                "path": f"fixtures/ec_sw/{fixture}",
                "filename": fixture,
                "role": "traceability",
            }
        ]
        c = _case(
            case_id=case_id,
            domain="ec_sw",
            split=split,
            cr=cr,
            docs=docs,
            enabled=["MDTM"],
            tags=tags,
            fixture_fp=_sha(fx / "ec_sw" / fixture),
            **kw,
        )
        (dev_cases if split == "development" else hold_cases).append(c)
        return c

    # Development EC-SW (12)
    add_ec("development", "v2_dev_ec_req11_exact", "Req. 11 추적성 행 갱신", "mdtm_base.docx", ["exact_id"])
    add_ec("development", "v2_dev_ec_req_space", "Req 11 추적성 행 갱신", "mdtm_base.docx", ["identifier_variation"], transformation="req_space", base_case_id="v2_dev_ec_req11_exact")
    add_ec("development", "v2_dev_ec_req_dash", "REQ-11 추적성 행 갱신", "mdtm_base.docx", ["identifier_variation"], transformation="req_dash", base_case_id="v2_dev_ec_req11_exact")
    add_ec("development", "v2_dev_ec_ws", whitespace_variant("Req. 11 추적성 행 갱신"), "mdtm_base.docx", ["whitespace"], transformation="whitespace", base_case_id="v2_dev_ec_req11_exact")
    add_ec("development", "v2_dev_ec_design_only", "설계 ID 5.1.2 관련 검토", "mdtm_base.docx", ["design_id"])
    add_ec("development", "v2_dev_ec_test_only", "시험 TC-12 결과 반영 검토", "mdtm_base.docx", ["test_id"])
    add_ec("development", "v2_dev_ec_mixed", "Req. 10 및 설계 5.1.1 연계 검토", "mdtm_base.docx", ["mixed"])
    add_ec("development", "v2_dev_ec_dup_rows", "Req. 11 중복 행 확인", "mdtm_dup_req.docx", ["duplicate_rows"])
    add_ec("development", "v2_dev_ec_gap_row", "Req. 11 갱신", "mdtm_with_gap.docx", ["empty_row"])
    add_ec("development", "v2_dev_ec_no_impact", "마케팅 브로슈어 문구 변경", "mdtm_base.docx", ["no_impact"])
    add_ec("development", "v2_dev_ec_semantic", "사용자 인증 정책 강화 필요", "mdtm_base.docx", ["semantic"])
    add_ec("development", "v2_dev_ec_bad_name", "Req. 101 갱신", "uploaded_trace_matrix.docx", ["filename_no_short_id"])
    add_ec("development", "v2_dev_ec_file_order_a", "Req. 10 갱신", "copy_a.docx", ["file_order"], transformation="file_order", base_case_id="v2_dev_ec_file_order_a")
    # multi upload order pair
    c_order = _case(
        case_id="v2_dev_ec_file_order_b",
        domain="ec_sw",
        split="development",
        cr="Req. 10 갱신",
        docs=[
            {"path": "fixtures/ec_sw/copy_b.docx", "filename": "copy_b.docx", "role": "traceability"},
            {"path": "fixtures/ec_sw/copy_a.docx", "filename": "copy_a.docx", "role": "traceability"},
        ],
        enabled=["MDTM"],
        tags=["file_order"],
        transformation="file_order",
        base_case_id="v2_dev_ec_file_order_a",
        fixture_fp=mdtm_fp,
    )
    dev_cases.append(c_order)

    metamorphic.extend(
        [
            {"pair_id": "mp_req_space", "base_case_id": "v2_dev_ec_req11_exact", "variant_case_id": "v2_dev_ec_req_space", "transformation": "identifier_req_space", "expected_relation": "same_document_decision"},
            {"pair_id": "mp_req_dash", "base_case_id": "v2_dev_ec_req11_exact", "variant_case_id": "v2_dev_ec_req_dash", "transformation": "identifier_req_dash", "expected_relation": "same_document_decision"},
            {"pair_id": "mp_ws", "base_case_id": "v2_dev_ec_req11_exact", "variant_case_id": "v2_dev_ec_ws", "transformation": "whitespace", "expected_relation": "same_document_decision"},
            {"pair_id": "mp_file_order", "base_case_id": "v2_dev_ec_file_order_a", "variant_case_id": "v2_dev_ec_file_order_b", "transformation": "file_order", "expected_relation": "same_document_decision"},
        ]
    )

    # Development GR (8)
    def add_gr(split, case_id, cr, fixture, tags, enabled="REPORT_BASE", **kw):
        c = _case(
            case_id=case_id,
            domain="general_report",
            split=split,
            cr=cr,
            docs=[{"path": f"fixtures/general_report/{fixture}", "filename": fixture, "role": "general_report"}],
            enabled=[enabled],
            tags=tags,
            fixture_fp=_sha(fx / "general_report" / fixture),
            **kw,
        )
        (dev_cases if split == "development" else hold_cases).append(c)

    add_gr("development", "v2_dev_gr_method", "방법론 데이터 출처 보완", "report_std.docx", ["section"])
    add_gr("development", "v2_dev_gr_results", "결과 핵심 발견 수정", "report_std.docx", ["section"])
    add_gr("development", "v2_dev_gr_schedule_table", "일정 표 2026-Q4 수정", "report_schedule_table.docx", ["schedule", "table"])
    add_gr("development", "v2_dev_gr_schedule_list", "추진 일정 목록 수정", "report_schedule_list.docx", ["schedule", "list"])
    add_gr("development", "v2_dev_gr_schedule_para", "Schedule timeline update 2026-Q4", "report_schedule_para.docx", ["schedule", "paragraph", "heading_en"])
    add_gr("development", "v2_dev_gr_dup", "결과 섹션 정리", "report_dup_results.docx", ["duplicate_heading"])
    add_gr("development", "v2_dev_gr_missing", "부록 통계표 추가 요청", "report_std.docx", ["missing_section"])
    add_gr("development", "v2_dev_gr_no_impact", "표지 디자인 색상 변경", "report_std.docx", ["no_impact"])
    add_gr("development", "v2_dev_gr_mixed", "방법론 Methodology 보완", "report_mixed.docx", ["heading_mixed"])

    metamorphic.append(
        {
            "pair_id": "mp_heading_schedule",
            "base_case_id": "v2_dev_gr_schedule_table",
            "variant_case_id": "v2_dev_gr_schedule_list",
            "transformation": "heading_schedule_structure",
            "expected_relation": "same_document_decision",
        }
    )

    # Development Business Proposal (8)
    def add_bp(split, case_id, cr, fixture, tags, **kw):
        c = _case(
            case_id=case_id,
            domain="business_proposal",
            split=split,
            cr=cr,
            docs=[{"path": f"fixtures/business_proposal/{fixture}", "filename": fixture, "role": "general_report"}],
            enabled=["REPORT_BASE"],
            tags=tags,
            fixture_fp=_sha(fx / "business_proposal" / fixture),
            **kw,
        )
        (dev_cases if split == "development" else hold_cases).append(c)

    add_bp("development", "v2_dev_bp_schedule", "실행 일정 2026-Q4 조정", "proposal_base.docx", ["schedule"])
    add_bp("development", "v2_dev_bp_budget", "예산 표 인건비 수정", "proposal_base.docx", ["budget", "table"])
    add_bp("development", "v2_dev_bp_risk", "위험 관리 항목 추가", "proposal_base.docx", ["risk"])
    add_bp("development", "v2_dev_bp_org", "수행 조직 역할 변경", "proposal_base.docx", ["org"])
    add_bp("development", "v2_dev_bp_effect", "기대 효과 문구 보완", "proposal_base.docx", ["effect"])
    add_bp("development", "v2_dev_bp_dup_sched", "일정 섹션 중복 정리", "proposal_dup_schedule.docx", ["duplicate_schedule"])
    add_bp("development", "v2_dev_bp_en", "Budget table update", "proposal_en.docx", ["en", "budget"])
    add_bp("development", "v2_dev_bp_no_impact", "표지 로고 위치 변경", "proposal_base.docx", ["no_impact"])

    # Holdout EC-SW (10) — sealed labels, different CRs/fixtures intent
    add_ec("holdout", "v2_hol_ec_req10", "Req. 10 행 검토", "mdtm_base.docx", ["exact_id", "holdout"])
    add_ec("holdout", "v2_hol_ec_req101", "Req. 101 추적성 갱신", "mdtm_base.docx", ["exact_id", "holdout"])
    add_ec("holdout", "v2_hol_ec_design", "설계 5.1.3 검토", "mdtm_base.docx", ["design_id", "holdout"])
    add_ec("holdout", "v2_hol_ec_test", "시험 TC-11 검토", "mdtm_base.docx", ["test_id", "holdout"])
    add_ec("holdout", "v2_hol_ec_mixed", "Req. 12 및 TC-12 연계", "mdtm_base.docx", ["mixed", "holdout"])
    add_ec("holdout", "v2_hol_ec_dup", "Req. 11 중복 확인", "mdtm_dup_req.docx", ["duplicate", "holdout"])
    add_ec("holdout", "v2_hol_ec_gap", "Req. 10 갱신", "mdtm_with_gap.docx", ["gap", "holdout"])
    add_ec("holdout", "v2_hol_ec_semantic", "접근통제 강화 요청", "mdtm_base.docx", ["semantic", "holdout"])
    add_ec("holdout", "v2_hol_ec_no_impact", "사내 행사 공지 문구", "mdtm_base.docx", ["no_impact", "holdout"])
    add_ec("holdout", "v2_hol_ec_malformed", "REQ11 잘못된 표기", "mdtm_base.docx", ["malformed", "holdout"])

    # Holdout GR (6)
    add_gr("holdout", "v2_hol_gr_concl", "결론 권고사항 수정", "report_std.docx", ["holdout"])
    add_gr("holdout", "v2_hol_gr_sched_t", "일정 표 수정", "report_schedule_table.docx", ["holdout", "schedule"])
    add_gr("holdout", "v2_hol_gr_en", "Results section update", "report_en_headings.docx", ["holdout", "en"])
    add_gr("holdout", "v2_hol_gr_dup", "결과 중복 헤딩 정리", "report_dup_results.docx", ["holdout"])
    add_gr("holdout", "v2_hol_gr_missing", "참고문헌 DOI 추가", "report_std.docx", ["holdout", "missing"])
    add_gr("holdout", "v2_hol_gr_no_impact", "문서 여백 조정", "report_std.docx", ["holdout", "no_impact"])

    # Holdout BP (4)
    add_bp("holdout", "v2_hol_bp_sched", "실행 일정 변경", "proposal_base.docx", ["holdout"])
    add_bp("holdout", "v2_hol_bp_budget", "예산 장비비 수정", "proposal_base.docx", ["holdout"])
    add_bp("holdout", "v2_hol_bp_risk", "위험 관리 완화책", "proposal_base.docx", ["holdout"])
    add_bp("holdout", "v2_hol_bp_no_impact", "표지 폰트만 변경", "proposal_base.docx", ["holdout", "no_impact"])

    assert len(dev_cases) >= 20, len(dev_cases)
    assert len(hold_cases) >= 20, len(hold_cases)

    # Write case files
    for c in dev_cases:
        domain = c["domain"]
        sub = {"ec_sw": "ec_sw", "general_report": "general_report", "business_proposal": "business_proposal"}[domain]
        _write_json(V2 / "development" / "cases" / sub / f"{c['case_id']}.json", c)
    for c in hold_cases:
        domain = c["domain"]
        sub = {"ec_sw": "ec_sw", "general_report": "general_report", "business_proposal": "business_proposal"}[domain]
        _write_json(V2 / "holdout" / "cases" / sub / f"{c['case_id']}.json", c)

    def labels_for(cases: list[dict], *, use_nodes: bool) -> dict[str, list]:
        docs, nodes, elig, writers = [], [], [], []
        for c in cases:
            cid = c["case_id"]
            tags = set(c.get("tags") or [])
            domain = c["domain"]
            writers.append(_writer(cid))
            if domain == "ec_sw":
                doc_id = "MDTM"
                if "no_impact" in tags or "malformed" in tags:
                    docs.append(_doc_label(cid, doc_id, "UNRELATED"))
                    elig.append(_elig(cid, domain, doc_id, "NOT_APPLICABLE"))
                elif "semantic" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    elig.append(_elig(cid, domain, doc_id, "OPTIONAL"))
                elif "design_id" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    elig.append(_elig(cid, domain, doc_id, "REQUIRED", design_node))
                    if use_nodes and design_node:
                        nodes.append(_node(cid, doc_id, design_node, "REVIEW_REQUIRED", "REQUIRED"))
                elif "test_id" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    primary = test_node or req11
                    elig.append(_elig(cid, domain, doc_id, "REQUIRED", primary))
                    if use_nodes and primary:
                        nodes.append(_node(cid, doc_id, primary, "REVIEW_REQUIRED", "REQUIRED"))
                elif "duplicate" in tags or "duplicate_rows" in tags:
                    docs.append(_doc_label(cid, doc_id, "IMPACTED"))
                    elig.append(_elig(cid, domain, doc_id, "REQUIRED", req11))
                    if use_nodes and req11:
                        nodes.append(_node(cid, doc_id, req11, "PATCH_CANDIDATE", "REQUIRED"))
                else:
                    # exact / mixed / gap / filename
                    docs.append(_doc_label(cid, doc_id, "IMPACTED"))
                    primary = req11
                    if "Req. 10" in c["change_request"] or "REQ-10" in c["change_request"]:
                        primary = req10
                    if "Req. 101" in c["change_request"]:
                        primary = req101
                    if "Req. 12" in c["change_request"]:
                        primary = by_req.get("Req. 12")
                    elig.append(_elig(cid, domain, doc_id, "REQUIRED", primary))
                    if use_nodes and primary:
                        nodes.append(_node(cid, doc_id, primary, "PATCH_CANDIDATE", "REQUIRED"))
            elif domain == "general_report":
                doc_id = "REPORT_BASE"
                if "no_impact" in tags:
                    docs.append(_doc_label(cid, doc_id, "UNRELATED"))
                    elig.append(_elig(cid, domain, doc_id, "NOT_APPLICABLE"))
                elif "missing" in tags or "missing_section" in tags:
                    docs.append(_doc_label(cid, doc_id, "UNRELATED"))
                    elig.append(_elig(cid, domain, doc_id, "NOT_APPLICABLE"))
                elif "schedule" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    nid = "general_report_v1.schedule"
                    elig.append(
                        _elig(
                            cid,
                            domain,
                            doc_id,
                            "AMBIGUOUS",
                            nid,
                            groups=[[nid]],
                        )
                    )
                    if use_nodes:
                        nodes.append(_node(cid, doc_id, nid, "REVIEW_REQUIRED", "AMBIGUOUS"))
                else:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    # map keywords to template sections
                    cr = c["change_request"]
                    if "방법" in cr or "Method" in cr:
                        nid = "general_report_v1.methodology"
                    elif "결과" in cr or "Result" in cr:
                        nid = "general_report_v1.results"
                    elif "결론" in cr or "Conclusion" in cr:
                        nid = "general_report_v1.conclusion"
                    else:
                        nid = "general_report_v1.results"
                    mode = "AMBIGUOUS" if "duplicate" in tags else "REQUIRED"
                    elig.append(_elig(cid, domain, doc_id, mode, nid, groups=[[nid]] if mode == "AMBIGUOUS" else None))
                    if use_nodes:
                        nodes.append(_node(cid, doc_id, nid, "REVIEW_REQUIRED", mode))
            else:  # business_proposal
                doc_id = "REPORT_BASE"
                if "no_impact" in tags:
                    docs.append(_doc_label(cid, doc_id, "UNRELATED"))
                    elig.append(_elig(cid, domain, doc_id, "NOT_APPLICABLE"))
                else:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    elig.append(_elig(cid, domain, doc_id, "OPTIONAL"))
            # business proposal: optional grounding (new domain)
        return {"docs": docs, "nodes": nodes, "elig": elig, "writers": writers}

    # Fix business proposal enabled document — workflow may use first uploaded id.
    # Keep REPORT_BASE as evaluation doc id used by generic analyzer when single upload.
    # Actually generic uses uploaded_docs[0]["document_id"] — need to check create_workflow document_id assignment.

    # For labeling, document_impacts document_id must match prediction. Check workflow naming...
    # From v1 GR cases: enabled REPORT_BASE and gold uses REPORT_BASE.
    # create_workflow likely sets document_id from filename stem upper.

    # Safer: leave enabled as filename-derived; gold document_id will be resolved at eval time.
    # Looking at v1 fixture report_base.docx → REPORT_BASE.
    # proposal_base.docx → PROPOSAL_BASE perhaps!

    # Fix BP gold document ids to stem upper
    def fix_bp_enabled():
        for c in dev_cases + hold_cases:
            if c["domain"] != "business_proposal":
                continue
            stem = Path(c["input_documents"][0]["filename"]).stem.upper()
            c["enabled_documents"] = [stem]

    fix_bp_enabled()

    def labels_for_fixed(cases: list[dict]) -> dict[str, list]:
        docs, nodes, elig, writers = [], [], [], []
        for c in cases:
            cid = c["case_id"]
            tags = set(c.get("tags") or [])
            domain = c["domain"]
            writers.append(_writer(cid))
            if domain == "ec_sw":
                doc_id = "MDTM"
                # filename variants still MDTM role — prediction may use stem
                stem = Path(c["input_documents"][0]["filename"]).stem.upper()
                # Prefer enabled
                doc_id = (c.get("enabled_documents") or [stem])[0]
                # Keep MDTM for base fixture predictions when filename is mdtm_base → MDTM_BASE
                # Observational registry may still say MDTM; uploaded id is stem.
                doc_id = stem
                c["enabled_documents"] = [doc_id]
                if "no_impact" in tags or "malformed" in tags:
                    docs.append(_doc_label(cid, doc_id, "UNRELATED"))
                    elig.append(_elig(cid, domain, doc_id, "NOT_APPLICABLE"))
                elif "semantic" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    elig.append(_elig(cid, domain, doc_id, "OPTIONAL"))
                elif "design_id" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    elig.append(_elig(cid, domain, doc_id, "REQUIRED", design_node))
                    if design_node:
                        nodes.append(_node(cid, doc_id, design_node, "REVIEW_REQUIRED", "REQUIRED"))
                elif "test_id" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    primary = test_node or req11
                    elig.append(_elig(cid, domain, doc_id, "REQUIRED", primary))
                    if primary:
                        nodes.append(_node(cid, doc_id, primary, "REVIEW_REQUIRED", "REQUIRED"))
                else:
                    docs.append(_doc_label(cid, doc_id, "IMPACTED"))
                    primary = req11
                    cr = c["change_request"]
                    if "Req. 10" in cr or "Req 10" in cr or "REQ-10" in cr:
                        primary = req10
                    if "101" in cr:
                        primary = req101
                    if "Req. 12" in cr or "REQ-12" in cr:
                        primary = by_req.get("Req. 12")
                    elig.append(_elig(cid, domain, doc_id, "REQUIRED", primary))
                    if primary:
                        status = "PATCH_CANDIDATE"
                        if "design" in tags or "test_id" in tags:
                            status = "REVIEW_REQUIRED"
                        nodes.append(_node(cid, doc_id, primary, status, "REQUIRED"))
            elif domain == "general_report":
                doc_id = Path(c["input_documents"][0]["filename"]).stem.upper()
                c["enabled_documents"] = [doc_id]
                if "no_impact" in tags or "missing" in tags or "missing_section" in tags:
                    docs.append(_doc_label(cid, doc_id, "UNRELATED"))
                    elig.append(_elig(cid, domain, doc_id, "NOT_APPLICABLE"))
                elif "schedule" in tags:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    nid = "general_report_v1.schedule"
                    elig.append(_elig(cid, domain, doc_id, "AMBIGUOUS", nid, groups=[[nid]]))
                    nodes.append(_node(cid, doc_id, nid, "REVIEW_REQUIRED", "AMBIGUOUS"))
                else:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    cr = c["change_request"]
                    if "방법" in cr or "Method" in cr:
                        nid = "general_report_v1.methodology"
                    elif "결론" in cr or "Conclusion" in cr:
                        nid = "general_report_v1.conclusion"
                    else:
                        nid = "general_report_v1.results"
                    mode = "AMBIGUOUS" if "duplicate" in tags else "REQUIRED"
                    elig.append(_elig(cid, domain, doc_id, mode, nid, groups=[[nid]] if mode == "AMBIGUOUS" else None))
                    nodes.append(_node(cid, doc_id, nid, "REVIEW_REQUIRED", mode))
            else:
                doc_id = Path(c["input_documents"][0]["filename"]).stem.upper()
                c["enabled_documents"] = [doc_id]
                if "no_impact" in tags:
                    docs.append(_doc_label(cid, doc_id, "UNRELATED"))
                    elig.append(_elig(cid, domain, doc_id, "NOT_APPLICABLE"))
                else:
                    docs.append(_doc_label(cid, doc_id, "REVIEW_REQUIRED"))
                    elig.append(_elig(cid, domain, doc_id, "OPTIONAL"))
        return {"docs": docs, "nodes": nodes, "elig": elig, "writers": writers}

    # rewrite cases with updated enabled_documents
    for c in dev_cases:
        domain = c["domain"]
        sub = {"ec_sw": "ec_sw", "general_report": "general_report", "business_proposal": "business_proposal"}[domain]
        # update enabled from filename
        c["enabled_documents"] = [Path(c["input_documents"][0]["filename"]).stem.upper()]
        _write_json(V2 / "development" / "cases" / sub / f"{c['case_id']}.json", c)
    for c in hold_cases:
        domain = c["domain"]
        sub = {"ec_sw": "ec_sw", "general_report": "general_report", "business_proposal": "business_proposal"}[domain]
        c["enabled_documents"] = [Path(c["input_documents"][0]["filename"]).stem.upper()]
        _write_json(V2 / "holdout" / "cases" / sub / f"{c['case_id']}.json", c)

    # Multi-doc file_order_b enabled
    for c in dev_cases:
        if c["case_id"] == "v2_dev_ec_file_order_b":
            c["enabled_documents"] = ["COPY_B"]
            _write_json(V2 / "development" / "cases" / "ec_sw" / f"{c['case_id']}.json", c)

    lab_dev = labels_for_fixed(dev_cases)
    lab_hol = labels_for_fixed(hold_cases)

    _write_jsonl(V2 / "development" / "labels" / "document_impacts.jsonl", lab_dev["docs"])
    _write_jsonl(V2 / "development" / "labels" / "node_impacts.jsonl", lab_dev["nodes"])
    _write_jsonl(V2 / "development" / "labels" / "node_evaluation_eligibility.jsonl", lab_dev["elig"])
    _write_jsonl(V2 / "development" / "labels" / "writer_expectations.jsonl", lab_dev["writers"])
    _write_jsonl(V2 / "development" / "labels" / "patch_expectations.jsonl", [])

    sealed = V2 / "holdout" / "sealed_labels"
    _write_jsonl(sealed / "document_impacts.jsonl", lab_hol["docs"])
    _write_jsonl(sealed / "node_impacts.jsonl", lab_hol["nodes"])
    _write_jsonl(sealed / "node_evaluation_eligibility.jsonl", lab_hol["elig"])
    _write_jsonl(sealed / "writer_expectations.jsonl", lab_hol["writers"])
    _write_jsonl(sealed / "patch_expectations.jsonl", [])

    write_seal_manifest(
        holdout_dir=V2 / "holdout",
        sealed_labels_dir=sealed,
        out_path=V2 / "holdout" / "holdout_label_manifest.json",
    )

    _write_jsonl(V2 / "metamorphic_pairs.jsonl", metamorphic)

    # human review forms
    hr = V2 / "human_review"
    hr.mkdir(parents=True, exist_ok=True)
    (hr / "review_guideline.md").write_text(
        "# Human Review Guideline\n\nScore 1–5 on understanding, evidence, diff clarity, trust.\nMark PASS/PARTIAL/FAIL separately from automatic metrics.\n",
        encoding="utf-8",
    )
    forms = []
    for c in hold_cases[:10]:
        forms.append(
            {
                "case_id": c["case_id"],
                "change_request_understanding": None,
                "impacted_docs_appropriateness": None,
                "node_evidence_appropriateness": None,
                "review_reason_plausibility": None,
                "diff_clarity": None,
                "proposed_change_accuracy": None,
                "unnecessary_change": None,
                "overall_trust": None,
                "verdict": None,
            }
        )
    _write_jsonl(hr / "review_form.jsonl", forms)

    # Copy fixtures into V2 (already under V2/fixtures)
    # Manifest
    def rel_cases(cases, split):
        out = []
        for c in cases:
            domain = c["domain"]
            sub = {"ec_sw": "ec_sw", "general_report": "general_report", "business_proposal": "business_proposal"}[domain]
            out.append(f"{split}/cases/{sub}/{c['case_id']}.json")
        return out

    manifest = {
        "meta": {
            "name": "document_set_benchmark_v2",
            "version": "2.0",
            "development_count": len(dev_cases),
            "holdout_count": len(hold_cases),
            "regression_count": 24,
            "domains": ["ec_sw", "general_report", "business_proposal"],
            "generated_at": NOW,
            "note": "Holdout labels sealed before prediction; regression references v1 immutable set.",
        },
        "regression_manifest": str(V1 / "manifest.json").replace("\\", "/"),
        "development_cases": rel_cases(dev_cases, "development"),
        "holdout_cases": rel_cases(hold_cases, "holdout"),
    }
    _write_json(V2 / "manifest.json", manifest)

    # Also copy fixtures path referenced as fixtures/... from V2 root — cases use fixtures/...
    # cases paths are fixtures/ec_sw/... relative to V2 root — good (fixtures already at V2/fixtures)

    print(
        json.dumps(
            {
                "development": len(dev_cases),
                "holdout": len(hold_cases),
                "metamorphic_pairs": len(metamorphic),
                "req11": req11,
                "sealed": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
