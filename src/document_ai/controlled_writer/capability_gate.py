# -*- coding: utf-8 -*-
"""PR-25: Controlled activation capability gate."""

from __future__ import annotations

import os
from typing import Any

from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.template.schema import WRITER_SUPPORTED_OPERATIONS


CONTROLLED_WRITER_ENV = "CONTROLLED_WRITER_ENABLED"


def is_controlled_writer_enabled(
    *,
    env: dict[str, str] | None = None,
    override: bool | None = None,
) -> bool:
    if override is not None:
        return bool(override)
    src = env if env is not None else os.environ
    raw = str(src.get(CONTROLLED_WRITER_ENV, "false")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def evaluate_controlled_activation(
    *,
    requested_operation: str,
    writer_adapter: str,
    span_kind: str,
    fingerprint_ok: bool,
    approval_ok: bool,
    contract_status: str,
    env: dict[str, str] | None = None,
    force_controlled: bool | None = None,
) -> dict[str, Any]:
    """Activation allowed only when ALL gates pass.

    Required:
      CONTROLLED_WRITER_ENABLED
      AND DOCX_ACTIVATION_ENABLED (external flag)
      AND approval
      AND fingerprint ok
      AND span_kind == SOURCE_ABSOLUTE
      AND contract READY_FOR_REVIEW
      AND adapter supported for operation
    """
    external_flag = bool(is_docx_activation_enabled(env=env or {}))
    controlled_flag = bool(
        is_controlled_writer_enabled(env=env or {}, override=force_controlled)
    )
    op = (requested_operation or "").upper()
    adapter = (writer_adapter or "").upper()

    reasons: list[str] = []
    if not controlled_flag:
        reasons.append("CONTROLLED_WRITER_DISABLED")
    if not external_flag:
        reasons.append("EXTERNAL_FEATURE_FLAG_OFF")
    if not approval_ok:
        reasons.append("APPROVAL_NOT_GRANTED")
    if not fingerprint_ok:
        reasons.append("FINGERPRINT_INVALID")
    if span_kind != "SOURCE_ABSOLUTE":
        reasons.append("SPAN_KIND_NOT_SOURCE_ABSOLUTE")

    ready_statuses = {"CONTRACT_READY_FOR_REVIEW"}
    if op == "DELETE":
        # Explicit APPROVED DELETE may proceed from REVIEW contracts
        ready_statuses.add("CONTRACT_REVIEW")
    contract_ready = contract_status in ready_statuses
    if not contract_ready:
        reasons.append("CONTRACT_NOT_READY_FOR_REVIEW")

    writer_ops = set(WRITER_SUPPORTED_OPERATIONS) | {"REPLACE", "ADD", "DELETE", "LINK"}
    op_supported = op in writer_ops
    if not op_supported:
        reasons.append("OPERATION_UNSUPPORTED")

    adapter_ok = adapter in {
        "DOCX_PARAGRAPH_WRITER",
        "DOCX_TABLE_CELL_WRITER",
        "MARKDOWN_BLOCK_WRITER",
    }
    if not adapter_ok or adapter == "UNSUPPORTED_WRITER":
        reasons.append("WRITER_ADAPTER_UNSUPPORTED")
        adapter_ok = False

    # ADD/DELETE/LINK allowed only via markdown adapter in PR-25 MVP
    if op in ("ADD", "DELETE", "LINK") and adapter != "MARKDOWN_BLOCK_WRITER":
        reasons.append("OPERATION_ADAPTER_MISMATCH")
        adapter_ok = False

    activation_allowed = (
        controlled_flag
        and external_flag
        and approval_ok
        and fingerprint_ok
        and (span_kind == "SOURCE_ABSOLUTE")
        and contract_ready
        and op_supported
        and adapter_ok
    )
    if activation_allowed:
        reasons = ["ACTIVATION_ALLOWED"]
    elif not reasons:
        reasons.append("ACTIVATION_BLOCKED")

    return {
        "external_activation_flag": external_flag,
        "controlled_writer_enabled": controlled_flag,
        "approval_ok": approval_ok,
        "fingerprint_ok": fingerprint_ok,
        "span_kind": span_kind,
        "contract_status": contract_status,
        "writer_adapter": adapter,
        "operation": op,
        "activation_allowed": activation_allowed,
        "reason_codes": reasons,
    }
