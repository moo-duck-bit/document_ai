# -*- coding: utf-8 -*-
"""PR-22: Template vs Writer capability gate."""

from __future__ import annotations

from typing import Any

from document_ai.impact.docx_activation_writer import is_docx_activation_enabled
from document_ai.template.schema import WRITER_SUPPORTED_OPERATIONS


def evaluate_capabilities(
    requested_operation: str,
    *,
    allowed_operations: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Separate template capability from writer/activation capability.

    PR-22 is observational-only: ``activation_allowed`` is always False,
    regardless of the external DOCX Feature Flag.
    """
    op = str(requested_operation or "").upper()
    allowed = list(allowed_operations or [])
    template_allowed = op in allowed
    writer_supported = op in WRITER_SUPPORTED_OPERATIONS
    external_activation_flag = bool(is_docx_activation_enabled(env=env or {}))
    # Observational gate: never allow activation in PR-22.
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
    reasons.append("ACTIVATION_DISABLED")
    reasons.append("OBSERVATIONAL_GATE_FORCED_OFF")
    reasons.append("ACTUAL_WRITER_NOT_CALLED")

    return {
        "template_allowed": template_allowed,
        "writer_supported": writer_supported,
        "external_activation_flag": external_activation_flag,
        "activation_enabled": external_activation_flag,  # backward-compatible alias
        "observational_gate_forced_off": observational_gate_forced_off,
        "activation_allowed": activation_allowed,
        "reason_codes": reasons,
    }
