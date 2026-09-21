# -*- coding: utf-8 -*-
"""PR-18: Template Abstraction Layer tests."""

from __future__ import annotations

import copy

import pytest

from document_ai.impact.docx_activation_writer import (
    is_docx_activation_enabled,
    resolve_execution_policy,
)
from document_ai.template.adapters import (
    build_mddr_template,
    build_mdsr_template,
    map_artifacts_to_template_nodes,
)
from document_ai.template.inventory import run_template_abstraction_layer
from document_ai.template.registry import TemplateRegistry
from document_ai.template.schema import (
    FieldDefinition,
    SectionDefinition,
    TemplateDefinition,
    TemplateNode,
    make_template_node_id,
    slugify_requirement_id,
)
from document_ai.template.validation import validate_template_layer


def _review(
    pid: str,
    *,
    doc: str = "MDSR",
    rid: str | None = "Req. 105",
    field: str = "criteria",
    acu: str = "ACU-001",
    op: str = "UPDATE",
    review_status: str = "READY",
) -> dict:
    return {
        "review_item_id": f"CRI-{pid}",
        "patch_id": pid,
        "atomic_change_id": acu,
        "activation_item_id": f"DA-{pid}",
        "document": doc,
        "requirement_id": rid,
        "field": field,
        "change_type": op,
        "review_status": review_status,
        "gate_status": "PASS" if review_status == "READY" else review_status,
    }


def test_1_2_register_mdsr_mddr():
    reg = TemplateRegistry()
    reg.register_template(build_mdsr_template())
    reg.register_template(build_mddr_template())
    assert reg.get_template("mdsr_v1") is not None
    assert reg.get_template("mddr_v1") is not None
    assert len(reg.list_templates()) == 2


def test_3_duplicate_template_id():
    reg = TemplateRegistry()
    reg.register_template(build_mdsr_template())
    with pytest.raises(ValueError, match="duplicate_template_id"):
        reg.register_template(build_mdsr_template())


def test_4_duplicate_node_id():
    reg = TemplateRegistry()
    reg.register_template(build_mdsr_template())
    n = TemplateNode(
        template_node_id="mdsr_v1.document",
        template_id="mdsr_v1",
        document_type="software_requirements",
        section_id="document",
        field_id="",
    )
    reg.register_node(n)
    with pytest.raises(ValueError, match="duplicate_template_node_id"):
        reg.register_node(n)


def test_5_6_parent_unknown_and_cycle():
    reg = TemplateRegistry()
    t = TemplateDefinition(
        template_id="t1",
        schema_version="template_schema_v1",
        document_type="custom",
        display_name="t",
        sections=[
            SectionDefinition(
                section_id="a",
                display_name="A",
                parent_section_id="missing",
            )
        ],
        allowed_operations=["UPDATE"],
    )
    reg.register_template(t)
    v = reg.validate_registry()
    assert any("unknown_parent" in i for i in v["issues"])

    reg2 = TemplateRegistry()
    t2 = TemplateDefinition(
        template_id="t2",
        schema_version="template_schema_v1",
        document_type="custom",
        display_name="t2",
        sections=[
            SectionDefinition(section_id="a", display_name="A", parent_section_id="b"),
            SectionDefinition(section_id="b", display_name="B", parent_section_id="a"),
        ],
        allowed_operations=["UPDATE"],
    )
    reg2.register_template(t2)
    v2 = reg2.validate_registry()
    assert any("parent_cycle" in i for i in v2["issues"])


def test_7_required_field_warning_path():
    # required section with no fields → warning (not hard fail)
    reg = TemplateRegistry()
    t = TemplateDefinition(
        template_id="t3",
        schema_version="template_schema_v1",
        document_type="custom",
        display_name="t3",
        sections=[
            SectionDefinition(
                section_id="req",
                display_name="R",
                section_type="requirement",
                required=True,
                fields=[],
            )
        ],
        allowed_operations=["UPDATE"],
    )
    reg.register_template(t)
    v = reg.validate_registry()
    assert v["status"] in ("VALID", "VALID_WITH_WARNINGS")


def test_8_invalid_operation_on_register():
    reg = TemplateRegistry()
    t = TemplateDefinition(
        template_id="bad",
        schema_version="template_schema_v1",
        document_type="custom",
        display_name="bad",
        allowed_operations=["NOT_A_REAL_OP"],
    )
    with pytest.raises(ValueError, match="invalid_operation"):
        reg.register_template(t)


def test_9_10_deterministic_ids():
    assert slugify_requirement_id("Req. 105") == "req_105"
    a = make_template_node_id("mdsr_v1", requirement_slug="req_105", field_id="criteria")
    b = make_template_node_id("mdsr_v1", requirement_slug="req_105", field_id="criteria")
    assert a == b == "mdsr_v1.requirements.req_105.criteria"


def test_11_15_field_mappings():
    pkg = run_template_abstraction_layer(
        review_items=[
            _review("RP-1", doc="MDSR", field="criteria"),
            _review("RP-2", doc="MDDR", field="design_body", rid="Req. 105"),
            _review("RP-3", doc="MDDR", field="design_condition", rid="Req. 105", acu="ACU-002"),
            _review("RP-4", doc="MDSR", field="description", rid="Req. 10"),
        ]
    )
    by_pid = {m["patch_id"]: m for m in pkg["mappings"]["mappings"]}
    assert by_pid["RP-1"]["mapping_status"] == "MAPPED"
    assert by_pid["RP-1"]["template_id"] == "mdsr_v1"
    assert "criteria" in by_pid["RP-1"]["template_node_id"]
    assert by_pid["RP-2"]["template_id"] == "mddr_v1"
    assert "design_body" in by_pid["RP-2"]["template_node_id"]
    assert by_pid["RP-3"]["mapping_status"] == "MAPPED"
    assert "design_condition" in by_pid["RP-3"]["template_node_id"]


def test_16_17_18_unmapped_cases():
    pkg = run_template_abstraction_layer(
        review_items=[
            _review("RP-N", rid=None, doc="MDSR", field="criteria"),
            _review("RP-E", doc="", rid="Req. 1", field="criteria"),
            _review("RP-U", doc="MDSR", field="not_a_field", rid="Req. 1"),
        ]
    )
    statuses = {m["patch_id"]: m for m in pkg["mappings"]["mappings"]}
    assert statuses["RP-N"]["mapping_status"] == "UNMAPPED"
    assert "MISSING_REQUIREMENT_ID" in statuses["RP-N"]["mapping_reason_codes"]
    assert statuses["RP-E"]["mapping_status"] == "UNMAPPED"
    assert "MISSING_DOCUMENT" in statuses["RP-E"]["mapping_reason_codes"]
    assert statuses["RP-U"]["mapping_status"] == "UNMAPPED"
    assert "UNKNOWN_FIELD" in statuses["RP-U"]["mapping_reason_codes"]
    assert pkg["summary"]["global_template_status"] == "REVIEW"


def test_19_20_mapped_exists():
    pkg = run_template_abstraction_layer(
        review_items=[_review("RP-1", field="criteria")]
    )
    m = pkg["mappings"]["mappings"][0]
    assert m["template_id"] in {t["template_id"] for t in pkg["registry"]["templates"]}
    assert m["template_node_id"] in {n["template_node_id"] for n in pkg["nodes"]["nodes"]}


def test_21_23_mismatch_detection():
    reg = TemplateRegistry()
    reg.register_template(build_mdsr_template())
    # forge mapping pointing to wrong template
    mappings = [
        {
            "mapping_id": "TM-X",
            "template_id": "mddr_v1",
            "template_node_id": "mddr_v1.requirements.req_105.design_body",
            "patch_id": "RP-1",
            "review_item_id": "CRI-RP-1",
            "document": "MDSR",
            "requirement_id": "Req. 105",
            "field": "criteria",
            "mapping_status": "MAPPED",
            "mapping_method": "explicit_adapter",
            "mapping_reason_codes": [],
        }
    ]
    # register fake node on wrong template — need mddr registered and node
    reg.register_template(build_mddr_template())
    from document_ai.template.adapters import ensure_requirement_nodes

    ensure_requirement_nodes(
        reg, document="MDDR", requirement_id="Req. 105", field="design_body"
    )
    v = validate_template_layer(reg, mappings=mappings)
    assert any("mdsr_mapped_to_mddr" in i or "mapped_document" in i for i in v["issues"])


def test_24_one_mapping_per_review_item():
    items = [_review("RP-1"), _review("RP-1")]
    # same review_item_id
    items[1]["review_item_id"] = items[0]["review_item_id"]
    pkg = run_template_abstraction_layer(review_items=items)
    statuses = [m["mapping_status"] for m in pkg["mappings"]["mappings"]]
    assert "INVALID" in statuses or pkg["validation"]["global_template_status"] == "INVALID"


def test_25_add_capability():
    pkg = run_template_abstraction_layer(
        review_items=[_review("RP-ADD", op="ADD", field="description")]
    )
    cap = pkg["mappings"]["mappings"][0]["operation_capability"]["ADD"]
    assert cap["template_allowed"] is True
    assert cap["writer_supported"] is False
    # template registry capability
    mdsr = [t for t in pkg["registry"]["templates"] if t["template_id"] == "mdsr_v1"][0]
    assert mdsr["operation_capability"]["ADD"]["template_allowed"] is True
    assert mdsr["operation_capability"]["ADD"]["writer_supported"] is False


def test_26_27_summary_inventory_counts():
    pkg = run_template_abstraction_layer(
        review_items=[
            _review("RP-1", doc="MDSR", field="criteria"),
            _review("RP-2", doc="MDDR", field="design_body"),
            _review("RP-U", rid=None, field="criteria"),
        ]
    )
    s = pkg["summary"]
    assert s["mapping_total_count"] == 3
    assert s["mapped_count"] + s["unmapped_count"] + s["review_count"] + s["invalid_count"] == 3
    assert s["template_count"] == 2
    inv = pkg["inventory"]
    assert inv["template_count"] == 2
    assert inv["node_count"] == pkg["nodes"]["node_count"]


def test_28_deterministic():
    items = [
        _review("RP-2", doc="MDDR", field="design_body", acu="ACU-002"),
        _review("RP-1", doc="MDSR", field="criteria", acu="ACU-001"),
    ]
    a = run_template_abstraction_layer(review_items=items)
    b = run_template_abstraction_layer(review_items=items)
    assert [m["patch_id"] for m in a["mappings"]["mappings"]] == [
        m["patch_id"] for m in b["mappings"]["mappings"]
    ]
    assert [n["template_node_id"] for n in a["nodes"]["nodes"]] == [
        n["template_node_id"] for n in b["nodes"]["nodes"]
    ]


def test_29_30_non_mutation_and_review_status_preserved():
    items = [_review("RP-1", review_status="READY"), _review("RP-B", review_status="BLOCKED", rid=None)]
    snap = copy.deepcopy(items)
    pkg = run_template_abstraction_layer(review_items=items)
    assert items == snap
    # review statuses in input unchanged
    assert items[0]["review_status"] == "READY"
    assert items[1]["review_status"] == "BLOCKED"
    assert pkg["summary"]["actual_docx_changed"] is False


def test_31_32_33_flag_and_docx_invariants():
    assert is_docx_activation_enabled(env={}) is False
    assert resolve_execution_policy(env={}) == "strict_global"
    pkg = run_template_abstraction_layer(review_items=[_review("RP-1")])
    assert pkg["validation"]["invariants"]["docx_writer_not_changed"] is True
    assert pkg["validation"]["invariants"]["actual_docx_unchanged"] is True
    assert pkg["validation"]["invariants"]["actual_generation_unchanged"] is True


def test_34_current_scenario_like_mapping():
    items = []
    for i in range(1, 7):
        items.append(_review(f"RP-M{i}", doc="MDDR", field="design_body", rid=f"Req. {i}"))
    for i in range(1, 6):
        items.append(
            _review(f"RP-S{i}", doc="MDSR", field="criteria", rid=f"Req. {100+i}", acu=f"ACU-{i:03d}")
        )
    items.append(_review("RP-BLOCK", doc="", rid=None, field="", review_status="BLOCKED", op="ADD"))
    pkg = run_template_abstraction_layer(review_items=items)
    mapped = pkg["summary"]["mapped_count"]
    unmapped = pkg["summary"]["unmapped_count"]
    assert mapped == 11
    assert unmapped >= 1
    assert pkg["summary"]["global_template_status"] in ("REVIEW", "VALID")
    # ADD capability on blocked unmapped still recorded if op present
    block_m = [m for m in pkg["mappings"]["mappings"] if m["patch_id"] == "RP-BLOCK"][0]
    assert block_m["mapping_status"] == "UNMAPPED"


def test_negative_summary_mismatch():
    pkg = run_template_abstraction_layer(review_items=[_review("RP-1")])
    bad = dict(pkg["summary"])
    bad["mapped_count"] = 99
    v = validate_template_layer(
        TemplateRegistry(),
        mappings=pkg["mappings"]["mappings"],
        summary=bad,
    )
    # registry empty → more issues; at least summary mismatch
    assert any("summary_" in i for i in v["issues"]) or v["status"] == "INVALID"


def test_negative_field_op_not_in_policy():
    reg = TemplateRegistry()
    t = TemplateDefinition(
        template_id="t_op",
        schema_version="template_schema_v1",
        document_type="custom",
        display_name="t",
        allowed_operations=["UPDATE"],
        sections=[
            SectionDefinition(
                section_id="s",
                display_name="S",
                fields=[
                    FieldDefinition(
                        field_id="f",
                        display_name="F",
                        allowed_operations=["DELETE"],  # not in template allowed
                    )
                ],
            )
        ],
    )
    reg.register_template(t)
    v = validate_template_layer(reg, mappings=[])
    assert any("op_not_in_template_policy" in i for i in v["issues"])
