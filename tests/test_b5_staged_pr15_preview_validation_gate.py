# -*- coding: utf-8 -*-
"""PR-15: Preview Validation Gate tests."""

from __future__ import annotations

import copy

from document_ai.impact.preview_validation_gate import (
    PreviewGateResult,
    build_preview_gate_results,
    compare_gate_vs_activation,
    evaluate_preview_gate_item,
    run_preview_validation_gate,
    validate_preview_gate_results,
)


def _patch(
    pid: str,
    *,
    status: str = "VALID",
    acu: str = "ACU-001",
    rid: str = "Req.A",
    doc: str = "MDSR",
    field: str = "description",
    issues: list[str] | None = None,
) -> dict:
    return {
        "patch_id": pid,
        "draft_id": f"SD-{pid}",
        "atomic_change_id": acu,
        "requirement_id": rid,
        "document": doc,
        "field": field,
        "validation_status": status,
        "validation_issues": issues or [],
    }


def _lang(
    pid: str,
    *,
    status: str = "VALID",
    rejected: bool = False,
    semantic_changed: bool = False,
    meaning_preserved: bool = True,
    style: bool = True,
    grammar: bool = True,
    acu: str = "ACU-001",
) -> dict:
    return {
        "patch_id": pid,
        "draft_id": f"SD-{pid}",
        "atomic_change_id": acu,
        "requirement_id": "Req.A",
        "document": "MDSR",
        "field": "description",
        "validation_status": status,
        "rejected": rejected,
        "semantic_changed": semantic_changed,
        "meaning_preserved": meaning_preserved,
        "requirement_style": style,
        "grammar_normalized": grammar,
    }


def _dec(pid: str, decision: str, *, acu: str = "ACU-001") -> dict:
    return {
        "patch_id": pid,
        "decision": decision,
        "draft_id": f"SD-{pid}",
        "atomic_change_id": acu,
        "requirement_id": "Req.A",
    }


def _prev(
    pid: str,
    *,
    decision: str = "AUTO_APPLY",
    applied: bool = True,
    reasons: list[str] | None = None,
    acu: str = "ACU-001",
    rid: str = "Req.A",
) -> dict:
    return {
        "patch_id": pid,
        "draft_id": f"SD-{pid}",
        "atomic_change_id": acu,
        "requirement_id": rid,
        "document": "MDSR",
        "field": "description",
        "activation_decision": decision,
        "applied_in_preview": applied,
        "reasons": reasons or [],
    }


def _ok_bundle(pid: str, *, acu: str = "ACU-001") -> tuple[dict, dict, dict, dict]:
    return (
        _patch(pid, acu=acu),
        _lang(pid, acu=acu),
        _dec(pid, "AUTO_APPLY", acu=acu),
        _prev(pid, decision="AUTO_APPLY", applied=True, acu=acu),
    )


def _run(
    patches,
    languages,
    decisions,
    previews,
    *,
    aggregated=None,
    preview_validation=None,
    **kwargs,
):
    return run_preview_validation_gate(
        patches=patches,
        languages=languages,
        decisions=decisions,
        preview_entries=previews,
        aggregated=aggregated or [],
        preview_validation=preview_validation or {"status": "VALID"},
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Core decision tests
# ---------------------------------------------------------------------------


def test_1_all_valid_auto_apply_pass():
    p, l, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "PASS"
    assert r.eligible_for_docx_activation is True
    assert r.reason_codes == ["PASS_ALL_VALID"]


def test_2_activation_block():
    p, l, _, _ = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=_dec("RP-1", "BLOCK"),
        preview_entry=_prev("RP-1", decision="BLOCK", applied=False),
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "ACTIVATION_BLOCK" in r.reason_codes
    assert r.eligible_for_docx_activation is False


def test_3_activation_review():
    p, l, _, _ = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=_dec("RP-1", "REVIEW"),
        preview_entry=_prev("RP-1", decision="REVIEW", applied=False),
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "REVIEW"
    assert "ACTIVATION_REVIEW" in r.reason_codes


def test_4_language_review_required():
    p, _, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=_lang("RP-1", status="REVIEW_REQUIRED"),
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "REVIEW"
    assert "LANGUAGE_REVIEW_REQUIRED" in r.reason_codes


def test_5_language_rejected():
    p, _, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=_lang("RP-1", rejected=True),
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "REVIEW"
    assert "LANGUAGE_REJECTED" in r.reason_codes


def test_6_semantic_changed_block():
    p, _, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=_lang("RP-1", semantic_changed=True),
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "SEMANTIC_CHANGED" in r.reason_codes


def test_7_meaning_not_preserved_block():
    p, _, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=_lang("RP-1", meaning_preserved=False),
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "MEANING_NOT_PRESERVED" in r.reason_codes


def test_8_patch_invalid_block():
    _, l, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=_patch("RP-1", status="INVALID"),
        language=l,
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "PATCH_INVALID" in r.reason_codes


def test_9_preview_invalid_block():
    p, l, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=d,
        preview_entry=v,
        preview_validation={"status": "INVALID"},
    )
    assert r.final_status == "BLOCK"
    assert "PREVIEW_INVALID" in r.reason_codes


def test_10_auto_apply_not_applied_block():
    p, l, d, _ = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=d,
        preview_entry=_prev("RP-1", decision="AUTO_APPLY", applied=False),
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "PREVIEW_NOT_APPLIED" in r.reason_codes


def test_11_block_applied_in_preview():
    p, l, _, _ = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=_dec("RP-1", "BLOCK"),
        preview_entry=_prev("RP-1", decision="BLOCK", applied=True),
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "BLOCK_WAS_APPLIED" in r.reason_codes or "NON_AUTO_APPLY_WAS_APPLIED" in r.reason_codes


def test_12_missing_decision_applied_block():
    p, l, _, _ = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision={},
        preview_entry=_prev(
            "RP-1",
            decision="REVIEW",
            applied=True,
            reasons=["missing_activation_decision"],
        ),
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "MISSING_DECISION_APPLIED" in r.reason_codes


def test_13_conflict_preserved_review():
    p, l, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=d,
        preview_entry=v,
        aggregated_for_target={
            "conflict_detected": True,
            "original_requirement": "원문",
            "final_preview_requirement": "원문",
            "requirement_id": "Req.A",
            "document": "MDSR",
            "field": "description",
        },
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "REVIEW"
    assert "PREVIEW_CONFLICT" in r.reason_codes


def test_14_conflict_not_preserved_block():
    p, l, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=d,
        preview_entry=v,
        aggregated_for_target={
            "conflict_detected": True,
            "original_requirement": "원문",
            "final_preview_requirement": "오염된 텍스트",
        },
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "CONFLICT_DID_NOT_PRESERVE_ORIGINAL" in r.reason_codes


def test_15_unknown_state_block():
    p, l, _, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=_dec("RP-1", "UNKNOWN"),
        preview_entry=_prev("RP-1", decision="UNKNOWN", applied=False),
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "UNKNOWN_STATE" in r.reason_codes


def test_16_artifact_missing_block():
    r = evaluate_preview_gate_item(
        patch={},
        language=_lang("RP-X"),
        decision=_dec("RP-X", "AUTO_APPLY"),
        preview_entry={},
        preview_validation={"status": "VALID"},
        artifact_missing=True,
    )
    assert r.final_status == "BLOCK"
    assert "MISSING_ARTIFACT" in r.reason_codes


def test_17_18_19_eligible_only_for_pass():
    p, l, d, v = _ok_bundle("RP-P")
    pass_r = evaluate_preview_gate_item(
        patch=p, language=l, decision=d, preview_entry=v, preview_validation={"status": "VALID"}
    )
    review_r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=_dec("RP-P", "REVIEW"),
        preview_entry=_prev("RP-P", decision="REVIEW", applied=False),
        preview_validation={"status": "VALID"},
    )
    block_r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=_dec("RP-P", "BLOCK"),
        preview_entry=_prev("RP-P", decision="BLOCK", applied=False),
        preview_validation={"status": "VALID"},
    )
    assert pass_r.eligible_for_docx_activation is True
    assert review_r.eligible_for_docx_activation is False
    assert block_r.eligible_for_docx_activation is False


def test_20_precedence_block_over_review_over_pass():
    # AUTO_APPLY + language REVIEW + semantic_changed → BLOCK wins
    p, _, d, v = _ok_bundle("RP-1")
    r = evaluate_preview_gate_item(
        patch=p,
        language=_lang("RP-1", status="REVIEW_REQUIRED", semantic_changed=True),
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "SEMANTIC_CHANGED" in r.reason_codes
    assert "LANGUAGE_REVIEW_REQUIRED" in r.reason_codes


def test_21_global_status_aggregation():
    patches, langs, decs, prevs = [], [], [], []
    for i in range(3):
        p, l, d, v = _ok_bundle(f"RP-{i}", acu=f"ACU-{i:03d}")
        patches.append(p)
        langs.append(l)
        decs.append(d)
        prevs.append(v)
    # one block
    patches.append(_patch("RP-B", status="INVALID", acu="ACU-999"))
    langs.append(_lang("RP-B", acu="ACU-999"))
    decs.append(_dec("RP-B", "BLOCK", acu="ACU-999"))
    prevs.append(_prev("RP-B", decision="BLOCK", applied=False, acu="ACU-999"))

    payload = _run(patches, langs, decs, prevs)
    assert payload["global_status"] == "BLOCK"
    assert payload["summary"]["pass_count"] == 3
    assert payload["summary"]["block_count"] == 1


def test_22_deterministic_output():
    patches, langs, decs, prevs = [], [], [], []
    for i, acu in enumerate(["ACU-002", "ACU-001", "ACU-003"]):
        p, l, d, v = _ok_bundle(f"RP-{i}", acu=acu)
        patches.append(p)
        langs.append(l)
        decs.append(d)
        prevs.append(v)
    a = _run(patches, langs, decs, prevs)
    b = _run(patches, langs, decs, prevs)
    ids_a = [r.patch_id for r in a["results"]]
    ids_b = [r.patch_id for r in b["results"]]
    assert ids_a == ids_b
    assert [r.to_dict() for r in a["results"]] == [r.to_dict() for r in b["results"]]
    # sort by atomic_change_id then patch_id
    assert [r.atomic_change_id for r in a["results"]] == sorted(
        r.atomic_change_id for r in a["results"]
    )


def test_23_input_artifacts_not_mutated():
    patches = [_patch("RP-1")]
    langs = [_lang("RP-1")]
    decs = [_dec("RP-1", "AUTO_APPLY")]
    prevs = [_prev("RP-1")]
    snap = (
        copy.deepcopy(patches),
        copy.deepcopy(langs),
        copy.deepcopy(decs),
        copy.deepcopy(prevs),
    )
    _run(patches, langs, decs, prevs)
    assert patches == snap[0]
    assert langs == snap[1]
    assert decs == snap[2]
    assert prevs == snap[3]


def test_24_scenario_like_eleven_pass_one_block():
    """Current scenario shape: derive counts from activation decisions (not hardcoded gate)."""
    patches, langs, decs, prevs = [], [], [], []
    auto_ids = [f"RP-{i:02d}" for i in range(1, 12)]
    for i, pid in enumerate(auto_ids):
        acu = f"ACU-{i+1:03d}"
        p, l, d, v = _ok_bundle(pid, acu=acu)
        patches.append(p)
        langs.append(l)
        decs.append(d)
        prevs.append(v)
    # Separate BLOCK target (e.g. ACU-style block) — do not reuse AUTO_APPLY acu ids
    block_pid = "RP-BLOCK"
    block_acu = "ACU-BLOCK"
    patches.append(_patch(block_pid, status="INVALID", acu=block_acu))
    langs.append(_lang(block_pid, acu=block_acu))
    decs.append(_dec(block_pid, "BLOCK", acu=block_acu))
    prevs.append(_prev(block_pid, decision="BLOCK", applied=False, acu=block_acu))

    payload = _run(patches, langs, decs, prevs)
    auto_count = sum(1 for d in decs if d["decision"] == "AUTO_APPLY")
    block_count = sum(1 for d in decs if d["decision"] == "BLOCK")
    assert payload["summary"]["pass_count"] == auto_count
    assert payload["summary"]["block_count"] == block_count
    assert payload["summary"]["review_count"] == 0
    assert payload["summary"]["eligible_count"] == auto_count
    assert payload["global_status"] == "BLOCK"  # because one BLOCK exists
    blocked = [r for r in payload["results"] if r.patch_id == block_pid]
    assert blocked and blocked[0].final_status == "BLOCK"
    assert blocked[0].atomic_change_id == block_acu


def test_25_26_docx_legacy_flags():
    p, l, d, v = _ok_bundle("RP-1")
    payload = _run([p], [l], [d], [v])
    assert payload["summary"]["actual_docx_changed"] is False
    assert payload["summary"]["actual_generation_changed"] is False
    assert payload["summary"]["docx_change_count"] == 0
    assert payload["summary"]["legacy_change_count"] == 0
    assert all(not r.actual_docx_changed for r in payload["results"])


# ---------------------------------------------------------------------------
# Negative validation tests
# ---------------------------------------------------------------------------


def test_negative_unknown_activation_detected():
    bad = PreviewGateResult(
        gate_result_id="PG-X",
        patch_id="RP-X",
        draft_id="",
        atomic_change_id="",
        requirement_id=None,
        document="",
        field="",
        patch_validation_status="VALID",
        language_validation_status="VALID",
        activation_decision="UNKNOWN",
        preview_applied=False,
        preview_validation_status="VALID",
        final_status="BLOCK",
        reason_codes=["UNKNOWN_STATE"],
        reason_messages=["Unknown"],
        eligible_for_docx_activation=False,
    )
    v = validate_preview_gate_results([bad])
    assert any("unknown_activation" in i for i in v["issues"])


def test_negative_block_applied_detected():
    bad = PreviewGateResult(
        gate_result_id="PG-X",
        patch_id="RP-X",
        draft_id="",
        atomic_change_id="",
        requirement_id=None,
        document="",
        field="",
        patch_validation_status="VALID",
        language_validation_status="VALID",
        activation_decision="BLOCK",
        preview_applied=True,
        preview_validation_status="VALID",
        final_status="BLOCK",
        reason_codes=["BLOCK_WAS_APPLIED"],
        reason_messages=[],
        eligible_for_docx_activation=False,
    )
    v = validate_preview_gate_results([bad])
    assert any("block_applied" in i for i in v["issues"])


def test_negative_review_eligible_detected():
    bad = PreviewGateResult(
        gate_result_id="PG-X",
        patch_id="RP-X",
        draft_id="",
        atomic_change_id="",
        requirement_id=None,
        document="",
        field="",
        patch_validation_status="VALID",
        language_validation_status="VALID",
        activation_decision="REVIEW",
        preview_applied=False,
        preview_validation_status="VALID",
        final_status="REVIEW",
        reason_codes=["ACTIVATION_REVIEW"],
        reason_messages=[],
        eligible_for_docx_activation=True,  # illegal
    )
    v = validate_preview_gate_results([bad])
    assert any("non_pass_eligible" in i for i in v["issues"])


def test_negative_semantic_pass_detected():
    bad = PreviewGateResult(
        gate_result_id="PG-X",
        patch_id="RP-X",
        draft_id="",
        atomic_change_id="",
        requirement_id=None,
        document="",
        field="",
        patch_validation_status="VALID",
        language_validation_status="VALID",
        activation_decision="AUTO_APPLY",
        preview_applied=True,
        preview_validation_status="VALID",
        final_status="PASS",
        reason_codes=["PASS_ALL_VALID", "SEMANTIC_CHANGED"],
        reason_messages=[],
        eligible_for_docx_activation=True,
    )
    v = validate_preview_gate_results([bad])
    assert any("semantic_changed" in i or "precedence" in i for i in v["issues"])


def test_negative_meaning_pass_detected():
    bad = PreviewGateResult(
        gate_result_id="PG-X",
        patch_id="RP-X",
        draft_id="",
        atomic_change_id="",
        requirement_id=None,
        document="",
        field="",
        patch_validation_status="VALID",
        language_validation_status="VALID",
        activation_decision="AUTO_APPLY",
        preview_applied=True,
        preview_validation_status="VALID",
        final_status="PASS",
        reason_codes=["MEANING_NOT_PRESERVED"],
        reason_messages=[],
        eligible_for_docx_activation=True,
    )
    v = validate_preview_gate_results([bad])
    assert any("meaning_lost" in i or "precedence" in i for i in v["issues"])


def test_negative_docx_changed_detected():
    bad = PreviewGateResult(
        gate_result_id="PG-X",
        patch_id="RP-X",
        draft_id="",
        atomic_change_id="",
        requirement_id=None,
        document="",
        field="",
        patch_validation_status="VALID",
        language_validation_status="VALID",
        activation_decision="AUTO_APPLY",
        preview_applied=True,
        preview_validation_status="VALID",
        final_status="BLOCK",
        reason_codes=["ACTUAL_DOCX_CHANGED"],
        reason_messages=[],
        eligible_for_docx_activation=False,
        actual_docx_changed=True,
    )
    v = validate_preview_gate_results([bad])
    assert any("docx_changed" in i for i in v["issues"])


def test_negative_trace_id_mismatch_blocks():
    p = _patch("RP-1", acu="ACU-001")
    l = _lang("RP-1", acu="ACU-999")  # mismatch
    d = _dec("RP-1", "AUTO_APPLY", acu="ACU-001")
    v = _prev("RP-1", acu="ACU-001")
    r = evaluate_preview_gate_item(
        patch=p,
        language=l,
        decision=d,
        preview_entry=v,
        preview_validation={"status": "VALID"},
    )
    assert r.final_status == "BLOCK"
    assert "TRACE_ID_MISMATCH" in r.reason_codes


def test_gate_vs_activation_shape():
    p, l, d, v = _ok_bundle("RP-1")
    payload = _run([p], [l], [d], [v])
    vs = compare_gate_vs_activation(payload["results"])
    assert vs["pair_count"] == 1
    row = vs["pairs"][0]
    assert row["activation_decision"] == "AUTO_APPLY"
    assert row["preview_applied"] is True
    assert row["gate_final_status"] == "PASS"
    assert row["eligible_for_docx_activation"] is True


def test_build_results_sorted():
    items = []
    for pid, acu in [("RP-B", "ACU-002"), ("RP-A", "ACU-001")]:
        items.append(_ok_bundle(pid, acu=acu))
    patches = [x[0] for x in items]
    langs = [x[1] for x in items]
    decs = [x[2] for x in items]
    prevs = [x[3] for x in items]
    results = build_preview_gate_results(
        patches=patches,
        languages=langs,
        decisions=decs,
        preview_entries=prevs,
        preview_validation={"status": "VALID"},
    )
    assert [r.patch_id for r in results] == ["RP-A", "RP-B"]
