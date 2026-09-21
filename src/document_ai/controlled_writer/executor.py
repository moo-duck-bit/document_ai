# -*- coding: utf-8 -*-
"""PR-25: Patch executor (copy-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.controlled_writer.adapters import dispatch_adapter
from document_ai.controlled_writer.approval import evaluate_approval
from document_ai.controlled_writer.capability_gate import evaluate_controlled_activation
from document_ai.controlled_writer.copy_workspace import (
    ensure_copy,
    file_sha256,
    verify_original_unchanged,
)
from document_ai.controlled_writer.diff_engine import build_diff
from document_ai.controlled_writer.rollback import create_rollback_point, rollback_to_point
from document_ai.controlled_writer.schema import (
    ControlledWriterInput,
    DiffResult,
    RollbackPoint,
    WriterPlan,
    WriterResult,
)
from document_ai.patch_contract.fingerprint import fingerprint_text


def _fingerprint_ok(inp: ControlledWriterInput, source_path: Path) -> bool:
    if not source_path.exists():
        return False
    if inp.expected_fingerprint:
        # For markdown: content fingerprint; for binary: file hash
        if inp.source_format in ("markdown", "md", "text"):
            content = source_path.read_text(encoding="utf-8")
            fp = fingerprint_text(content)["fingerprint"]
            return fp == inp.expected_fingerprint
        return file_sha256(source_path) == inp.expected_fingerprint
    # If no expected fingerprint provided, treat as invalid (fail closed)
    return False


def build_writer_plan(
    inp: ControlledWriterInput,
    *,
    seq: int,
    copy_path: str,
    activation: dict[str, Any],
) -> WriterPlan:
    return WriterPlan(
        writer_plan_id=f"WP-{seq:04d}",
        patch_contract_id=inp.patch_contract_id,
        writer_adapter=inp.writer_adapter,
        operation=(inp.requested_operation or "").upper(),
        source_path=inp.source_path,
        copy_path=copy_path,
        intended_location={
            "document_id": inp.document_id,
            "location_type": inp.location_type,
            "section_id": inp.section_id,
            "block_id": inp.block_id,
            "paragraph_index": inp.paragraph_index,
            "list_index": inp.list_index,
            "table_index": inp.table_index,
            "cell_coordinate": list(inp.cell_coordinate)
            if inp.cell_coordinate is not None
            else None,
            "character_span": list(inp.character_span)
            if inp.character_span is not None
            else None,
            "span_kind": inp.span_kind,
        },
        intended_payload={
            "original_text": inp.original_text,
            "proposed_text": inp.proposed_text,
            "link_metadata": inp.link_metadata,
        },
        activation_allowed=bool(activation.get("activation_allowed")),
        blocking_reasons=[
            r
            for r in (activation.get("reason_codes") or [])
            if r != "ACTIVATION_ALLOWED"
        ],
        evidence={"activation": activation},
    )


def execute_controlled_write(
    inp: ControlledWriterInput,
    *,
    seq: int,
    work_dir: Path,
    env: dict[str, str] | None = None,
    force_fail: bool = False,
) -> tuple[WriterPlan, WriterResult, DiffResult | None, RollbackPoint | None, dict[str, Any]]:
    """Full controlled write pipeline for one input."""
    env = env or {}
    work_dir = Path(work_dir)
    copies_dir = work_dir / "copies"
    snaps_dir = work_dir / "snapshots"
    copies_dir.mkdir(parents=True, exist_ok=True)
    snaps_dir.mkdir(parents=True, exist_ok=True)

    approval = evaluate_approval(inp)
    src = Path(inp.source_path)
    fp_ok = _fingerprint_ok(inp, src)

    # Always create copy first for observability (even if blocked),
    # except when source missing.
    copy_info = ensure_copy(src, copies_dir, stem_suffix=f"_copy_{seq:04d}")
    source_fp = copy_info.get("source_fingerprint")
    copy_path = copy_info.get("copy_path") or ""

    activation = evaluate_controlled_activation(
        requested_operation=inp.requested_operation,
        writer_adapter=inp.writer_adapter,
        span_kind=inp.span_kind,
        fingerprint_ok=fp_ok,
        approval_ok=bool(approval.get("approved")),
        contract_status=inp.contract_status,
        env=env,
    )

    plan = build_writer_plan(
        inp, seq=seq, copy_path=copy_path, activation=activation
    )

    # Early exits
    if not copy_info.get("ok"):
        result = WriterResult(
            writer_result_id=f"WR-{seq:04d}",
            patch_contract_id=inp.patch_contract_id,
            writer_plan_id=plan.writer_plan_id,
            result_status="FAILED",
            source_path=inp.source_path,
            copy_path=copy_path,
            original_unchanged=True,
            copy_modified=False,
            operation=(inp.requested_operation or "").upper(),
            reason_codes=list(copy_info.get("reason_codes") or ["COPY_FAILED"]),
            actual_writer_called=False,
            actual_document_changed=False,
            actual_original_changed=False,
        )
        return plan, result, None, None, {"approval": approval, "activation": activation}

    if not approval.get("approved"):
        status = "REJECTED" if "APPROVAL_REJECTED" in (approval.get("reason_codes") or []) else "BLOCKED"
        result = WriterResult(
            writer_result_id=f"WR-{seq:04d}",
            patch_contract_id=inp.patch_contract_id,
            writer_plan_id=plan.writer_plan_id,
            result_status=status,
            source_path=str(src),
            copy_path=copy_path,
            original_unchanged=verify_original_unchanged(src, source_fp or ""),
            copy_modified=False,
            operation=(inp.requested_operation or "").upper(),
            reason_codes=list(approval.get("reason_codes") or []),
            actual_writer_called=False,
            actual_document_changed=False,
            actual_original_changed=False,
            evidence={"approval": approval},
        )
        return plan, result, None, None, {"approval": approval, "activation": activation}

    if not activation.get("activation_allowed"):
        result = WriterResult(
            writer_result_id=f"WR-{seq:04d}",
            patch_contract_id=inp.patch_contract_id,
            writer_plan_id=plan.writer_plan_id,
            result_status="BLOCKED",
            source_path=str(src),
            copy_path=copy_path,
            original_unchanged=verify_original_unchanged(src, source_fp or ""),
            copy_modified=False,
            operation=(inp.requested_operation or "").upper(),
            reason_codes=list(activation.get("reason_codes") or []),
            actual_writer_called=False,
            actual_document_changed=False,
            actual_original_changed=False,
            evidence={"activation": activation},
        )
        return plan, result, None, None, {"approval": approval, "activation": activation}

    # Pre-write rollback snapshot
    rb = create_rollback_point(
        rollback_id=f"RB-{seq:04d}",
        patch_contract_id=inp.patch_contract_id,
        copy_path=copy_path,
        snapshot_dir=snaps_dir,
    )

    if force_fail:
        # Simulate failure → rollback
        rollback_to_point(rb)
        result = WriterResult(
            writer_result_id=f"WR-{seq:04d}",
            patch_contract_id=inp.patch_contract_id,
            writer_plan_id=plan.writer_plan_id,
            result_status="ROLLED_BACK",
            source_path=str(src),
            copy_path=copy_path,
            original_unchanged=verify_original_unchanged(src, source_fp or ""),
            copy_modified=False,
            operation=(inp.requested_operation or "").upper(),
            reason_codes=["FORCED_FAILURE", "ROLLED_BACK"],
            rollback_id=rb.rollback_id,
            actual_writer_called=False,
            actual_document_changed=False,
            actual_original_changed=False,
            evidence={"rollback": rb.to_dict()},
        )
        return plan, result, None, rb, {"approval": approval, "activation": activation}

    write = dispatch_adapter(
        inp.writer_adapter,
        Path(copy_path),
        operation=inp.requested_operation,
        original_text=inp.original_text,
        proposed_text=inp.proposed_text,
        character_span=inp.character_span,
        paragraph_index=inp.paragraph_index,
        table_index=inp.table_index,
        cell_coordinate=inp.cell_coordinate,
        link_metadata=inp.link_metadata,
    )

    if not write.get("ok"):
        rollback_to_point(rb)
        result = WriterResult(
            writer_result_id=f"WR-{seq:04d}",
            patch_contract_id=inp.patch_contract_id,
            writer_plan_id=plan.writer_plan_id,
            result_status="ROLLED_BACK",
            source_path=str(src),
            copy_path=copy_path,
            original_unchanged=verify_original_unchanged(src, source_fp or ""),
            copy_modified=False,
            operation=(inp.requested_operation or "").upper(),
            reason_codes=list(write.get("reason_codes") or []) + ["ROLLED_BACK"],
            rollback_id=rb.rollback_id,
            actual_writer_called=True,
            actual_document_changed=False,
            actual_original_changed=False,
            evidence={"write": write, "rollback": rb.to_dict()},
        )
        return plan, result, None, rb, {"approval": approval, "activation": activation}

    diff = build_diff(
        diff_id=f"DIFF-{seq:04d}",
        patch_contract_id=inp.patch_contract_id,
        before_text=str(write.get("before") or ""),
        after_text=str(write.get("after") or ""),
        operation=(inp.requested_operation or "").upper(),
    )

    original_ok = verify_original_unchanged(src, source_fp or "")
    result = WriterResult(
        writer_result_id=f"WR-{seq:04d}",
        patch_contract_id=inp.patch_contract_id,
        writer_plan_id=plan.writer_plan_id,
        result_status="APPLIED",
        source_path=str(src),
        copy_path=copy_path,
        original_unchanged=original_ok,
        copy_modified=bool(write.get("changed")),
        operation=(inp.requested_operation or "").upper(),
        reason_codes=list(write.get("reason_codes") or []),
        diff_id=diff.diff_id,
        rollback_id=rb.rollback_id,
        actual_writer_called=True,
        actual_document_changed=bool(write.get("changed")),  # copy changed
        actual_original_changed=not original_ok,
        evidence={
            "write": {
                "reason_codes": write.get("reason_codes"),
                "changed": write.get("changed"),
            },
            "source_fingerprint": source_fp,
            "copy_fingerprint_after": file_sha256(Path(copy_path)),
        },
    )
    return plan, result, diff, rb, {"approval": approval, "activation": activation}
