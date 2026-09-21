# -*- coding: utf-8 -*-
"""PR-23: Generic Physical Locator tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from document_ai.document_parser.parser import run_document_structure_mapping_engine
from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.physical_locator.candidate_builder import build_physical_candidates
from document_ai.physical_locator.locator_engine import locate_physical_target
from document_ai.physical_locator.orchestrator import (
    run_physical_locator_engine,
    sample_physical_locator_inputs,
)
from document_ai.physical_locator.ranking import (
    MARGIN_MIN,
    RESOLVED_MIN,
    REVIEW_MIN,
    decide_location_status,
    rank_candidates,
)
from document_ai.physical_locator.schema import (
    PhysicalLocatorInput,
    PhysicalLocationCandidate,
    PrimaryPhysicalLocation,
)
from document_ai.physical_locator.validation import validate_physical_locator
from document_ai.patch_targeting.orchestrator import run_patch_targeting_engine
from document_ai.semantic_locator.locator import run_semantic_locator_engine
from document_ai.template.generic_mapping import run_generic_document_template_pack
from document_ai.template.inventory import run_template_abstraction_layer

REPO = Path(__file__).resolve().parents[1]
FROZEN = [
    REPO / "data/user_scenarios/scenario-001",
    REPO / "data/trials/trial-001-mindrium-xa",
    REPO / "data/trials/trial-002-lockout-multireq",
]


def _by_ptc(pkg):
    return {p["patch_target_candidate_id"]: p for p in pkg["primaries"]}


def test_01_matched_paragraph_resolved():
    p = _by_ptc(run_physical_locator_engine())["PTC-0001"]
    assert p["location_status"] == "RESOLVED"
    assert p["location_type"] == "PARAGRAPH"
    assert p["location_score"] >= RESOLVED_MIN


def test_02_matched_table_resolved():
    p = _by_ptc(run_physical_locator_engine())["PTC-0002"]
    assert p["location_status"] == "RESOLVED"
    assert p["location_type"] == "TABLE"


def test_03_matched_list_resolved():
    p = _by_ptc(run_physical_locator_engine())["PTC-0003"]
    assert p["location_status"] == "RESOLVED"
    assert p["location_type"] == "LIST"


def test_04_duplicate_heading_review():
    p = _by_ptc(run_physical_locator_engine())["PTC-0004"]
    assert p["location_status"] == "REVIEW"
    assert "AMBIGUOUS_TOP_LOCATIONS" in p["reason_codes"]


def test_05_unresolved_empty():
    p = _by_ptc(run_physical_locator_engine())["PTC-0005"]
    assert p["location_status"] == "UNRESOLVED"


def test_06_invalid_missing_document():
    p = _by_ptc(run_physical_locator_engine())["PTC-0006"]
    assert p["location_status"] == "INVALID"
    assert "DOCUMENT_NOT_FOUND" in p["reason_codes"] or "BROKEN_REFERENCE" in p[
        "reason_codes"
    ]


def test_07_invalid_target():
    p = _by_ptc(run_physical_locator_engine())["PTC-0007"]
    assert p["location_status"] == "INVALID"


def test_08_proposal_schedule_resolved():
    p = _by_ptc(run_physical_locator_engine())["PTC-0008"]
    assert p["location_status"] == "RESOLVED"
    assert p["location_type"] == "PARAGRAPH"


def test_09_duplicate_paragraph_review():
    p = _by_ptc(run_physical_locator_engine())["PTC-0009"]
    assert p["location_status"] == "REVIEW"


def test_10_heading_ranking():
    pkg = run_physical_locator_engine()
    cands = [
        c
        for c in pkg["candidates"]
        if c["patch_target_candidate_id"] == "PTC-0001" and c["location_type"] == "HEADING"
    ]
    assert cands
    # preferred paragraph should outrank heading for PTC-0001
    primary = _by_ptc(pkg)["PTC-0001"]
    assert primary["location_type"] == "PARAGRAPH"


def test_11_paragraph_ranking_top1():
    pkg = run_physical_locator_engine()
    group = [
        c for c in pkg["candidates"] if c["patch_target_candidate_id"] == "PTC-0001"
    ]
    assert group
    assert group[0]["rank"] == 1
    assert group[0]["physical_candidate_id"] == _by_ptc(pkg)["PTC-0001"][
        "physical_candidate_id"
    ]


def test_12_table_ranking():
    primary = _by_ptc(run_physical_locator_engine())["PTC-0002"]
    assert primary["location_type"] == "TABLE"
    assert primary["location_score"] >= RESOLVED_MIN


def test_13_list_ranking():
    primary = _by_ptc(run_physical_locator_engine())["PTC-0003"]
    assert primary["location_type"] == "LIST"


def test_14_top_k_in_evidence():
    p = _by_ptc(run_physical_locator_engine())["PTC-0001"]
    assert "top_k" in p["evidence"]
    assert len(p["evidence"]["top_k"]) >= 1


def test_15_margin_on_resolved():
    p = _by_ptc(run_physical_locator_engine())["PTC-0001"]
    assert p["score_margin"] is not None
    assert p["score_margin"] >= MARGIN_MIN


def test_16_thresholds_constants():
    assert RESOLVED_MIN == 0.85
    assert REVIEW_MIN == 0.60


def test_17_deterministic():
    a = run_physical_locator_engine()
    b = run_physical_locator_engine()
    assert json.dumps(a["primaries"], sort_keys=True) == json.dumps(
        b["primaries"], sort_keys=True
    )
    assert json.dumps(a["candidates"], sort_keys=True) == json.dumps(
        b["candidates"], sort_keys=True
    )


def test_18_candidate_builder_types():
    from document_ai.physical_locator.orchestrator import _sample_documents

    docs = _sample_documents()
    inp = sample_physical_locator_inputs()[0]
    cands = build_physical_candidates(inp, docs[inp.document_id])
    types = {c.location_type for c in cands}
    assert "PARAGRAPH" in types
    assert "HEADING" in types or "SECTION" in types
    assert "TABLE" in types
    assert "LIST" in types


def test_19_validation_valid():
    pkg = run_physical_locator_engine()
    assert pkg["validation"]["status"] == "VALID"
    assert pkg["validation"]["invariants"]["actual_docx_changed_false"] is True
    assert pkg["validation"]["invariants"]["actual_writer_called_false"] is True
    assert pkg["validation"]["invariants"]["actual_patch_created_false"] is True


def test_20_summary_fields():
    s = run_physical_locator_engine()["summary"]
    for k in (
        "input_count",
        "candidate_count",
        "resolved_count",
        "review_count",
        "unresolved_count",
        "invalid_count",
        "global_physical_locator_status",
    ):
        assert k in s
    assert s["actual_docx_changed_count"] == 0
    assert s["actual_writer_called_count"] == 0
    assert s["actual_patch_created_count"] == 0


def test_21_decide_unresolved_empty():
    status, reasons, *_ = decide_location_status([])
    assert status == "UNRESOLVED"
    assert "NO_PHYSICAL_CANDIDATES" in reasons


def test_22_decide_invalid_broken():
    status, reasons, *_ = decide_location_status([], broken=True)
    assert status == "INVALID"


def test_23_score_range():
    pkg = run_physical_locator_engine()
    for c in pkg["candidates"]:
        assert 0.0 <= c["location_score"] <= 1.0


def test_24_feature_flag_off():
    assert is_docx_activation_enabled(env={}) is False
    pkg = run_physical_locator_engine()
    assert pkg["actual_docx_changed"] is False
    assert pkg["actual_writer_called"] is False
    assert pkg["actual_patch_created"] is False


def test_25_freeze():
    for p in FROZEN:
        assert p.exists()


def test_26_pr18_regression():
    items = [
        {
            "review_item_id": "CRI-RP-1",
            "patch_id": "RP-1",
            "document": "MDSR",
            "requirement_id": "Req. 105",
            "field": "criteria",
            "change_type": "UPDATE",
            "review_status": "READY",
            "acu_id": "ACU-001",
        }
    ]
    snap = copy.deepcopy(items)
    a = run_template_abstraction_layer(review_items=items)
    _ = run_physical_locator_engine()
    b = run_template_abstraction_layer(review_items=items)
    assert items == snap
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_27_pr19_regression():
    a = run_generic_document_template_pack()
    _ = run_physical_locator_engine()
    b = run_generic_document_template_pack()
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_28_pr20_regression():
    kwargs = {
        "markdown_texts": [
            {
                "text": "# T\n\n## A\n\nx\n",
                "document_id": "pr20",
                "document_type": "general_report",
            }
        ],
        "objects": [],
    }
    a = run_document_structure_mapping_engine(**kwargs)
    _ = run_physical_locator_engine()
    b = run_document_structure_mapping_engine(**kwargs)
    assert a["summary"]["section_count"] == b["summary"]["section_count"]


def test_29_pr21_regression():
    a = run_semantic_locator_engine(emit_all_ranks=False)
    _ = run_physical_locator_engine()
    b = run_semantic_locator_engine(emit_all_ranks=False)
    assert a["summary"]["matched_count"] == b["summary"]["matched_count"]


def test_30_pr22_regression():
    a = run_patch_targeting_engine()
    _ = run_physical_locator_engine()
    b = run_patch_targeting_engine()
    assert a["summary"]["eligible_count"] == b["summary"]["eligible_count"]
    assert a["summary"]["activation_allowed_count"] == 0


def test_31_negative_duplicate_candidate_id():
    pkg = run_physical_locator_engine()
    c = PhysicalLocationCandidate(**{
        **pkg["candidates"][0],
        "cell_coordinate": tuple(pkg["candidates"][0]["cell_coordinate"])
        if pkg["candidates"][0].get("cell_coordinate")
        else None,
        "character_span": tuple(pkg["candidates"][0]["character_span"])
        if pkg["candidates"][0].get("character_span")
        else None,
    })
    v = validate_physical_locator(
        candidates=[c, copy.deepcopy(c)],
        primaries=[PrimaryPhysicalLocation(**pkg["primaries"][0])],
        input_target_ids={pkg["primaries"][0]["patch_target_candidate_id"]},
        known_document_ids={pkg["primaries"][0]["document_id"]},
        summary=None,
    )
    assert "duplicate_physical_candidate_id" in v["issues"]


def test_32_negative_summary_tamper():
    pkg = run_physical_locator_engine()
    from document_ai.physical_locator.schema import PhysicalLocationCandidate as PLC
    from document_ai.physical_locator.schema import PrimaryPhysicalLocation as PPL

    def _cand(d):
        kw = dict(d)
        if kw.get("cell_coordinate") is not None:
            kw["cell_coordinate"] = tuple(kw["cell_coordinate"])
        if kw.get("character_span") is not None:
            kw["character_span"] = tuple(kw["character_span"])
        return PLC(**kw)

    cands = [_cand(c) for c in pkg["candidates"]]
    primaries = [PPL(**p) for p in pkg["primaries"]]
    bad = dict(pkg["summary"])
    bad["resolved_count"] = 999
    v = validate_physical_locator(
        candidates=cands,
        primaries=primaries,
        input_target_ids={i.patch_target_candidate_id for i in sample_physical_locator_inputs()},
        known_document_ids={p.document_id for p in primaries if p.document_id},
        summary=bad,
    )
    assert any("summary_" in i for i in v["issues"])


def test_33_negative_top1_inconsistent():
    pkg = run_physical_locator_engine()
    from document_ai.physical_locator.schema import PhysicalLocationCandidate as PLC
    from document_ai.physical_locator.schema import PrimaryPhysicalLocation as PPL

    def _cand(d):
        kw = dict(d)
        if kw.get("cell_coordinate") is not None:
            kw["cell_coordinate"] = tuple(kw["cell_coordinate"])
        if kw.get("character_span") is not None:
            kw["character_span"] = tuple(kw["character_span"])
        return PLC(**kw)

    # take resolved primary and point to wrong candidate of same group
    primary_d = next(p for p in pkg["primaries"] if p["location_status"] == "RESOLVED")
    group = [
        c
        for c in pkg["candidates"]
        if c["patch_target_candidate_id"] == primary_d["patch_target_candidate_id"]
    ]
    assert len(group) >= 2
    bad_primary = dict(primary_d)
    bad_primary["physical_candidate_id"] = group[1]["physical_candidate_id"]
    v = validate_physical_locator(
        candidates=[_cand(c) for c in group],
        primaries=[PPL(**bad_primary)],
        input_target_ids={primary_d["patch_target_candidate_id"]},
        known_document_ids={primary_d["document_id"]},
        summary=None,
    )
    assert any("top1_inconsistent" in i for i in v["issues"])


def test_34_sample_input_count():
    assert len(sample_physical_locator_inputs()) >= 9


def test_35_no_mutation_flags_on_primary():
    for p in run_physical_locator_engine()["primaries"]:
        assert p["actual_docx_changed"] is False
        assert p["actual_writer_called"] is False
        assert p["actual_patch_created"] is False


def test_36_locate_engine_broken_section_flag():
    from document_ai.physical_locator.orchestrator import _sample_documents

    docs = _sample_documents()
    inp = PhysicalLocatorInput(
        physical_locator_input_id="X",
        patch_target_candidate_id="PTC-X",
        document_id="sample_md_general_report_001",
        template_id="general_report_v1",
        template_node_id="general_report_v1.methodology.data_sources",
        section_id="not_in_structure",
        field_id="data_sources",
        target_status="RESOLVED",
        heading_path_hint=["방법론"],
        metadata={"require_structure_section": True},
    )
    _, primary = locate_physical_target(inp, docs[inp.document_id], seq=99)
    assert primary.location_status == "INVALID"
    assert "SECTION_NOT_FOUND" in primary.reason_codes


def test_37_rank_sequence():
    pkg = run_physical_locator_engine()
    by = {}
    for c in pkg["candidates"]:
        by.setdefault(c["patch_target_candidate_id"], []).append(c["rank"])
    for tid, ranks in by.items():
        assert sorted(ranks) == list(range(1, len(ranks) + 1)), tid


def test_38_global_status_invalid_with_fixtures():
    s = run_physical_locator_engine()["summary"]
    assert s["global_physical_locator_status"] == "INVALID"
    assert s["invalid_count"] >= 1


def test_39_validation_vs_global_distinction():
    pkg = run_physical_locator_engine()
    assert pkg["validation"]["status"] == "VALID"
    assert pkg["summary"]["global_physical_locator_status"] == "INVALID"


def test_40_character_span_present_on_paragraph():
    pkg = run_physical_locator_engine()
    paras = [c for c in pkg["candidates"] if c["location_type"] == "PARAGRAPH"]
    assert paras
    assert paras[0]["character_span"] is not None


def test_41_table_cell_candidates_exist():
    pkg = run_physical_locator_engine()
    cells = [c for c in pkg["candidates"] if c["location_type"] == "TABLE_CELL"]
    # may be truncated in artifact top-k; check builder directly
    from document_ai.physical_locator.orchestrator import _sample_documents

    docs = _sample_documents()
    inp = sample_physical_locator_inputs()[1]
    cands = build_physical_candidates(inp, docs[inp.document_id])
    assert any(c.location_type == "TABLE_CELL" for c in cands)
