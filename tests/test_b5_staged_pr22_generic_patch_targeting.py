# -*- coding: utf-8 -*-
"""PR-22: Generic Patch Targeting / Observational Patch Intent Bridge tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from document_ai.document_parser.parser import run_document_structure_mapping_engine
from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.patch_targeting.capability_gate import evaluate_capabilities
from document_ai.patch_targeting.eligibility import evaluate_eligibility
from document_ai.patch_targeting.orchestrator import (
    run_patch_targeting_engine,
    sample_patch_targeting_inputs,
)
from document_ai.patch_targeting.schema import (
    ActivationPreview,
    PatchIntent,
    PatchTargetCandidate,
    PatchTargetingInput,
)
from document_ai.patch_targeting.validation import validate_patch_targeting
from document_ai.semantic_locator.locator import (
    load_generic_node_candidates,
    run_semantic_locator_engine,
)
from document_ai.template.generic_mapping import run_generic_document_template_pack
from document_ai.template.inventory import run_template_abstraction_layer

REPO = Path(__file__).resolve().parents[1]
FROZEN = [
    REPO / "data/user_scenarios/scenario-001",
    REPO / "data/trials/trial-001-mindrium-xa",
    REPO / "data/trials/trial-002-lockout-multireq",
]


def _by_change(pkg):
    return {i["change_id"]: i for i in pkg["intents"]}, {
        t["patch_intent_id"]: t for t in pkg["targets"]
    }, {p["patch_intent_id"]: p for p in pkg["previews"]}


def test_01_matched_update_intent_eligible():
    pkg = run_patch_targeting_engine()
    intents, targets, previews = _by_change(pkg)
    i = intents["CHG-001"]
    t = targets[i["patch_intent_id"]]
    p = previews[i["patch_intent_id"]]
    assert i["intent_status"] == "ELIGIBLE"
    assert t["target_status"] == "RESOLVED"
    assert t["template_node_id"] == "general_report_v1.methodology.data_sources"
    assert t["writer_supported"] is True
    assert p["preview_status"] == "PREVIEW_BLOCKED"
    assert "ACTIVATION_DISABLED" in p["blocking_reasons"]
    assert "OBSERVATIONAL_GATE_FORCED_OFF" in p["blocking_reasons"]
    assert i["actual_patch_created"] is False
    assert p["actual_document_changed"] is False
    assert p["actual_writer_called"] is False
    assert p["preview_status"] != "PREVIEW_READY"


def test_02_matched_add_writer_unsupported():
    pkg = run_patch_targeting_engine()
    intents, targets, previews = _by_change(pkg)
    i = intents["CHG-002"]
    t = targets[i["patch_intent_id"]]
    p = previews[i["patch_intent_id"]]
    assert i["intent_status"] == "ELIGIBLE"
    assert t["target_status"] == "RESOLVED"
    assert t["template_allowed"] is True
    assert t["writer_supported"] is False
    assert p["preview_status"] == "PREVIEW_BLOCKED"
    assert "OPERATION_WRITER_NOT_SUPPORTED" in p["blocking_reasons"]


def test_03_semantic_review():
    pkg = run_patch_targeting_engine()
    intents, targets, previews = _by_change(pkg)
    i = intents["CHG-003"]
    assert i["intent_status"] == "REVIEW_REQUIRED"
    assert targets[i["patch_intent_id"]]["target_status"] == "REVIEW"
    assert previews[i["patch_intent_id"]]["preview_status"] == "PREVIEW_REVIEW"


def test_04_unmapped_blocked():
    pkg = run_patch_targeting_engine()
    intents, targets, previews = _by_change(pkg)
    i = intents["CHG-004"]
    assert i["intent_status"] == "BLOCKED"
    assert targets[i["patch_intent_id"]]["target_status"] == "UNRESOLVED"
    assert previews[i["patch_intent_id"]]["preview_status"] == "PREVIEW_BLOCKED"
    assert "SEMANTIC_UNMAPPED" in i["reason_codes"]


def test_05_semantic_invalid():
    pkg = run_patch_targeting_engine()
    intents, targets, previews = _by_change(pkg)
    i = intents["CHG-005"]
    assert i["intent_status"] == "INVALID"
    assert targets[i["patch_intent_id"]]["target_status"] == "INVALID"
    assert previews[i["patch_intent_id"]]["preview_status"] == "PREVIEW_INVALID"


def test_06_ambiguous_delete_review():
    pkg = run_patch_targeting_engine()
    intents, _, previews = _by_change(pkg)
    i = intents["CHG-006"]
    assert i["intent_status"] == "REVIEW_REQUIRED"
    assert "DELETE_REQUIRES_REVIEW" in i["reason_codes"]
    assert previews[i["patch_intent_id"]]["actual_document_changed"] is False


def test_07_missing_proposed_text():
    pkg = run_patch_targeting_engine()
    intents, _, _ = _by_change(pkg)
    i = intents["CHG-007"]
    assert i["intent_status"] == "BLOCKED"
    assert "PROPOSED_TEXT_MISSING" in i["reason_codes"]


def test_08_template_allowed_writer_unsupported_link():
    pkg = run_patch_targeting_engine()
    intents, targets, previews = _by_change(pkg)
    i = intents["CHG-008"]
    t = targets[i["patch_intent_id"]]
    assert t["template_allowed"] is True
    assert t["writer_supported"] is False
    assert previews[i["patch_intent_id"]]["preview_status"] == "PREVIEW_BLOCKED"
    assert previews[i["patch_intent_id"]]["actual_writer_called"] is False


def test_09_generic_requirement_id_optional():
    pkg = run_patch_targeting_engine()
    intents, targets, _ = _by_change(pkg)
    i = intents["CHG-009"]
    t = targets[i["patch_intent_id"]]
    assert i["intent_status"] == "ELIGIBLE"
    assert t["evidence"].get("source_requirement_id") is None
    assert "MISSING_REQUIREMENT_ID" not in i["reason_codes"]


def test_10_deterministic_ids_and_artifacts():
    a = run_patch_targeting_engine()
    b = run_patch_targeting_engine()
    assert json.dumps(a["intents"], sort_keys=True) == json.dumps(
        b["intents"], sort_keys=True
    )
    assert json.dumps(a["targets"], sort_keys=True) == json.dumps(
        b["targets"], sort_keys=True
    )
    assert json.dumps(a["previews"], sort_keys=True) == json.dumps(
        b["previews"], sort_keys=True
    )


def test_11_capability_separation():
    nodes = load_generic_node_candidates()
    node = next(n for n in nodes if n.field_id == "data_sources")
    caps = evaluate_capabilities("UPDATE", allowed_operations=node.allowed_operations)
    assert caps["template_allowed"] is True
    assert caps["writer_supported"] is True
    assert caps["activation_allowed"] is False
    caps_add = evaluate_capabilities("ADD", allowed_operations=node.allowed_operations)
    assert caps_add["template_allowed"] is True
    assert caps_add["writer_supported"] is False


def test_12_target_node_resolution():
    pkg = run_patch_targeting_engine()
    intents, targets, _ = _by_change(pkg)
    t = targets[intents["CHG-001"]["patch_intent_id"]]
    assert t["section_id"] == "methodology"
    assert t["field_id"] == "data_sources"


def test_13_summary_fields():
    s = run_patch_targeting_engine()["summary"]
    for k in (
        "input_count",
        "eligible_count",
        "review_required_count",
        "blocked_count",
        "invalid_count",
        "preview_blocked_count",
        "actual_patch_created_count",
        "actual_document_changed_count",
        "actual_writer_called_count",
        "global_patch_targeting_status",
    ):
        assert k in s
    assert s["actual_patch_created_count"] == 0
    assert s["actual_writer_called_count"] == 0
    assert s["activation_allowed_count"] == 0


def test_14_validation_valid_with_invalid_fixture():
    pkg = run_patch_targeting_engine()
    assert pkg["validation"]["status"] == "VALID"
    assert pkg["summary"]["global_patch_targeting_status"] == "INVALID"
    assert pkg["validation"]["invariants"]["activation_always_disabled"] is True


def test_15_sample_input_count():
    assert len(sample_patch_targeting_inputs()) >= 9


def test_16_low_score_margin_review():
    from document_ai.semantic_locator.thresholds import DEFAULT_THRESHOLDS

    pkg = run_patch_targeting_engine()
    intents, targets, _ = _by_change(pkg)
    i = intents["CHG-003"]
    t = targets[i["patch_intent_id"]]
    assert i["intent_status"] == "REVIEW_REQUIRED"
    assert "LOW_SCORE_MARGIN" in i["reason_codes"]
    assert "AMBIGUOUS_MATCH" in i["reason_codes"]
    assert t["score_margin"] is not None
    assert t["score_margin"] < DEFAULT_THRESHOLDS.score_margin_min


def test_17_feature_flag_off():
    assert is_docx_activation_enabled(env={}) is False
    pkg = run_patch_targeting_engine()
    assert all(t["activation_allowed"] is False for t in pkg["targets"])
    assert all(p["actual_writer_called"] is False for p in pkg["previews"])


def test_17b_feature_flag_forced_on_still_blocks_activation():
    """DOCX_ACTIVATION_ENABLED=true must not enable PR-22 activation."""
    env_on = {"DOCX_ACTIVATION_ENABLED": "true"}
    assert is_docx_activation_enabled(env=env_on) is True
    caps = evaluate_capabilities(
        "UPDATE",
        allowed_operations=["UPDATE"],
        env=env_on,
    )
    assert caps["external_activation_flag"] is True
    assert caps["observational_gate_forced_off"] is True
    assert caps["activation_allowed"] is False
    assert "OBSERVATIONAL_GATE_FORCED_OFF" in caps["reason_codes"]
    assert "ACTIVATION_DISABLED" in caps["reason_codes"]
    assert "ACTUAL_WRITER_NOT_CALLED" in caps["reason_codes"]
    # Engine path remains writer-free
    pkg = run_patch_targeting_engine()
    assert pkg["actual_writer_called"] is False
    assert all(t["activation_allowed"] is False for t in pkg["targets"])
    assert all(p["preview_status"] != "PREVIEW_READY" for p in pkg["previews"])
    assert all(
        (t.get("evidence") or {}).get("observational_gate_forced_off") is True
        for t in pkg["targets"]
        if t.get("target_status") in ("RESOLVED", "REVIEW")
    )


def test_18_eligibility_unmapped():
    inp = PatchTargetingInput(
        change_id="X",
        document_id="d",
        locator_candidate_id="L",
        semantic_match_id="S",
        template_id="general_report_v1",
        template_node_id=None,
        requested_operation="UPDATE",
        proposed_text="a",
        match_status="UNMAPPED",
    )
    status, reasons, _ = evaluate_eligibility(inp, node_exists=False)
    assert status == "BLOCKED"
    assert "SEMANTIC_UNMAPPED" in reasons


def test_19_eligibility_invalid_op():
    inp = PatchTargetingInput(
        change_id="X",
        document_id="d",
        locator_candidate_id="L",
        semantic_match_id="S",
        template_id="general_report_v1",
        template_node_id="general_report_v1.methodology.data_sources",
        requested_operation="NOPE",
        match_status="MATCHED",
        proposed_text="a",
    )
    status, _, _ = evaluate_eligibility(
        inp, node_exists=True, node_allowed_operations=["UPDATE"], node_template_id="general_report_v1"
    )
    assert status == "INVALID"


def test_20_link_metadata_missing():
    inp = PatchTargetingInput(
        change_id="X",
        document_id="d",
        locator_candidate_id="L",
        semantic_match_id="S",
        template_id="general_report_v1",
        template_node_id="general_report_v1.references.entries",
        requested_operation="LINK",
        match_status="MATCHED",
        combined_score=0.9,
        score_margin=0.2,
        ambiguity_status="CLEAR",
        metadata={},
    )
    nodes = load_generic_node_candidates()
    node = next(n for n in nodes if n.field_id == "entries")
    status, reasons, _ = evaluate_eligibility(
        inp,
        node_exists=True,
        node_allowed_operations=node.allowed_operations,
        node_template_id=node.template_id,
    )
    assert status == "BLOCKED"
    assert "LINK_METADATA_MISSING" in reasons


def test_21_negative_duplicate_intent_id():
    pkg = run_patch_targeting_engine()
    intents = [
        PatchIntent(**{**pkg["intents"][0]}),
        PatchIntent(**{**pkg["intents"][0]}),
    ]
    targets = [PatchTargetCandidate(**pkg["targets"][0])]
    previews = [ActivationPreview(**pkg["previews"][0])]
    nodes = {t["template_node_id"] for t in pkg["targets"] if t["template_node_id"]}
    v = validate_patch_targeting(
        intents=intents,
        targets=targets,
        previews=previews,
        input_change_ids={pkg["intents"][0]["change_id"]},
        known_nodes=nodes,
        summary=None,
    )
    assert "duplicate_patch_intent_id" in v["issues"]


def test_22_negative_summary_tamper():
    pkg = run_patch_targeting_engine()
    from document_ai.patch_targeting.orchestrator import process_one
    from document_ai.patch_targeting.orchestrator import build_summary

    inputs = sample_patch_targeting_inputs()
    nodes = load_generic_node_candidates()
    intents, targets, previews = [], [], []
    for seq, inp in enumerate(sorted(inputs, key=lambda x: x.change_id), start=1):
        i, t, p = process_one(inp, seq=seq, nodes=nodes)
        intents.append(i)
        targets.append(t)
        previews.append(p)
    bad = dict(pkg["summary"])
    bad["eligible_count"] = 999
    v = validate_patch_targeting(
        intents=intents,
        targets=targets,
        previews=previews,
        input_change_ids={i.change_id for i in inputs},
        known_nodes={n.template_node_id for n in nodes},
        summary=bad,
    )
    assert any("summary_" in i for i in v["issues"])


def test_23_negative_broken_preview_link():
    pkg = run_patch_targeting_engine()
    intents = [PatchIntent(**pkg["intents"][0])]
    targets = [PatchTargetCandidate(**pkg["targets"][0])]
    bad_prev = dict(pkg["previews"][0])
    bad_prev["target_candidate_id"] = "PTC-MISSING"
    previews = [ActivationPreview(**bad_prev)]
    v = validate_patch_targeting(
        intents=intents,
        targets=targets,
        previews=previews,
        input_change_ids={intents[0].change_id},
        known_nodes={targets[0].template_node_id} if targets[0].template_node_id else set(),
        summary=None,
    )
    assert any("broken_preview_target_link" in i for i in v["issues"])


def test_24_negative_unknown_node_resolved():
    pkg = run_patch_targeting_engine()
    intents = [PatchIntent(**pkg["intents"][0])]
    t = dict(pkg["targets"][0])
    t["template_node_id"] = "general_report_v1.no.such"
    t["target_status"] = "RESOLVED"
    targets = [PatchTargetCandidate(**t)]
    previews = [ActivationPreview(**pkg["previews"][0])]
    v = validate_patch_targeting(
        intents=intents,
        targets=targets,
        previews=previews,
        input_change_ids={intents[0].change_id},
        known_nodes=set(),
        summary=None,
    )
    assert any("invalid_node_ref" in i for i in v["issues"])


def test_25_pr18_regression():
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
    _ = run_patch_targeting_engine()
    b = run_template_abstraction_layer(review_items=items)
    assert items == snap
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_26_pr19_regression():
    a = run_generic_document_template_pack()
    _ = run_patch_targeting_engine()
    b = run_generic_document_template_pack()
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_27_pr20_regression():
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
    _ = run_patch_targeting_engine()
    b = run_document_structure_mapping_engine(**kwargs)
    assert a["summary"]["section_count"] == b["summary"]["section_count"]


def test_28_pr21_regression():
    a = run_semantic_locator_engine(emit_all_ranks=False)
    _ = run_patch_targeting_engine()
    b = run_semantic_locator_engine(emit_all_ranks=False)
    assert a["summary"]["matched_count"] == b["summary"]["matched_count"]


def test_29_freeze_and_flags():
    assert is_docx_activation_enabled(env={}) is False
    for p in FROZEN:
        assert p.exists()
    pkg = run_patch_targeting_engine()
    assert pkg["actual_docx_changed"] is False
    assert pkg["actual_patch_created"] is False
    assert pkg["actual_writer_called"] is False


def test_30_would_modify_on_eligible_update():
    pkg = run_patch_targeting_engine()
    intents, _, previews = _by_change(pkg)
    p = previews[intents["CHG-001"]["patch_intent_id"]]
    assert p["would_modify_document"] is True
    assert p["blocked"] is True


def test_31_operation_counts():
    s = run_patch_targeting_engine()["summary"]
    assert "UPDATE" in s["operation_counts"]
    assert "ADD" in s["operation_counts"]


def test_32_intent_target_preview_linkage():
    pkg = run_patch_targeting_engine()
    intent_ids = {i["patch_intent_id"] for i in pkg["intents"]}
    assert all(t["patch_intent_id"] in intent_ids for t in pkg["targets"])
    target_ids = {t["patch_target_candidate_id"] for t in pkg["targets"]}
    assert all(p["target_candidate_id"] in target_ids for p in pkg["previews"])


def test_33_no_preview_ready_by_default():
    pkg = run_patch_targeting_engine()
    assert pkg["summary"]["preview_ready_count"] == 0


def test_34_actual_markers_on_eligible():
    pkg = run_patch_targeting_engine()
    intents, _, _ = _by_change(pkg)
    i = intents["CHG-001"]
    assert "ACTUAL_PATCH_NOT_CREATED" in i["reason_codes"]
    assert "ACTUAL_DOCUMENT_UNCHANGED" in i["reason_codes"]
    assert "PATCH_INTENT_CREATED" in i["reason_codes"]


def test_35_template_mismatch_invalid():
    inp = PatchTargetingInput(
        change_id="X",
        document_id="d",
        locator_candidate_id="L",
        semantic_match_id="S",
        template_id="general_report_v1",
        template_node_id="business_proposal_v1.overview.body",
        requested_operation="UPDATE",
        proposed_text="a",
        match_status="MATCHED",
        combined_score=0.9,
        score_margin=0.2,
    )
    status, reasons, _ = evaluate_eligibility(
        inp,
        node_exists=True,
        node_allowed_operations=["UPDATE"],
        node_template_id="business_proposal_v1",
    )
    assert status == "INVALID"
    assert "TEMPLATE_MISMATCH" in reasons


def test_36_node_not_found_invalid():
    inp = PatchTargetingInput(
        change_id="X",
        document_id="d",
        locator_candidate_id="L",
        semantic_match_id="S",
        template_id="general_report_v1",
        template_node_id="general_report_v1.missing.field",
        requested_operation="UPDATE",
        proposed_text="a",
        match_status="MATCHED",
        combined_score=0.9,
        score_margin=0.2,
    )
    status, reasons, _ = evaluate_eligibility(inp, node_exists=False)
    assert status == "INVALID"
    assert "NODE_NOT_FOUND" in reasons


def test_37_operation_not_allowed_blocked():
    inp = PatchTargetingInput(
        change_id="X",
        document_id="d",
        locator_candidate_id="L",
        semantic_match_id="S",
        template_id="general_report_v1",
        template_node_id="general_report_v1.document.title",
        requested_operation="ADD",
        proposed_text="a",
        match_status="MATCHED",
        combined_score=0.9,
        score_margin=0.2,
        metadata={"parent_section_id": "document"},
    )
    # title only allows UPDATE/REPLACE
    status, reasons, _ = evaluate_eligibility(
        inp,
        node_exists=True,
        node_allowed_operations=["UPDATE", "REPLACE"],
        node_template_id="general_report_v1",
    )
    assert status == "BLOCKED"
    assert "OPERATION_TEMPLATE_NOT_ALLOWED" in reasons


def test_38_activation_disabled_reason():
    caps = evaluate_capabilities("UPDATE", allowed_operations=["UPDATE"])
    assert "ACTIVATION_DISABLED" in caps["reason_codes"]
    assert "OBSERVATIONAL_GATE_FORCED_OFF" in caps["reason_codes"]
    assert "ACTUAL_WRITER_NOT_CALLED" in caps["reason_codes"]
    assert caps["activation_allowed"] is False
    assert caps["observational_gate_forced_off"] is True


def test_39_engine_flags():
    pkg = run_patch_targeting_engine()
    assert pkg["validation"]["invariants"]["no_llm"] is True
    assert pkg["validation"]["invariants"]["docx_writer_non_mutation"] is True
    assert pkg["validation"]["invariants"]["activation_always_disabled"] is True
    assert pkg["validation"]["invariants"]["actual_writer_called_false"] is True
    assert pkg["validation"]["invariants"]["semantic_match_reference_valid"] is True


def test_40_weak_evidence_delete():
    pkg = run_patch_targeting_engine()
    intents, _, _ = _by_change(pkg)
    assert intents["CHG-006"]["intent_status"] == "REVIEW_REQUIRED"


def test_41_input_sorted_deterministic():
    pkg = run_patch_targeting_engine()
    ids = [i["change_id"] for i in pkg["inputs"]]
    assert ids == sorted(ids)


def test_42_unknown_semantic_match_id_detected():
    pkg = run_patch_targeting_engine()
    intents = [PatchIntent(**pkg["intents"][0])]
    targets = [PatchTargetCandidate(**pkg["targets"][0])]
    previews = [ActivationPreview(**pkg["previews"][0])]
    known_nodes = {t.template_node_id for t in targets if t.template_node_id}
    v = validate_patch_targeting(
        intents=intents,
        targets=targets,
        previews=previews,
        input_change_ids={intents[0].change_id},
        known_nodes=known_nodes,
        summary=None,
        known_semantic_match_ids={"SM-DOES-NOT-EXIST"},
    )
    assert any(
        i.startswith("unknown_semantic_match_id:") for i in v["issues"]
    )
    assert v["invariants"]["semantic_match_reference_valid"] is False


def test_43_known_semantic_match_ids_none_compatible():
    """None skips reference check — sample fixtures remain valid."""
    pkg = run_patch_targeting_engine()
    assert pkg["validation"]["status"] == "VALID"
    assert pkg["validation"]["invariants"]["semantic_match_reference_valid"] is True
