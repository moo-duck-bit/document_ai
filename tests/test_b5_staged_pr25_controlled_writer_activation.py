# -*- coding: utf-8 -*-
"""PR-25: Controlled Writer Activation tests."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from document_ai.controlled_writer.approval import evaluate_approval, make_approval
from document_ai.controlled_writer.capability_gate import (
    evaluate_controlled_activation,
    is_controlled_writer_enabled,
)
from document_ai.controlled_writer.copy_workspace import ensure_copy, file_sha256
from document_ai.controlled_writer.diff_engine import build_diff
from document_ai.controlled_writer.orchestrator import (
    prepare_sample_inputs,
    run_controlled_writer_engine,
)
from document_ai.controlled_writer.rollback import create_rollback_point, rollback_to_point
from document_ai.controlled_writer.schema import ControlledWriterInput
from document_ai.document_parser.parser import run_document_structure_mapping_engine
from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.patch_contract.orchestrator import run_patch_contract_engine
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


def _engine(tmp_path: Path | None = None, env=None):
    td = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp(prefix="cw25t_"))
    return run_controlled_writer_engine(work_dir=td, env=env), td


def _by_case(pkg):
    out = {}
    for inp, res in zip(pkg["inputs"], pkg["writer_results"]):
        out[inp["metadata"]["case"]] = {"input": inp, "result": res}
    return out


def test_01_paragraph_update_applied():
    pkg, _ = _engine()
    row = _by_case(pkg)["paragraph_update"]
    assert row["result"]["result_status"] == "APPLIED"
    assert row["result"]["copy_modified"] is True
    assert row["result"]["original_unchanged"] is True


def test_02_table_update_applied():
    pkg, _ = _engine()
    assert _by_case(pkg)["table_update"]["result"]["result_status"] == "APPLIED"


def test_03_list_update_applied():
    pkg, _ = _engine()
    assert _by_case(pkg)["list_update"]["result"]["result_status"] == "APPLIED"


def test_04_add_applied():
    pkg, _ = _engine()
    row = _by_case(pkg)["add"]
    assert row["result"]["result_status"] == "APPLIED"
    copy_path = Path(row["result"]["copy_path"])
    assert "검수 단계 추가" in copy_path.read_text(encoding="utf-8")


def test_05_delete_with_approval():
    pkg, _ = _engine()
    row = _by_case(pkg)["delete"]
    assert row["result"]["result_status"] == "APPLIED"
    text = Path(row["result"]["copy_path"]).read_text(encoding="utf-8")
    assert "일정 본문" not in text
    assert "Keep me" in text


def test_06_link_applied():
    pkg, _ = _engine()
    row = _by_case(pkg)["link"]
    assert row["result"]["result_status"] == "APPLIED"
    text = Path(row["result"]["copy_path"]).read_text(encoding="utf-8")
    assert "https://example.com/doc" in text


def test_07_approval_reject():
    pkg, _ = _engine()
    row = _by_case(pkg)["approval_reject"]
    assert row["result"]["result_status"] == "REJECTED"
    assert row["result"]["actual_writer_called"] is False
    src = Path(row["input"]["source_path"]).read_text(encoding="utf-8")
    assert "reject me" in src


def test_08_rollback():
    pkg, _ = _engine()
    row = _by_case(pkg)["rollback"]
    assert row["result"]["result_status"] == "ROLLED_BACK"
    assert row["result"]["rollback_id"]
    assert any(r["rollback_id"] == row["result"]["rollback_id"] for r in pkg["rollbacks"])


def test_09_diff_generated_for_applied():
    pkg, _ = _engine()
    applied = [r for r in pkg["writer_results"] if r["result_status"] == "APPLIED"]
    assert applied
    assert pkg["diffs"]
    for r in applied:
        assert r["diff_id"]
        assert any(d["diff_id"] == r["diff_id"] for d in pkg["diffs"])


def test_10_validation_valid():
    pkg, _ = _engine()
    assert pkg["validation"]["status"] == "VALID"
    assert pkg["validation"]["invariants"]["originals_unchanged"] is True


def test_11_feature_flag_off_blocks():
    pkg, _ = _engine()
    row = _by_case(pkg)["feature_flag_off"]
    assert row["result"]["result_status"] == "BLOCKED"
    assert row["result"]["copy_modified"] is False


def test_12_copy_only_original_not_changed():
    pkg, td = _engine()
    for inp in pkg["inputs"]:
        src = Path(inp["source_path"])
        assert src.exists()
    for r in pkg["writer_results"]:
        assert r["original_unchanged"] is True
        assert r["actual_original_changed"] is False
        if r["result_status"] == "APPLIED":
            assert Path(r["copy_path"]).exists()
            assert Path(r["copy_path"]).resolve() != Path(r["source_path"]).resolve()


def test_13_docx_paragraph_update():
    pkg, _ = _engine()
    assert _by_case(pkg)["docx_paragraph_update"]["result"]["result_status"] == "APPLIED"


def test_14_docx_table_update():
    pkg, _ = _engine()
    assert _by_case(pkg)["docx_table_update"]["result"]["result_status"] == "APPLIED"


def test_15_stale_fingerprint_blocked():
    pkg, _ = _engine()
    row = _by_case(pkg)["stale_fingerprint"]
    assert row["result"]["result_status"] == "BLOCKED"
    assert "FINGERPRINT_INVALID" in row["result"]["reason_codes"]


def test_16_unsupported_writer_blocked():
    pkg, _ = _engine()
    assert _by_case(pkg)["unsupported_writer"]["result"]["result_status"] == "BLOCKED"


def test_17_delete_without_approval_blocked():
    td = Path(tempfile.mkdtemp(prefix="cw25del_"))
    inputs = prepare_sample_inputs(td / "fx")
    delete = next(i for i in inputs if i.metadata.get("case") == "delete")
    delete.approval = make_approval(
        approval_id="APR-X",
        patch_contract_id=delete.patch_contract_id,
        decision="AUTO_APPROVED",
    )
    pkg = run_controlled_writer_engine(inputs=[delete], work_dir=td / "w")
    assert pkg["writer_results"][0]["result_status"] in ("REJECTED", "BLOCKED")
    assert "DELETE_REQUIRES_EXPLICIT_APPROVAL" in pkg["writer_results"][0]["reason_codes"]


def test_18_env_flags_both_required():
    td = Path(tempfile.mkdtemp(prefix="cw25env_"))
    inputs = prepare_sample_inputs(td / "fx")
    para = next(i for i in inputs if i.metadata.get("case") == "paragraph_update")
    pkg = run_controlled_writer_engine(
        inputs=[para],
        work_dir=td / "w",
        env={"DOCX_ACTIVATION_ENABLED": "true", "CONTROLLED_WRITER_ENABLED": "false"},
    )
    assert pkg["writer_results"][0]["result_status"] == "BLOCKED"


def test_19_docx_flag_alone_insufficient():
    assert is_docx_activation_enabled(env={"DOCX_ACTIVATION_ENABLED": "true"}) is True
    assert is_controlled_writer_enabled(env={"CONTROLLED_WRITER_ENABLED": "false"}) is False
    gate = evaluate_controlled_activation(
        requested_operation="UPDATE",
        writer_adapter="MARKDOWN_BLOCK_WRITER",
        span_kind="SOURCE_ABSOLUTE",
        fingerprint_ok=True,
        approval_ok=True,
        contract_status="CONTRACT_READY_FOR_REVIEW",
        env={"DOCX_ACTIVATION_ENABLED": "true", "CONTROLLED_WRITER_ENABLED": "false"},
    )
    assert gate["activation_allowed"] is False


def test_20_span_kind_not_absolute_blocked():
    gate = evaluate_controlled_activation(
        requested_operation="UPDATE",
        writer_adapter="MARKDOWN_BLOCK_WRITER",
        span_kind="ESTIMATED_BLOCK_LOCAL",
        fingerprint_ok=True,
        approval_ok=True,
        contract_status="CONTRACT_READY_FOR_REVIEW",
        env={"DOCX_ACTIVATION_ENABLED": "true", "CONTROLLED_WRITER_ENABLED": "true"},
    )
    assert gate["activation_allowed"] is False
    assert "SPAN_KIND_NOT_SOURCE_ABSOLUTE" in gate["reason_codes"]


def test_21_ensure_copy_does_not_touch_source():
    td = Path(tempfile.mkdtemp(prefix="cw25cp_"))
    src = td / "orig.md"
    src.write_text("hello\n", encoding="utf-8")
    fp = file_sha256(src)
    info = ensure_copy(src, td / "copies")
    assert info["ok"] is True
    assert file_sha256(src) == fp
    assert Path(info["copy_path"]).read_text(encoding="utf-8") == "hello\n"


def test_22_rollback_restores_snapshot():
    td = Path(tempfile.mkdtemp(prefix="cw25rb_"))
    copy = td / "c.md"
    copy.write_text("before\n", encoding="utf-8")
    rb = create_rollback_point(
        rollback_id="RB-T",
        patch_contract_id="PCT-T",
        copy_path=copy,
        snapshot_dir=td / "snaps",
    )
    copy.write_text("mutated\n", encoding="utf-8")
    out = rollback_to_point(rb)
    assert out["ok"] is True
    assert copy.read_text(encoding="utf-8") == "before\n"


def test_23_diff_engine_fields():
    d = build_diff(
        diff_id="D1",
        patch_contract_id="P1",
        before_text="a\nb\n",
        after_text="a\nc\n",
        operation="UPDATE",
    )
    assert d.operation_count == 1
    assert d.changed_blocks
    assert d.before_text != d.after_text


def test_24_approval_schema_fields():
    a = make_approval(
        approval_id="A1",
        patch_contract_id="P1",
        decision="APPROVED",
        approved_by="u",
        approved_at="t",
        reason="ok",
    )
    d = a.to_dict()
    for k in (
        "approval_id",
        "patch_contract_id",
        "decision",
        "approved_by",
        "approved_at",
        "reason",
    ):
        assert k in d


def test_25_evaluate_approval_missing():
    inp = ControlledWriterInput(
        writer_input_id="x",
        patch_contract_id="p",
        change_id="c",
        document_id="d",
        requested_operation="UPDATE",
        proposed_text="a",
        original_text="b",
        contract_status="CONTRACT_READY_FOR_REVIEW",
        writer_adapter="MARKDOWN_BLOCK_WRITER",
        source_path="x.md",
        approval=None,
    )
    assert evaluate_approval(inp)["approved"] is False


def test_26_summary_counts():
    pkg, _ = _engine()
    s = pkg["summary"]
    assert s["input_count"] == len(pkg["inputs"])
    assert s["original_changed_count"] == 0
    assert s["patch_success_count"] == s["result_status_counts"].get("APPLIED", 0)


def test_27_artifacts_keys_present():
    pkg, _ = _engine()
    for k in (
        "approvals",
        "writer_plans",
        "writer_results",
        "diffs",
        "rollbacks",
        "validation",
        "summary",
    ):
        assert k in pkg


def test_28_pr18_regression():
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
    _engine()
    b = run_template_abstraction_layer(review_items=items)
    assert items == snap
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_29_pr19_regression():
    a = run_generic_document_template_pack()
    _engine()
    b = run_generic_document_template_pack()
    assert a["summary"]["mapped_count"] == b["summary"]["mapped_count"]


def test_30_pr20_regression():
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
    _engine()
    b = run_document_structure_mapping_engine(**kwargs)
    assert a["summary"]["section_count"] == b["summary"]["section_count"]


def test_31_pr21_regression():
    a = run_semantic_locator_engine(emit_all_ranks=False)
    _engine()
    b = run_semantic_locator_engine(emit_all_ranks=False)
    assert a["summary"]["matched_count"] == b["summary"]["matched_count"]


def test_32_pr22_regression():
    a = run_patch_targeting_engine()
    _engine()
    b = run_patch_targeting_engine()
    assert a["summary"]["eligible_count"] == b["summary"]["eligible_count"]
    assert a["summary"]["activation_allowed_count"] == 0


def test_33_pr23_regression():
    a = run_physical_locator_engine()
    _engine()
    b = run_physical_locator_engine()
    assert a["summary"]["resolved_count"] == b["summary"]["resolved_count"]
    assert a["activation_allowed"] is False


def test_34_pr24_regression():
    a = run_patch_contract_engine()
    _engine()
    b = run_patch_contract_engine()
    assert a["summary"]["ready_for_review_count"] == b["summary"]["ready_for_review_count"]
    assert a["activation_allowed"] is False
    assert a["contract_executable"] is False


def test_35_freeze():
    for p in FROZEN:
        assert p.exists()


def test_36_sample_input_count():
    td = Path(tempfile.mkdtemp(prefix="cw25n_"))
    assert len(prepare_sample_inputs(td)) >= 13


def test_37_writer_plan_activation_false_when_blocked():
    pkg, _ = _engine()
    for plan, res in zip(pkg["writer_plans"], pkg["writer_results"]):
        if res["result_status"] == "BLOCKED":
            assert plan["activation_allowed"] is False


def test_38_applied_has_writer_called():
    pkg, _ = _engine()
    for r in pkg["writer_results"]:
        if r["result_status"] == "APPLIED":
            assert r["actual_writer_called"] is True
            assert r["actual_document_changed"] is True  # copy


def test_39_rejected_no_writer_call():
    pkg, _ = _engine()
    r = _by_case(pkg)["approval_reject"]["result"]
    assert r["actual_writer_called"] is False


def test_40_diff_changed_paragraphs_present():
    pkg, _ = _engine()
    d = next(d for d in pkg["diffs"] if d["operation_count"] >= 1)
    assert "changed_paragraphs" in d
    assert "changed_blocks" in d
    assert "changed_tables" in d


def test_41_deterministic_result_ids():
    a, _ = _engine()
    b, _ = _engine()
    assert [r["writer_result_id"] for r in a["writer_results"]] == [
        r["writer_result_id"] for r in b["writer_results"]
    ]


def test_42_source_content_unchanged_after_apply():
    pkg, _ = _engine()
    row = _by_case(pkg)["paragraph_update"]
    src = Path(row["input"]["source_path"]).read_text(encoding="utf-8")
    assert "내부 artifact 및 샘플 fixture" in src
    assert "공개 데이터셋" not in src


def test_43_copy_contains_new_text():
    pkg, _ = _engine()
    row = _by_case(pkg)["paragraph_update"]
    copy_text = Path(row["result"]["copy_path"]).read_text(encoding="utf-8")
    assert "공개 데이터셋" in copy_text


def test_44_validation_patch_success_matches():
    pkg, _ = _engine()
    assert (
        pkg["validation"]["patch_success_count"]
        == pkg["summary"]["patch_success_count"]
    )


def test_45_link_missing_metadata_fails_or_blocks():
    td = Path(tempfile.mkdtemp(prefix="cw25link_"))
    inputs = prepare_sample_inputs(td / "fx")
    link = next(i for i in inputs if i.metadata.get("case") == "link")
    link.link_metadata = None
    pkg = run_controlled_writer_engine(inputs=[link], work_dir=td / "w")
    # may apply gate then fail write → ROLLED_BACK, or still attempt
    assert pkg["writer_results"][0]["result_status"] in (
        "ROLLED_BACK",
        "FAILED",
        "BLOCKED",
    )


def test_46_manual_required_not_approved():
    a = make_approval(
        approval_id="A",
        patch_contract_id="P",
        decision="MANUAL_REQUIRED",
    )
    inp = ControlledWriterInput(
        writer_input_id="x",
        patch_contract_id="p",
        change_id="c",
        document_id="d",
        requested_operation="UPDATE",
        proposed_text="a",
        original_text="b",
        contract_status="CONTRACT_READY_FOR_REVIEW",
        writer_adapter="MARKDOWN_BLOCK_WRITER",
        source_path="x.md",
        approval=a,
    )
    assert evaluate_approval(inp)["approved"] is False


def test_47_all_gates_pass_activation_true():
    gate = evaluate_controlled_activation(
        requested_operation="UPDATE",
        writer_adapter="MARKDOWN_BLOCK_WRITER",
        span_kind="SOURCE_ABSOLUTE",
        fingerprint_ok=True,
        approval_ok=True,
        contract_status="CONTRACT_READY_FOR_REVIEW",
        env={"DOCX_ACTIVATION_ENABLED": "true", "CONTROLLED_WRITER_ENABLED": "true"},
    )
    assert gate["activation_allowed"] is True


def test_48_json_serializable():
    pkg, _ = _engine()
    json.dumps(pkg["writer_results"], ensure_ascii=False)
    json.dumps(pkg["diffs"], ensure_ascii=False)
    json.dumps(pkg["rollbacks"], ensure_ascii=False)


def test_49_rollback_points_created_before_successful_writes():
    pkg, _ = _engine()
    for r in pkg["writer_results"]:
        if r["result_status"] == "APPLIED":
            assert r["rollback_id"]
            rb = next(x for x in pkg["rollbacks"] if x["rollback_id"] == r["rollback_id"])
            assert rb["created_before_write"] is True
            assert Path(rb["snapshot_path"]).exists()


def test_50_global_original_changed_zero():
    pkg, _ = _engine()
    assert pkg["summary"]["original_changed_count"] == 0


def test_51_contract_not_ready_blocks():
    gate = evaluate_controlled_activation(
        requested_operation="UPDATE",
        writer_adapter="MARKDOWN_BLOCK_WRITER",
        span_kind="SOURCE_ABSOLUTE",
        fingerprint_ok=True,
        approval_ok=True,
        contract_status="CONTRACT_BLOCKED",
        env={"DOCX_ACTIVATION_ENABLED": "true", "CONTROLLED_WRITER_ENABLED": "true"},
    )
    assert gate["activation_allowed"] is False


def test_52_replace_operation_works():
    td = Path(tempfile.mkdtemp(prefix="cw25rep_"))
    inputs = prepare_sample_inputs(td / "fx")
    para = next(i for i in inputs if i.metadata.get("case") == "paragraph_update")
    para.requested_operation = "REPLACE"
    pkg = run_controlled_writer_engine(inputs=[para], work_dir=td / "w")
    assert pkg["writer_results"][0]["result_status"] == "APPLIED"
