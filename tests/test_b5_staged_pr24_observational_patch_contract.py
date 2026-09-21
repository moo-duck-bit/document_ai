# -*- coding: utf-8 -*-
"""PR-24: Observational Patch Contract / Writer Plan Bridge tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from document_ai.document_parser.parser import run_document_structure_mapping_engine
from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.patch_contract.contract_builder import build_contract
from document_ai.patch_contract.fingerprint import fingerprint_text, sha256_hex
from document_ai.patch_contract.orchestrator import (
    run_patch_contract_engine,
    sample_patch_contract_inputs,
)
from document_ai.patch_contract.preconditions import PRECONDITION_ORDER
from document_ai.patch_contract.schema import (
    PatchContract,
    PatchContractInput,
    PatchOperationPlan,
    PatchPrecondition,
    WriterPlanPreview,
)
from document_ai.patch_contract.validation import validate_patch_contracts
from document_ai.patch_contract.writer_plan import select_writer_adapter
from document_ai.patch_targeting.orchestrator import run_patch_targeting_engine
from document_ai.physical_locator.orchestrator import run_physical_locator_engine
from document_ai.semantic_locator.locator import run_semantic_locator_engine
from document_ai.template.generic_mapping import run_generic_document_template_pack
from document_ai.template.inventory import run_template_abstraction_layer

REPO = Path(__file__).resolve().parents[1]
FROZEN = [
    REPO / "data/user_scenarios/scenario-001",
    REPO / "data/trials/trial-001-mindrium-xa",
    REPO / "data/trials/trial-002-lockout-multireq",
]


def _by_case(pkg):
    out = {}
    for inp, c, prev in zip(
        pkg["inputs"], pkg["contracts"], pkg["writer_plan_previews"]
    ):
        case = (inp.get("metadata") or {}).get("case") or inp["patch_contract_input_id"]
        out[case] = {"input": inp, "contract": c, "preview": prev}
    return out


def test_01_paragraph_update_ready_for_review():
    row = _by_case(run_patch_contract_engine())["resolved_paragraph_update"]
    assert row["contract"]["contract_status"] == "CONTRACT_READY_FOR_REVIEW"
    assert row["preview"]["preview_status"] == "PREVIEW_BLOCKED"
    assert row["contract"]["contract_executable"] is False


def test_02_table_cell_update():
    row = _by_case(run_patch_contract_engine())["resolved_table_cell_update"]
    assert row["contract"]["contract_status"] == "CONTRACT_READY_FOR_REVIEW"
    assert row["input"]["location_type"] == "TABLE_CELL"
    assert row["input"]["span_kind"] == "ESTIMATED_BLOCK_LOCAL"
    assert row["contract"]["actual_writer_called"] is False


def test_03_list_update():
    row = _by_case(run_patch_contract_engine())["resolved_list_update"]
    assert row["contract"]["contract_status"] == "CONTRACT_READY_FOR_REVIEW"
    assert row["preview"]["preview_status"] == "PREVIEW_BLOCKED"


def test_04_add_unsupported_blocked():
    row = _by_case(run_patch_contract_engine())["add_unsupported"]
    assert row["contract"]["contract_status"] == "CONTRACT_BLOCKED"
    assert "ADD_WRITER_UNSUPPORTED" in row["contract"]["reason_codes"]


def test_05_review_physical():
    row = _by_case(run_patch_contract_engine())["review_physical"]
    assert row["contract"]["contract_status"] == "CONTRACT_REVIEW"
    assert row["preview"]["preview_status"] == "PREVIEW_REVIEW"


def test_06_unresolved_physical_blocked():
    row = _by_case(run_patch_contract_engine())["unresolved_physical"]
    assert row["contract"]["contract_status"] == "CONTRACT_BLOCKED"


def test_07_invalid_target_ref():
    row = _by_case(run_patch_contract_engine())["invalid_target_ref"]
    assert row["contract"]["contract_status"] == "CONTRACT_INVALID"
    assert row["preview"]["preview_status"] == "PREVIEW_INVALID"


def test_08_missing_proposed_text():
    row = _by_case(run_patch_contract_engine())["missing_proposed_text"]
    assert row["contract"]["contract_status"] == "CONTRACT_BLOCKED"
    assert "MISSING_PROPOSED_TEXT" in row["contract"]["reason_codes"]


def test_09_delete_without_approval_review():
    row = _by_case(run_patch_contract_engine())["delete_without_approval"]
    assert row["contract"]["contract_status"] == "CONTRACT_REVIEW"
    assert "HUMAN_APPROVAL_MISSING" in row["contract"]["reason_codes"]


def test_10_link_missing_metadata_blocked():
    row = _by_case(run_patch_contract_engine())["link_missing_metadata"]
    assert row["contract"]["contract_status"] == "CONTRACT_BLOCKED"
    assert "LINK_METADATA_MISSING" in row["contract"]["reason_codes"]


def test_11_document_id_mismatch_invalid():
    row = _by_case(run_patch_contract_engine())["document_id_mismatch"]
    assert row["contract"]["contract_status"] == "CONTRACT_INVALID"


def test_12_stale_fingerprint_blocked():
    row = _by_case(run_patch_contract_engine())["stale_fingerprint"]
    assert row["contract"]["contract_status"] == "CONTRACT_BLOCKED"
    assert "STALE_OR_MISMATCHED_FINGERPRINT" in row["contract"]["reason_codes"]
    pcs = [
        p
        for p in run_patch_contract_engine()["preconditions"]
        if p["patch_contract_id"] == row["contract"]["patch_contract_id"]
        and p["precondition_type"] == "SOURCE_FINGERPRINT_MATCH"
    ]
    assert pcs and pcs[0]["precondition_status"] == "UNSATISFIED"


def test_13_external_flag_on_still_blocked():
    pkg = run_patch_contract_engine(env={"DOCX_ACTIVATION_ENABLED": "true"})
    assert pkg["external_activation_flag"] is True
    assert pkg["activation_allowed"] is False
    assert pkg["contract_executable"] is False
    assert all(c["activation_allowed"] is False for c in pkg["contracts"])
    assert all(c["contract_executable"] is False for c in pkg["contracts"])
    assert all(c["actual_writer_called"] is False for c in pkg["contracts"])
    assert all(c["actual_document_changed"] is False for c in pkg["contracts"])
    assert all(p["preview_status"] != "PREVIEW_READY" for p in pkg["writer_plan_previews"])
    assert all(
        c["contract_status"] != "CONTRACT_EXECUTABLE" for c in pkg["contracts"]
    )


def test_14_broken_intent_reference():
    inp = sample_patch_contract_inputs()[0]
    inp = copy.deepcopy(inp)
    inp.intent_reference_valid = False
    c, _, _ = build_contract(inp, seq=99)
    assert c.contract_status == "CONTRACT_INVALID"
    assert "BROKEN_PATCH_INTENT_REFERENCE" in c.reason_codes


def test_15_broken_primary_reference():
    inp = sample_patch_contract_inputs()[0]
    inp = copy.deepcopy(inp)
    inp.primary_reference_valid = False
    c, _, _ = build_contract(inp, seq=99)
    assert c.contract_status == "CONTRACT_INVALID"


def test_16_template_node_mismatch_blocked_when_missing():
    inp = copy.deepcopy(sample_patch_contract_inputs()[0])
    inp.template_node_id = None
    c, _, _ = build_contract(inp, seq=99)
    assert c.contract_status == "CONTRACT_BLOCKED"
    assert "MISSING_TEMPLATE_NODE" in c.reason_codes


def test_17_original_text_mismatch():
    inp = copy.deepcopy(sample_patch_contract_inputs()[0])
    inp.metadata = dict(inp.metadata)
    inp.metadata["observed_original_text"] = "완전히 다른 원문"
    c, pcs, _ = build_contract(inp, seq=99)
    assert c.contract_status == "CONTRACT_BLOCKED"
    assert any(
        p.precondition_type == "ORIGINAL_TEXT_MATCH"
        and p.precondition_status == "UNSATISFIED"
        for p in pcs
    )


def test_18_span_kind_not_executable_in_preview():
    pkg = run_patch_contract_engine()
    for prev in pkg["writer_plan_previews"]:
        assert "SPAN_KIND_NOT_EXECUTABLE" in prev["blocking_reasons"]
        assert prev["preview_status"] != "PREVIEW_READY"


def test_19_deterministic_ids():
    a = run_patch_contract_engine()
    b = run_patch_contract_engine()
    assert [c["patch_contract_id"] for c in a["contracts"]] == [
        c["patch_contract_id"] for c in b["contracts"]
    ]
    assert [p["precondition_id"] for p in a["preconditions"]] == [
        p["precondition_id"] for p in b["preconditions"]
    ]


def test_20_deterministic_hashes():
    t = "내부 artifact 및 샘플 fixture"
    assert fingerprint_text(t)["fingerprint"] == fingerprint_text(t)["fingerprint"]
    assert sha256_hex("x") == sha256_hex("x")


def test_21_precondition_ordering_deterministic():
    pkg = run_patch_contract_engine()
    by_c = {}
    for p in pkg["preconditions"]:
        by_c.setdefault(p["patch_contract_id"], []).append(p["precondition_type"])
    order_index = {t: i for i, t in enumerate(PRECONDITION_ORDER)}
    for types in by_c.values():
        idxs = [order_index[t] for t in types]
        assert idxs == sorted(idxs)


def test_22_summary_consistency():
    pkg = run_patch_contract_engine()
    s = pkg["summary"]
    assert s["input_count"] == len(pkg["inputs"])
    assert s["contract_count"] == len(pkg["contracts"])
    assert s["preview_ready_count"] == 0
    assert s["contract_executable_count"] == 0
    assert s["activation_allowed_count"] == 0
    assert s["actual_writer_called_count"] == 0
    assert s["actual_document_changed_count"] == 0
    assert s["actual_patch_created_count"] == 0


def test_23_duplicate_contract_id_detected():
    pkg = run_patch_contract_engine()
    c0 = PatchContract(**pkg["contracts"][0])
    v = validate_patch_contracts(
        inputs=sample_patch_contract_inputs(),
        contracts=[c0, copy.deepcopy(c0)],
        preconditions=[],
        plans=[],
        previews=[],
        summary=None,
    )
    assert "duplicate_patch_contract_id" in v["issues"]


def test_24_duplicate_precondition_id_detected():
    pkg = run_patch_contract_engine()
    p0 = PatchPrecondition(**pkg["preconditions"][0])
    v = validate_patch_contracts(
        inputs=[],
        contracts=[],
        preconditions=[p0, copy.deepcopy(p0)],
        plans=[],
        previews=[],
        summary=None,
    )
    assert "duplicate_precondition_id" in v["issues"]


def test_25_invalid_operation_plan_reference():
    pkg = run_patch_contract_engine()
    bad = dict(pkg["contracts"][0])
    bad["operation_plan_id"] = "POP-DOES-NOT-EXIST"
    v = validate_patch_contracts(
        inputs=sample_patch_contract_inputs(),
        contracts=[PatchContract(**bad)],
        preconditions=[],
        plans=[
            PatchOperationPlan(
                **{
                    **pkg["operation_plans"][0],
                    "cell_coordinate": tuple(pkg["operation_plans"][0]["cell_coordinate"])
                    if pkg["operation_plans"][0].get("cell_coordinate")
                    else None,
                    "character_span": tuple(pkg["operation_plans"][0]["character_span"])
                    if pkg["operation_plans"][0].get("character_span")
                    else None,
                }
            )
        ],
        previews=[],
        summary=None,
    )
    assert any("invalid_operation_plan_ref" in i for i in v["issues"])


def test_26_no_preview_ready():
    pkg = run_patch_contract_engine()
    assert all(p["preview_status"] != "PREVIEW_READY" for p in pkg["writer_plan_previews"])
    assert pkg["validation"]["invariants"]["no_preview_ready"] is True


def test_27_no_executable_contract():
    pkg = run_patch_contract_engine()
    assert all(c["contract_executable"] is False for c in pkg["contracts"])
    assert all(
        c["contract_status"]
        not in ("CONTRACT_EXECUTABLE", "EXECUTED", "APPLIED")
        for c in pkg["contracts"]
    )


def test_28_feature_flag_on_full_engine_path():
    assert is_docx_activation_enabled(env={"DOCX_ACTIVATION_ENABLED": "true"}) is True
    pkg = run_patch_contract_engine(env={"DOCX_ACTIVATION_ENABLED": "true"})
    assert pkg["validation"]["invariants"]["activation_allowed_always_false"] is True
    assert pkg["validation"]["invariants"]["activation_blocked_despite_external_flag"] is True
    assert pkg["writer_import_call_count"] == 0
    assert pkg["docx_markdown_mutation_count"] == 0


def test_29_actual_writer_count_zero():
    pkg = run_patch_contract_engine()
    assert pkg["summary"]["actual_writer_called_count"] == 0
    assert pkg["actual_writer_called"] is False


def test_30_actual_document_change_count_zero():
    pkg = run_patch_contract_engine()
    assert pkg["summary"]["actual_document_changed_count"] == 0
    assert pkg["actual_document_changed"] is False
    assert pkg["actual_docx_changed"] is False


def test_31_actual_patch_count_zero():
    pkg = run_patch_contract_engine()
    assert pkg["summary"]["actual_patch_created_count"] == 0
    assert pkg["actual_patch_created"] is False


def test_32_pr18_regression():
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
    _ = run_patch_contract_engine()
    b = run_template_abstraction_layer(review_items=items)
    assert items == snap
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_33_pr19_regression():
    a = run_generic_document_template_pack()
    _ = run_patch_contract_engine()
    b = run_generic_document_template_pack()
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_34_pr20_regression():
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
    _ = run_patch_contract_engine()
    b = run_document_structure_mapping_engine(**kwargs)
    assert a["summary"]["section_count"] == b["summary"]["section_count"]


def test_35_pr21_regression():
    a = run_semantic_locator_engine(emit_all_ranks=False)
    _ = run_patch_contract_engine()
    b = run_semantic_locator_engine(emit_all_ranks=False)
    assert a["summary"]["matched_count"] == b["summary"]["matched_count"]


def test_36_pr22_regression():
    a = run_patch_targeting_engine()
    _ = run_patch_contract_engine()
    b = run_patch_targeting_engine()
    assert a["summary"]["eligible_count"] == b["summary"]["eligible_count"]
    assert a["summary"]["activation_allowed_count"] == 0


def test_37_pr23_regression():
    a = run_physical_locator_engine()
    _ = run_patch_contract_engine()
    b = run_physical_locator_engine()
    assert a["summary"]["resolved_count"] == b["summary"]["resolved_count"]
    assert a["summary"]["full_candidate_count"] == b["summary"]["full_candidate_count"]
    assert a["activation_allowed"] is False


def test_38_freeze_maintained():
    for p in FROZEN:
        assert p.exists()


def test_39_validation_valid():
    pkg = run_patch_contract_engine()
    assert pkg["validation"]["status"] == "VALID"


def test_40_sample_input_count():
    assert len(sample_patch_contract_inputs()) >= 13


def test_41_writer_adapter_markdown_paragraph():
    r = select_writer_adapter(
        source_format="markdown",
        location_type="PARAGRAPH",
        requested_operation="UPDATE",
    )
    assert r["writer_adapter"] == "MARKDOWN_BLOCK_WRITER"


def test_42_writer_adapter_add_unsupported():
    r = select_writer_adapter(
        source_format="markdown",
        location_type="PARAGRAPH",
        requested_operation="ADD",
    )
    assert r["writer_adapter"] == "UNSUPPORTED_WRITER"
    assert r["writer_supported"] is False


def test_43_observational_gate_precondition_unsatisfied():
    pcs = run_patch_contract_engine()["preconditions"]
    gates = [p for p in pcs if p["precondition_type"] == "OBSERVATIONAL_GATE_DISABLED"]
    assert gates
    assert all(g["precondition_status"] == "UNSATISFIED" for g in gates)


def test_44_fingerprint_not_available_no_invented_hash():
    fp = fingerprint_text(None)
    assert fp["fingerprint_status"] == "NOT_AVAILABLE"
    assert fp["fingerprint"] is None


def test_45_operation_plan_safety_flags():
    for plan in run_patch_contract_engine()["operation_plans"]:
        assert plan["activation_allowed"] is False
        assert plan["actual_writer_called"] is False
        assert plan["actual_document_changed"] is False


def test_46_pr23_span_kind_on_candidates():
    pkg = run_physical_locator_engine()
    for c in pkg["full_candidates"]:
        assert c["span_kind"] in (
            "ESTIMATED_BLOCK_LOCAL",
            "SOURCE_ABSOLUTE",
            "OOXML_LOCAL",
            "NONE",
        )
    cells = [c for c in pkg["full_candidates"] if c["location_type"] == "TABLE_CELL"]
    assert cells
    assert all(c["span_kind"] == "ESTIMATED_BLOCK_LOCAL" for c in cells)


def test_47_pr23_full_vs_artifact_topk():
    pkg = run_physical_locator_engine()
    assert pkg["summary"]["full_candidate_count"] >= pkg["summary"]["artifact_candidate_count"]
    assert pkg["artifact_meta"]["candidate_scope"] == "TOP_K_PER_TARGET"
    assert pkg["artifact_meta"]["top_k_limit"] == 8
    # Primary must be in artifact top-k
    art_ids = {c["physical_candidate_id"] for c in pkg["artifact_candidates"]}
    for p in pkg["primaries"]:
        if p["physical_candidate_id"]:
            assert p["physical_candidate_id"] in art_ids


def test_48_pr23_external_flag_on_still_observational():
    pkg = run_physical_locator_engine(env={"DOCX_ACTIVATION_ENABLED": "true"})
    assert pkg["external_activation_flag"] is True
    assert pkg["activation_allowed"] is False
    assert pkg["validation"]["invariants"]["observational_gate_forced_off"] is True
    assert pkg["validation"]["invariants"]["activation_blocked_despite_external_flag"] is True


def test_49_replace_alias_ready():
    inp = copy.deepcopy(sample_patch_contract_inputs()[0])
    inp.requested_operation = "REPLACE"
    c, _, plan = build_contract(inp, seq=50)
    assert c.contract_status == "CONTRACT_READY_FOR_REVIEW"
    assert plan.operation == "REPLACE"


def test_50_json_roundtrip_deterministic():
    a = run_patch_contract_engine()
    b = run_patch_contract_engine()
    assert json.dumps(a["contracts"], sort_keys=True) == json.dumps(
        b["contracts"], sort_keys=True
    )
