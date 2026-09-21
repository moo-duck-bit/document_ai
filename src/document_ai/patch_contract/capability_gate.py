# -*- coding: utf-8 -*-
"""PR-24: Capability / observational activation gate."""

from __future__ import annotations

from typing import Any

from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.template.schema import WRITER_SUPPORTED_OPERATIONS


def evaluate_contract_capabilities(
    requested_operation: str,
    *,
    location_type: str | None = None,
    source_format: str = "markdown",
    allowed_operations: list[str] | None = None,
    env: dict[str, str] | None = None,
    external_activation_flag: bool | None = None,
) -> dict[str, Any]:
    """Template vs writer capability; activation always forced off in PR-24."""
    op = str(requested_operation or "").upper()
    allowed = list(allowed_operations or [])
    template_allowed = (not allowed) or (op in allowed)
    # Writer-supported ops from shared template schema (+ REPLACE alias)
    writer_ops = set(WRITER_SUPPORTED_OPERATIONS) | {"REPLACE"}
    writer_supported = op in writer_ops

    if external_activation_flag is None:
        external_activation_flag = bool(is_docx_activation_enabled(env=env or {}))
    else:
        external_activation_flag = bool(external_activation_flag)

    observational_gate_forced_off = True
    activation_allowed = False

    reasons: list[str] = []
    if template_allowed:
        reasons.append("OPERATION_TEMPLATE_ALLOWED")
    else:
        reasons.append("OPERATION_TEMPLATE_NOT_ALLOWED")
    if writer_supported:
        reasons.append("OPERATION_WRITER_SUPPORTED")
    else:
        reasons.append("OPERATION_WRITER_NOT_SUPPORTED")
    reasons.append("OBSERVATIONAL_GATE_FORCED_OFF")
    reasons.append("ACTIVATION_DISABLED")
    reasons.append("ACTUAL_WRITER_NOT_CALLED")

    return {
        "template_allowed": template_allowed,
        "writer_supported": writer_supported,
        "external_activation_flag": external_activation_flag,
        "observational_gate_forced_off": observational_gate_forced_off,
        "activation_allowed": activation_allowed,
        "location_type": location_type,
        "source_format": source_format,
        "reason_codes": reasons,
    }
