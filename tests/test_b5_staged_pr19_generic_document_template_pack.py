# -*- coding: utf-8 -*-
"""PR-19: Generic Document Template Pack tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from document_ai.impact.docx_activation_writer import (
    is_docx_activation_enabled,
    resolve_execution_policy,
)
from document_ai.template.adapters import build_mddr_template, build_mdsr_template
from document_ai.template.generic_mapping import (
    build_generic_template_summary,
    map_generic_sample_changes,
    run_generic_document_template_pack,
    sample_change_items,
    validate_generic_template_pack,
)
from document_ai.template.generic_templates import (
    build_business_proposal_template,
    build_general_report_template,
    build_static_nodes_for_template,
    make_generic_node_id,
)
from document_ai.template.inventory import run_template_abstraction_layer
from document_ai.template.registry import TemplateRegistry
from document_ai.template.sample_documents import (
    build_sample_business_proposal_001,
    build_sample_general_report_001,
    list_sample_documents,
)
from document_ai.template.schema import (
    FieldDefinition,
    SectionDefinition,
    TemplateDefinition,
    TemplateNode,
)


REPO = Path(__file__).resolve().parents[1]
FROZEN_PATHS = [
    REPO / "data/user_scenarios/scenario-001",
    REPO / "data/trials/trial-001-mindrium-xa",
    REPO / "data/trials/trial-002-lockout-multireq",
]


def _generic_registry() -> TemplateRegistry:
    reg = TemplateRegistry()
    report = build_general_report_template()
    proposal = build_business_proposal_template()
    reg.register_template(report)
    reg.register_template(proposal)
    for n in build_static_nodes_for_template(report):
        reg.register_node(n)
    for n in build_static_nodes_for_template(proposal):
        reg.register_node(n)
    return reg


def test_01_general_report_v1_registered():
    t = build_general_report_template()
    assert t.template_id == "general_report_v1"
    assert t.document_type == "general_report"
    assert t.display_name == "일반 보고서"
    reg = TemplateRegistry()
    reg.register_template(t)
    assert reg.get_template("general_report_v1") is not None


def test_02_business_proposal_v1_registered():
    t = build_business_proposal_template()
    assert t.template_id == "business_proposal_v1"
    assert t.document_type == "business_proposal"
    assert t.display_name == "사업 제안서"
    reg = TemplateRegistry()
    reg.register_template(t)
    assert reg.get_template("business_proposal_v1") is not None


def test_03_04_mdsr_mddr_preserved():
    pkg = run_template_abstraction_layer(review_items=[])
    tids = {t["template_id"] for t in pkg["registry"]["templates"]}
    assert "mdsr_v1" in tids
    assert "mddr_v1" in tids
    # generic pack does not remove them from PR-18 path
    g = run_generic_document_template_pack()
    assert "mdsr_v1" not in {t["template_id"] for t in g["registry"]["templates"]}
    # PR-18 still intact when re-run
    pkg2 = run_template_abstraction_layer(review_items=[])
    assert {t["template_id"] for t in pkg2["registry"]["templates"]} == tids


def test_05_duplicate_generic_template_detected():
    reg = TemplateRegistry()
    reg.register_template(build_general_report_template())
    with pytest.raises(ValueError, match="duplicate_template_id"):
        reg.register_template(build_general_report_template())


def test_06_duplicate_generic_node_detected():
    reg = TemplateRegistry()
    t = build_general_report_template()
    reg.register_template(t)
    nodes = build_static_nodes_for_template(t)
    reg.register_node(nodes[0])
    with pytest.raises(ValueError, match="duplicate_template_node_id"):
        reg.register_node(nodes[0])


def test_07_invalid_parent_detected():
    reg = TemplateRegistry()
    bad = TemplateDefinition(
        template_id="bad_parent_v1",
        schema_version="template_schema_v1",
        document_type="general_report",
        display_name="bad",
        sections=[
            SectionDefinition(
                section_id="orphan",
                display_name="orphan",
                parent_section_id="missing_parent",
                fields=[FieldDefinition(field_id="body", display_name="b")],
            )
        ],
        allowed_operations=["UPDATE"],
    )
    reg.register_template(bad)
    v = reg.validate_registry()
    assert any("unknown_parent" in i for i in v["issues"])


def test_08_parent_cycle_detected():
    reg = TemplateRegistry()
    cyclic = TemplateDefinition(
        template_id="cycle_v1",
        schema_version="template_schema_v1",
        document_type="general_report",
        display_name="cycle",
        sections=[
            SectionDefinition(
                section_id="a", display_name="a", parent_section_id="b", fields=[]
            ),
            SectionDefinition(
                section_id="b", display_name="b", parent_section_id="a", fields=[]
            ),
        ],
        allowed_operations=["UPDATE"],
    )
    reg.register_template(cyclic)
    v = reg.validate_registry()
    assert any("parent_cycle" in i for i in v["issues"])


def test_09_invalid_operation_detected():
    reg = TemplateRegistry()
    bad = TemplateDefinition(
        template_id="bad_op_v1",
        schema_version="template_schema_v1",
        document_type="general_report",
        display_name="bad",
        sections=[],
        allowed_operations=["NOT_A_REAL_OP"],
    )
    with pytest.raises(ValueError, match="invalid_operation"):
        reg.register_template(bad)


def test_10_11_report_proposal_sections():
    report = build_general_report_template()
    proposal = build_business_proposal_template()
    r_secs = {s.section_id for s in report.sections}
    p_secs = {s.section_id for s in proposal.sections}
    for need in (
        "document",
        "executive_summary",
        "background",
        "objectives",
        "methodology",
        "results",
        "discussion",
        "conclusion",
        "references",
        "appendix",
    ):
        assert need in r_secs
    for need in (
        "document",
        "overview",
        "problem_statement",
        "proposed_solution",
        "scope",
        "execution_plan",
        "schedule",
        "budget",
        "expected_outcomes",
        "risks",
        "organization",
        "appendix",
    ):
        assert need in p_secs


def test_12_13_report_proposal_fields():
    report = build_general_report_template()
    proposal = build_business_proposal_template()
    r_fields = {
        (s.section_id, f.field_id) for s in report.sections for f in s.fields
    }
    p_fields = {
        (s.section_id, f.field_id) for s in proposal.sections for f in s.fields
    }
    assert ("methodology", "data_sources") in r_fields
    assert ("results", "key_findings") in r_fields
    assert ("conclusion", "recommendations") in r_fields
    assert ("execution_plan", "schedule") in p_fields
    assert ("budget", "summary") in p_fields
    assert ("risks", "mitigation") in p_fields


def test_14_requirement_id_optional_on_generic_nodes():
    nodes = build_static_nodes_for_template(build_general_report_template())
    field_nodes = [n for n in nodes if n.field_id]
    assert field_nodes
    assert all(n.source_requirement_id is None for n in field_nodes)
    # must not be treated as INVALID solely for null requirement
    assert all(n.mapping_status != "INVALID" for n in field_nodes)


def test_15_deterministic_generic_node_id():
    a = make_generic_node_id("general_report_v1", "methodology", "data_sources")
    b = make_generic_node_id("general_report_v1", "methodology", "data_sources")
    assert a == b == "general_report_v1.methodology.data_sources"
    c = make_generic_node_id("business_proposal_v1", "execution_plan", "schedule")
    assert c == "business_proposal_v1.execution_plan.schedule"


def test_16_heading_path_locator_hint():
    t = build_general_report_template()
    meth = next(s for s in t.sections if s.section_id == "methodology")
    ds = next(f for f in meth.fields if f.field_id == "data_sources")
    assert "heading_path" in ds.locator_hints.strategies
    assert ds.locator_hints.heading_path == ["방법론", "데이터 출처"]
    nodes = build_static_nodes_for_template(t)
    node = next(
        n
        for n in nodes
        if n.template_node_id == "general_report_v1.methodology.data_sources"
    )
    assert node.locator_hints.heading_path
    assert node.locator_hints.section_id == "methodology"


def test_17_18_sample_documents():
    samples = list_sample_documents()
    assert len(samples) == 2
    ids = {s["sample_document_id"] for s in samples}
    assert "sample_general_report_001" in ids
    assert "sample_business_proposal_001" in ids
    r = build_sample_general_report_001()
    p = build_sample_business_proposal_001()
    assert "executive_summary" in r["sections"]
    assert "execution_plan" in p["sections"]


def test_19_20_explicit_mappings():
    reg = _generic_registry()
    mappings = map_generic_sample_changes(reg)
    by_id = {m["source_change_id"]: m for m in mappings}
    assert by_id["GCH-001"]["mapping_status"] == "MAPPED"
    assert by_id["GCH-001"]["template_node_id"] == (
        "general_report_v1.methodology.data_sources"
    )
    assert by_id["GCH-001"]["mapping_method"] == "explicit_section_field"
    assert by_id["GCH-002"]["mapping_status"] == "MAPPED"
    assert by_id["GCH-002"]["template_node_id"] == (
        "business_proposal_v1.execution_plan.schedule"
    )


def test_21_22_unknown_section_field_unmapped():
    reg = _generic_registry()
    mappings = map_generic_sample_changes(reg)
    by_id = {m["source_change_id"]: m for m in mappings}
    assert by_id["GCH-003"]["mapping_status"] == "UNMAPPED"
    assert "UNKNOWN_SECTION" in by_id["GCH-003"]["mapping_reason_codes"]
    assert by_id["GCH-004"]["mapping_status"] == "UNMAPPED"
    assert "UNKNOWN_FIELD" in by_id["GCH-004"]["mapping_reason_codes"]


def test_23_template_mismatch_invalid():
    reg = _generic_registry()
    mappings = map_generic_sample_changes(reg)
    by_id = {m["source_change_id"]: m for m in mappings}
    assert by_id["GCH-005"]["mapping_status"] == "INVALID"
    assert "TEMPLATE_MISMATCH" in by_id["GCH-005"]["mapping_reason_codes"]


def test_24_one_mapping_per_sample_change():
    reg = _generic_registry()
    dup = sample_change_items()[:1] + sample_change_items()[:1]
    mappings = map_generic_sample_changes(reg, changes=dup)
    assert any(
        "DUPLICATE_SAMPLE_CHANGE_MAPPING" in (m.get("mapping_reason_codes") or [])
        for m in mappings
    )


def test_25_summary_counts_match():
    pkg = run_generic_document_template_pack()
    s = pkg["summary"]
    mappings = pkg["mappings"]["mappings"]
    assert s["mapping_total_count"] == len(mappings)
    assert s["mapped_count"] == sum(
        1 for m in mappings if m["mapping_status"] == "MAPPED"
    )
    assert s["unmapped_count"] == sum(
        1 for m in mappings if m["mapping_status"] == "UNMAPPED"
    )
    assert s["invalid_count"] == sum(
        1 for m in mappings if m["mapping_status"] == "INVALID"
    )
    assert s["generic_template_count"] == 2
    assert s["sample_document_count"] == 2
    assert s["global_generic_template_status"] == "INVALID"  # mismatch sample present


def test_26_deterministic_json():
    a = run_generic_document_template_pack()
    b = run_generic_document_template_pack()
    assert json.dumps(a["mappings"], sort_keys=True) == json.dumps(
        b["mappings"], sort_keys=True
    )
    assert json.dumps(a["nodes"], sort_keys=True, default=str) == json.dumps(
        b["nodes"], sort_keys=True, default=str
    )
    assert [n["template_node_id"] for n in a["nodes"]["nodes"]] == [
        n["template_node_id"] for n in b["nodes"]["nodes"]
    ]


def test_27_28_missing_reason_aggregation():
    # MDSR/MDDR: empty document + null requirement → both reasons
    def _review(pid, *, doc="", rid=None, field="criteria"):
        return {
            "review_item_id": f"CRI-{pid}",
            "patch_id": pid,
            "document": doc,
            "requirement_id": rid,
            "field": field,
            "change_type": "UPDATE",
            "review_status": "BLOCKED",
            "acu_id": "ACU-004",
        }

    pkg = run_template_abstraction_layer(
        review_items=[_review("RP-ACU004", doc="", rid=None, field="")]
    )
    m = pkg["mappings"]["mappings"][0]
    codes = m["mapping_reason_codes"]
    assert "MISSING_DOCUMENT" in codes
    assert "MISSING_REQUIREMENT_ID" in codes
    # generic: null requirement is OK
    g = run_generic_document_template_pack(
        changes=[
            {
                "source_change_id": "GCH-OK",
                "sample_document_id": "sample_general_report_001",
                "template_id": "general_report_v1",
                "section_id": "methodology",
                "field_id": "data_sources",
                "change_type": "UPDATE",
                "before_text": "a",
                "after_text": "b",
            }
        ]
    )
    gm = g["mappings"]["mappings"][0]
    assert gm["mapping_status"] == "MAPPED"
    assert gm["source_requirement_id"] is None
    assert "MISSING_REQUIREMENT_ID" not in (gm.get("mapping_reason_codes") or [])


def test_29_30_pr18_and_change_review_non_mutation():
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
    pr18 = run_template_abstraction_layer(review_items=items)
    assert items == snap
    before_tids = {t["template_id"] for t in pr18["registry"]["templates"]}
    before_nodes = [n["template_node_id"] for n in pr18["nodes"]["nodes"]]
    before_map = copy.deepcopy(pr18["mappings"])

    # running generic pack must not mutate prior PR-18 results when re-run
    _ = run_generic_document_template_pack()
    pr18b = run_template_abstraction_layer(review_items=items)
    assert {t["template_id"] for t in pr18b["registry"]["templates"]} == before_tids
    assert "mdsr_v1" in before_tids and "mddr_v1" in before_tids
    # same mapping outcome for same inputs
    assert pr18b["summary"]["mapped_count"] == pr18["summary"]["mapped_count"]
    assert before_map["mapping_count"] == pr18b["mappings"]["mapping_count"]
    assert items[0]["review_status"] == "READY"
    assert before_nodes  # PR-18 still produces nodes


def test_31_feature_flag_off():
    assert is_docx_activation_enabled(env={}) is False
    assert resolve_execution_policy(env={}) == "strict_global"
    pkg = run_generic_document_template_pack()
    assert pkg["actual_docx_changed"] is False
    assert pkg["validation"]["invariants"]["docx_writer_not_changed"] is True


def test_32_33_docx_and_legacy_unchanged():
    pkg = run_generic_document_template_pack()
    assert pkg["actual_docx_changed"] is False
    assert pkg["actual_generation_changed"] is False
    assert pkg["validation"]["invariants"]["actual_docx_unchanged"] is True
    assert pkg["validation"]["invariants"]["actual_generation_unchanged"] is True
    # writer source modules not imported for mutation
    from document_ai.impact import docx_activation_writer as w

    assert hasattr(w, "run_docx_activation_writer")
    assert is_docx_activation_enabled(env={}) is False


def test_34_freeze_maintained():
    for p in FROZEN_PATHS:
        assert p.exists(), f"frozen path missing: {p}"
    # generic pack must not write into frozen dirs
    pkg = run_generic_document_template_pack()
    assert pkg["stage"] == "generic_document_template_pack"


def test_negative_mapping_missing_node_ref():
    reg = _generic_registry()
    mappings = [
        {
            "generic_mapping_id": "GM-X",
            "sample_document_id": "sample_general_report_001",
            "template_id": "general_report_v1",
            "template_node_id": "general_report_v1.no.such.node",
            "source_change_id": "GCH-X",
            "section_id": "methodology",
            "field_id": "data_sources",
            "mapping_status": "MAPPED",
            "mapping_method": "explicit_section_field",
            "mapping_reason_codes": [],
        }
    ]
    summary = build_generic_template_summary(
        reg, mappings, sample_document_count=2, global_status="REVIEW"
    )
    v = validate_generic_template_pack(reg, mappings=mappings, summary=summary)
    assert any("mapped_generic_node_missing" in i for i in v["issues"])


def test_negative_section_field_mismatch():
    reg = _generic_registry()
    node_id = "general_report_v1.methodology.data_sources"
    mappings = [
        {
            "generic_mapping_id": "GM-Y",
            "sample_document_id": "sample_general_report_001",
            "template_id": "general_report_v1",
            "template_node_id": node_id,
            "source_change_id": "GCH-Y",
            "section_id": "results",  # mismatch
            "field_id": "body",  # mismatch
            "mapping_status": "MAPPED",
            "mapping_method": "explicit_section_field",
            "mapping_reason_codes": [],
        }
    ]
    summary = build_generic_template_summary(
        reg, mappings, sample_document_count=2, global_status="REVIEW"
    )
    v = validate_generic_template_pack(reg, mappings=mappings, summary=summary)
    assert any("generic_section_inconsistent" in i for i in v["issues"])
    assert any("generic_field_inconsistent" in i for i in v["issues"])


def test_negative_summary_tamper():
    pkg = run_generic_document_template_pack()
    reg = _generic_registry()
    bad_summary = dict(pkg["summary"])
    bad_summary["mapped_count"] = 999
    v = validate_generic_template_pack(
        reg, mappings=pkg["mappings"]["mappings"], summary=bad_summary
    )
    assert any("summary_" in i for i in v["issues"])


def test_negative_generic_null_req_not_invalid():
    """Null requirement_id on generic must not become INVALID via MISSING_REQUIREMENT_ID."""
    reg = _generic_registry()
    mappings = [
        {
            "generic_mapping_id": "GM-Z",
            "sample_document_id": "sample_general_report_001",
            "template_id": "general_report_v1",
            "template_node_id": "general_report_v1.methodology.data_sources",
            "source_change_id": "GCH-Z",
            "section_id": "methodology",
            "field_id": "data_sources",
            "mapping_status": "INVALID",
            "mapping_method": "unknown",
            "mapping_reason_codes": ["MISSING_REQUIREMENT_ID"],
            "source_requirement_id": None,
        }
    ]
    summary = build_generic_template_summary(
        reg, mappings, sample_document_count=2, global_status="INVALID"
    )
    v = validate_generic_template_pack(reg, mappings=mappings, summary=summary)
    assert any("generic_requirement_id_wrongly_required" in i for i in v["issues"])


def test_add_delete_link_capability():
    t = build_general_report_template()
    for op in ("ADD", "DELETE", "LINK"):
        assert op in t.allowed_operations
    refs = next(s for s in t.sections if s.section_id == "references")
    assert set(refs.fields[0].allowed_operations) >= {"ADD", "UPDATE", "DELETE", "LINK"}
    budget = build_business_proposal_template()
    bud = next(s for s in budget.sections if s.section_id == "budget")
    assert "ADD" in bud.fields[1].allowed_operations  # summary


def test_mdsr_requirement_rule_unchanged():
    # requirement_id still required for MDSR mapping
    pkg = run_template_abstraction_layer(
        review_items=[
            {
                "review_item_id": "CRI-N",
                "patch_id": "RP-N",
                "document": "MDSR",
                "requirement_id": None,
                "field": "criteria",
                "change_type": "UPDATE",
                "review_status": "READY",
                "acu_id": "ACU-001",
            }
        ]
    )
    assert pkg["mappings"]["mappings"][0]["mapping_status"] == "UNMAPPED"
    assert "MISSING_REQUIREMENT_ID" in pkg["mappings"]["mappings"][0]["mapping_reason_codes"]
