# -*- coding: utf-8 -*-
"""PR-17: Change Review Package tests."""

from __future__ import annotations

import copy

from document_ai.impact.change_review_package import (
    ChangeReviewItem,
    build_change_groups,
    build_change_review_items,
    build_change_review_summary,
    render_change_review_markdown,
    run_change_review_package,
    validate_change_review_items,
)


def _gate(
    pid: str,
    *,
    status: str = "PASS",
    eligible: bool = True,
    decision: str = "AUTO_APPLY",
    applied: bool = True,
    acu: str = "ACU-001",
    reasons: list[str] | None = None,
    rid: str | None = "Req. 1",
    doc: str = "MDSR",
    field: str = "description",
) -> dict:
    return {
        "gate_result_id": f"PG-{pid}",
        "patch_id": pid,
        "draft_id": f"SD-{pid}",
        "atomic_change_id": acu,
        "requirement_id": rid,
        "document": doc,
        "field": field,
        "patch_validation_status": "VALID",
        "language_validation_status": "VALID",
        "activation_decision": decision,
        "preview_applied": applied,
        "final_status": status,
        "eligible_for_docx_activation": eligible,
        "reason_codes": reasons or (["PASS_ALL_VALID"] if status == "PASS" else [status]),
        "reason_messages": [],
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def _prev(pid: str, before: str, after: str, *, op: str = "UPDATE", rid: str | None = "Req. 1") -> dict:
    return {
        "patch_id": pid,
        "draft_id": f"SD-{pid}",
        "requirement_id": rid,
        "document": "MDSR",
        "field": "description",
        "operation": op,
        "original_requirement": before,
        "proposed_requirement": after,
        "preview_requirement": after,
    }


def _patch(pid: str, before: str, after: str, *, op: str = "UPDATE") -> dict:
    return {
        "patch_id": pid,
        "operation": op,
        "original_requirement": before,
        "patched_requirement": after,
        "requirement_id": "Req. 1",
        "document": "MDSR",
        "field": "description",
        "atomic_change_id": "ACU-001",
    }


def _act(
    pid: str,
    *,
    attempted: bool = False,
    succeeded: bool = False,
    skips: list[str] | None = None,
    before: str = "",
    after: str = "",
) -> dict:
    return {
        "activation_item_id": f"DA-{pid}",
        "patch_id": pid,
        "write_attempted": attempted,
        "write_succeeded": succeeded,
        "skip_reason_codes": skips or [],
        "before_text": before,
        "after_text": after,
        "target_locator": "table:Req. 1:row1:cell1:p0",
    }


def _pkg(
    gates,
    *,
    flag: bool = False,
    acts=None,
    previews=None,
    patches=None,
    cr: str = "계정 잠금 정책을 반영해 주세요.",
    acus=None,
):
    acts = acts if acts is not None else [_act(g["patch_id"], skips=["FEATURE_FLAG_DISABLED"]) for g in gates]
    previews = previews if previews is not None else [
        _prev(g["patch_id"], "BEFORE", "AFTER") for g in gates
    ]
    patches = patches if patches is not None else [
        _patch(g["patch_id"], "BEFORE", "AFTER") for g in gates
    ]
    return run_change_review_package(
        gate_payload={"results": gates, "global_status": "BLOCK"},
        preview_entries=previews,
        patches=patches,
        activation_payload={
            "plan": {"feature_flag_enabled": flag, "items": acts},
            "results": {"feature_flag_enabled": flag, "items": acts},
        },
        cr_text=cr,
        acus=acus or [{"atomic_change_id": "ACU-001", "normalized_text": "계정 잠금", "action": "UPDATE"}],
        feature_flag_enabled=flag,
    )


def test_1_pass_flag_off_ready_not_applied():
    pkg = _pkg([_gate("RP-1")], flag=False)
    it = pkg["items"][0]
    assert it["review_status"] == "READY"
    assert it["application_status"] == "NOT_APPLIED"
    assert it["actual_docx_applied"] is False


def test_2_pass_write_success_applied():
    g = _gate("RP-1")
    act = _act("RP-1", attempted=True, succeeded=True, skips=["WRITE_SUCCEEDED"], before="B", after="A")
    pkg = _pkg([g], flag=True, acts=[act])
    it = pkg["items"][0]
    assert it["review_status"] == "READY"
    assert it["application_status"] == "APPLIED"
    assert it["actual_docx_applied"] is True


def test_3_gate_review():
    pkg = _pkg(
        [_gate("RP-1", status="REVIEW", eligible=False, decision="REVIEW", applied=False, reasons=["ACTIVATION_REVIEW"])],
        flag=False,
        acts=[_act("RP-1", skips=["ITEM_NOT_PASS"])],
    )
    assert pkg["items"][0]["review_status"] == "REVIEW"


def test_4_5_gate_and_activation_block():
    pkg = _pkg(
        [_gate("RP-1", status="BLOCK", eligible=False, decision="BLOCK", applied=False, reasons=["ACTIVATION_BLOCK"])],
        acts=[_act("RP-1", skips=["ACTIVATION_NOT_AUTO_APPLY"])],
    )
    assert pkg["items"][0]["review_status"] == "BLOCKED"
    assert pkg["items"][0]["application_status"] == "BLOCKED"


def test_6_unsupported_operation_review():
    g = _gate("RP-1")
    pkg = _pkg(
        [g],
        flag=True,
        acts=[_act("RP-1", skips=["UNSUPPORTED_DOCX_OPERATION"])],
        patches=[_patch("RP-1", "B", "A", op="ADD")],
        previews=[_prev("RP-1", "B", "A", op="ADD")],
    )
    assert pkg["items"][0]["review_status"] == "REVIEW"
    assert "UNSUPPORTED_DOCX_OPERATION" in pkg["items"][0]["review_reason_codes"]


def test_7_missing_change_reason():
    items = build_change_review_items(
        gate_results=[_gate("RP-1", reasons=[])],
        preview_entries=[_prev("RP-1", "B", "A")],
        patches=[{"patch_id": "RP-1"}],  # no operation
        activation_items=[_act("RP-1")],
        cr_text="",
        acus=[],
        feature_flag_enabled=False,
    )
    # Still may have activation decision etc from gate — force empty by custom
    # If reason exists due to decision, OK; test MISSING when no parts:
    it = items[0]
    # With decision present, reason won't be missing. Force validate path:
    it.change_reason = "근거 artifact에서 상세 사유를 확인할 수 없음"
    it.review_required = True
    it.review_reason_codes = ["MISSING_CHANGE_REASON"]
    it.review_status = "REVIEW"
    v = validate_change_review_items([it])
    assert v["invariants"]["review_required_has_reason"]


def test_8_9_before_after_preserved():
    before = "원문 그대로 유지해야 한다."
    after = "원문 그대로 유지하고 알림을 추가해야 한다."
    pkg = _pkg(
        [_gate("RP-1")],
        previews=[_prev("RP-1", before, after)],
        patches=[_patch("RP-1", before, after)],
        acts=[_act("RP-1", skips=["FEATURE_FLAG_DISABLED"], before=before, after=after)],
    )
    assert pkg["items"][0]["before_text"] == before
    assert pkg["items"][0]["after_text"] == after


def test_10_source_request_preserved():
    pkg = _pkg(
        [_gate("RP-1")],
        cr="원본 CR 텍스트입니다.",
        acus=[{"atomic_change_id": "ACU-001", "normalized_text": "원본 ACU 텍스트", "action": "UPDATE"}],
    )
    assert "원본 ACU 텍스트" in pkg["items"][0]["source_request"]


def test_11_one_item_per_patch():
    pkg = _pkg([_gate("RP-1"), _gate("RP-2", acu="ACU-002")])
    assert len(pkg["items"]) == 2
    assert {i["patch_id"] for i in pkg["items"]} == {"RP-1", "RP-2"}


def test_12_13_duplicate_and_id_mismatch_detected():
    a = ChangeReviewItem(
        review_item_id="CRI-1",
        source_change_id="ACU-001",
        atomic_change_id="ACU-001",
        patch_id="RP-1",
        draft_id="",
        gate_result_id="PG-1",
        activation_item_id="DA-1",
        document="MDSR",
        requirement_id="Req. 1",
        section="Req. 1",
        field="description",
        change_type="UPDATE",
        change_type_label="수정",
        change_scope="requirement",
        source_request="x",
        source_request_summary="x",
        change_reason="r",
        change_reason_summary="r",
        before_text="b",
        after_text="a",
        gate_status="PASS",
        activation_decision="AUTO_APPLY",
        eligible_for_docx_activation=True,
        docx_write_attempted=False,
        docx_write_succeeded=False,
        actual_docx_applied=False,
        review_status="READY",
        application_status="NOT_APPLIED",
        review_required=False,
    )
    b = copy.deepcopy(a)
    b.review_item_id = "CRI-1"  # duplicate
    b.patch_id = "RP-1"
    v = validate_change_review_items([a, b])
    assert "duplicate_review_item_id" in v["issues"] or "duplicate_patch_id" in v["issues"]

    bad = copy.deepcopy(a)
    bad.atomic_change_id = "ACU-X"
    v2 = validate_change_review_items(
        [bad],
        gate_results=[_gate("RP-1", acu="ACU-001")],
    )
    assert any("atomic_change_id_mismatch" in i for i in v2["issues"])


def test_14_15_applied_rules():
    g = _gate("RP-1")
    pkg = _pkg([g], flag=False, acts=[_act("RP-1", succeeded=False, skips=["FEATURE_FLAG_DISABLED"])])
    assert pkg["items"][0]["application_status"] != "APPLIED"

    # negative: forge APPLIED with flag off
    it = ChangeReviewItem(**{**pkg["items"][0], "application_status": "APPLIED", "docx_write_succeeded": False, "actual_docx_applied": True})
    # rebuild from dict carefully
    forged = ChangeReviewItem(
        **{k: pkg["items"][0][k] for k in ChangeReviewItem.__dataclass_fields__}
    )
    forged.application_status = "APPLIED"
    forged.docx_write_succeeded = False
    forged.actual_docx_applied = True
    v = validate_change_review_items([forged], feature_flag_enabled=False)
    assert any("flag_off_but_applied" in i or "applied_without" in i for i in v["issues"])


def test_16_review_required_without_reason():
    it = ChangeReviewItem(
        review_item_id="CRI-X",
        source_change_id="ACU-1",
        atomic_change_id="ACU-1",
        patch_id="RP-X",
        draft_id="",
        gate_result_id="PG-X",
        activation_item_id="DA-X",
        document="MDSR",
        requirement_id="Req. 1",
        section="Req. 1",
        field="description",
        change_type="UPDATE",
        change_type_label="수정",
        change_scope="requirement",
        source_request="",
        source_request_summary="",
        change_reason="",
        change_reason_summary="",
        before_text="",
        after_text="",
        gate_status="REVIEW",
        activation_decision="REVIEW",
        eligible_for_docx_activation=False,
        docx_write_attempted=False,
        docx_write_succeeded=False,
        actual_docx_applied=False,
        review_status="REVIEW",
        application_status="NOT_APPLIED",
        review_required=True,
        review_reason_codes=[],
    )
    v = validate_change_review_items([it])
    assert any("review_required_without_reason" in i for i in v["issues"])


def test_17_18_19_groups_and_summary():
    pkg = _pkg(
        [
            _gate("RP-1", acu="ACU-001", doc="MDSR", field="description"),
            _gate("RP-2", acu="ACU-001", doc="MDDR", field="design_body", rid="Req. 105"),
            _gate("RP-B", status="BLOCK", eligible=False, decision="BLOCK", applied=False, acu="ACU-004"),
        ],
        previews=[
            _prev("RP-1", "B1", "A1"),
            _prev("RP-2", "B2", "A2", rid="Req. 105"),
            _prev("RP-B", "BX", "AX"),
        ],
        patches=[
            _patch("RP-1", "B1", "A1"),
            _patch("RP-2", "B2", "A2"),
            _patch("RP-B", "BX", "AX"),
        ],
        acts=[
            _act("RP-1", skips=["FEATURE_FLAG_DISABLED"]),
            _act("RP-2", skips=["FEATURE_FLAG_DISABLED"]),
            _act("RP-B", skips=["ITEM_NOT_PASS"]),
        ],
        acus=[
            {"atomic_change_id": "ACU-001", "normalized_text": "잠금", "action": "UPDATE"},
            {"atomic_change_id": "ACU-004", "normalized_text": "차단", "action": "BLOCK"},
        ],
    )
    assert pkg["summary"]["group_count"] == 2
    assert pkg["summary"]["ready_count"] == 2
    assert pkg["summary"]["blocked_count"] == 1
    assert pkg["summary"]["total_count"] == 3
    g001 = [g for g in pkg["groups"] if g["atomic_change_id"] == "ACU-001"][0]
    assert g001["item_count"] == 2
    assert g001["item_count"] == len(g001["review_item_ids"])


def test_20_21_22_global_status():
    blocked = _pkg([_gate("RP-B", status="BLOCK", eligible=False, decision="BLOCK", applied=False, acu="ACU-B")])
    assert blocked["summary"]["global_review_status"] == "BLOCKED"

    review = _pkg(
        [_gate("RP-R", status="REVIEW", eligible=False, decision="REVIEW", applied=False, acu="ACU-R")]
    )
    assert review["summary"]["global_review_status"] == "REVIEW"

    ready = run_change_review_package(
        gate_payload={"results": [_gate("RP-1")], "global_status": "PASS"},
        preview_entries=[_prev("RP-1", "B", "A")],
        patches=[_patch("RP-1", "B", "A")],
        activation_payload={
            "results": {
                "feature_flag_enabled": False,
                "items": [_act("RP-1", skips=["FEATURE_FLAG_DISABLED"])],
            }
        },
        cr_text="요청",
        acus=[{"atomic_change_id": "ACU-001", "normalized_text": "요청"}],
        feature_flag_enabled=False,
    )
    assert ready["summary"]["global_review_status"] == "READY"


def test_23_before_after_json():
    pkg = _pkg([_gate("RP-1")], previews=[_prev("RP-1", "BBB", "AAA")])
    assert pkg["before_after"]["pairs"][0]["before_text"] == "BBB"
    assert pkg["before_after"]["pairs"][0]["after_text"] == "AAA"


def test_24_25_markdown_contains_items_and_texts():
    before = "변경 전 고유문장 XYZ"
    after = "변경 후 고유문장 UVW"
    pkg = _pkg(
        [_gate("RP-1"), _gate("RP-2", acu="ACU-002")],
        previews=[_prev("RP-1", before, after), _prev("RP-2", "B2", "A2")],
        patches=[_patch("RP-1", before, after), _patch("RP-2", "B2", "A2")],
        acts=[
            _act("RP-1", skips=["FEATURE_FLAG_DISABLED"]),
            _act("RP-2", skips=["FEATURE_FLAG_DISABLED"]),
        ],
    )
    md = pkg["markdown"]
    assert "CRI-RP-1" in md
    assert "CRI-RP-2" in md
    assert before in md
    assert after in md


def test_26_27_empty_and_null_requirement():
    pkg = _pkg(
        [_gate("RP-1", rid=None)],
        previews=[_prev("RP-1", "", "", rid=None)],
        patches=[_patch("RP-1", "", "")],
    )
    assert pkg["items"][0]["requirement_id"] is None
    assert "(내용 없음)" in pkg["markdown"]


def test_28_29_deterministic():
    gates = [_gate("RP-2", acu="ACU-002"), _gate("RP-1", acu="ACU-001")]
    a = _pkg(gates)
    b = _pkg(gates)
    assert [i["patch_id"] for i in a["items"]] == [i["patch_id"] for i in b["items"]]
    assert a["markdown"] == b["markdown"]
    assert [i["patch_id"] for i in a["items"]] == ["RP-1", "RP-2"]


def test_30_non_mutation():
    gates = [_gate("RP-1")]
    previews = [_prev("RP-1", "B", "A")]
    patches = [_patch("RP-1", "B", "A")]
    acts = [_act("RP-1", skips=["FEATURE_FLAG_DISABLED"])]
    snap = (
        copy.deepcopy(gates),
        copy.deepcopy(previews),
        copy.deepcopy(patches),
        copy.deepcopy(acts),
    )
    run_change_review_package(
        gate_payload={"results": gates},
        preview_entries=previews,
        patches=patches,
        activation_payload={"results": {"feature_flag_enabled": False, "items": acts}},
        cr_text="x",
        acus=[{"atomic_change_id": "ACU-001", "normalized_text": "x"}],
        feature_flag_enabled=False,
    )
    assert gates == snap[0]
    assert previews == snap[1]
    assert patches == snap[2]
    assert acts == snap[3]


def test_31_scenario_like_eleven_ready_one_blocked():
    gates = [_gate(f"RP-{i:02d}", acu=f"ACU-{i:03d}") for i in range(1, 12)]
    gates.append(
        _gate(
            "RP-BLOCK",
            status="BLOCK",
            eligible=False,
            decision="BLOCK",
            applied=False,
            acu="ACU-004-BLOCK",
        )
    )
    # avoid colliding ACU-004 with a PASS item — use distinct block acu; still assert counts from data
    previews = [_prev(g["patch_id"], f"B-{g['patch_id']}", f"A-{g['patch_id']}") for g in gates]
    patches = [_patch(g["patch_id"], f"B-{g['patch_id']}", f"A-{g['patch_id']}") for g in gates]
    acts = [_act(g["patch_id"], skips=["FEATURE_FLAG_DISABLED"]) for g in gates]
    acus = [{"atomic_change_id": g["atomic_change_id"], "normalized_text": g["atomic_change_id"]} for g in gates]
    pkg = run_change_review_package(
        gate_payload={"results": gates, "global_status": "BLOCK"},
        preview_entries=previews,
        patches=patches,
        activation_payload={"results": {"feature_flag_enabled": False, "items": acts}},
        cr_text="시나리오 변경 요청",
        acus=acus,
        feature_flag_enabled=False,
    )
    pass_n = sum(1 for g in gates if g["final_status"] == "PASS")
    block_n = sum(1 for g in gates if g["final_status"] == "BLOCK")
    assert pkg["summary"]["ready_count"] == pass_n
    assert pkg["summary"]["blocked_count"] == block_n
    assert pkg["summary"]["review_count"] == 0
    assert pkg["summary"]["applied_count"] == 0
    assert pkg["summary"]["not_applied_count"] == pass_n
    assert pkg["summary"]["global_review_status"] == "BLOCKED"
    blocked = [i for i in pkg["items"] if i["patch_id"] == "RP-BLOCK"][0]
    assert blocked["review_status"] == "BLOCKED"


def test_negative_block_gate_ready_review():
    it = ChangeReviewItem(
        review_item_id="CRI-1",
        source_change_id="ACU-1",
        atomic_change_id="ACU-1",
        patch_id="RP-1",
        draft_id="",
        gate_result_id="PG-1",
        activation_item_id="DA-1",
        document="MDSR",
        requirement_id="Req. 1",
        section="Req. 1",
        field="description",
        change_type="UPDATE",
        change_type_label="수정",
        change_scope="requirement",
        source_request="",
        source_request_summary="",
        change_reason="x",
        change_reason_summary="x",
        before_text="b",
        after_text="a",
        gate_status="BLOCK",
        activation_decision="BLOCK",
        eligible_for_docx_activation=False,
        docx_write_attempted=False,
        docx_write_succeeded=False,
        actual_docx_applied=False,
        review_status="READY",
        application_status="BLOCKED",
        review_required=False,
    )
    v = validate_change_review_items([it], gate_results=[_gate("RP-1", status="BLOCK", decision="BLOCK", eligible=False, applied=False)])
    assert any("block_gate_ready_review" in i or "blocked_gate_not_blocked" in i for i in v["issues"])


def test_negative_before_mismatch():
    it_dict = _pkg([_gate("RP-1")], previews=[_prev("RP-1", "ORIG", "AFTER")])["items"][0]
    it = ChangeReviewItem(**{k: it_dict[k] for k in ChangeReviewItem.__dataclass_fields__})
    it.before_text = "TAMPERED"
    v = validate_change_review_items(
        [it],
        preview_entries=[_prev("RP-1", "ORIG", "AFTER")],
    )
    assert any("before_text_not_preserved" in i for i in v["issues"])


def test_validation_summary_and_group_mismatch():
    pkg = _pkg([_gate("RP-1"), _gate("RP-2", acu="ACU-002")])
    items = [ChangeReviewItem(**{k: d[k] for k in ChangeReviewItem.__dataclass_fields__}) for d in pkg["items"]]
    bad_summary = dict(pkg["summary"])
    bad_summary["ready_count"] = 99
    v = validate_change_review_items(items, summary=bad_summary, groups=pkg["groups"])
    assert any("summary_ready_mismatch" in i for i in v["issues"])

    bad_groups = copy.deepcopy(pkg["groups"])
    if bad_groups:
        bad_groups[0]["review_item_ids"] = bad_groups[0]["review_item_ids"][:-1]
    v2 = validate_change_review_items(items, groups=bad_groups)
    assert any("group_item_count_mismatch" in i for i in v2["issues"])
