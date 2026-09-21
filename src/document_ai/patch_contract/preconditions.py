# -*- coding: utf-8 -*-
"""PR-24: Patch precondition builder (observational)."""

from __future__ import annotations

from typing import Any

from document_ai.patch_contract.fingerprint import (
    compare_fingerprints,
    fingerprint_text,
    normalize_for_fingerprint,
)
from document_ai.patch_contract.schema import PatchContractInput, PatchPrecondition
from document_ai.semantic_locator.text_normalization import normalize_text


# Deterministic precondition type order
PRECONDITION_ORDER = (
    "DOCUMENT_EXISTS",
    "DOCUMENT_ID_MATCH",
    "TARGET_RESOLVED",
    "LOCATION_RESOLVED",
    "SOURCE_FINGERPRINT_MATCH",
    "BLOCK_EXISTS",
    "ORIGINAL_TEXT_MATCH",
    "OPERATION_ALLOWED",
    "WRITER_CAPABILITY_SUPPORTED",
    "HUMAN_APPROVAL_PRESENT",
    "OBSERVATIONAL_GATE_DISABLED",
)


def build_preconditions(
    inp: PatchContractInput,
    *,
    patch_contract_id: str,
    seq: int,
    caps: dict[str, Any],
) -> list[PatchPrecondition]:
    """Build ordered observational preconditions (no mutation)."""
    out: list[PatchPrecondition] = []
    idx = 0

    def _add(
        ptype: str,
        expected: Any,
        observed: Any,
        status: str,
        reasons: list[str],
        evidence: dict[str, Any] | None = None,
    ) -> None:
        nonlocal idx
        idx += 1
        out.append(
            PatchPrecondition(
                precondition_id=f"PPC-{seq:04d}-{idx:02d}",
                patch_contract_id=patch_contract_id,
                precondition_type=ptype,
                expected_value=expected,
                observed_value=observed,
                precondition_status=status,
                reason_codes=list(reasons),
                evidence=dict(evidence or {}),
            )
        )

    # DOCUMENT_EXISTS
    _add(
        "DOCUMENT_EXISTS",
        True,
        inp.document_exists,
        "SATISFIED" if inp.document_exists else "UNSATISFIED",
        ["DOCUMENT_EXISTS"] if inp.document_exists else ["DOCUMENT_MISSING"],
    )

    # DOCUMENT_ID_MATCH
    expected_doc = inp.expected_document_id or inp.document_id
    match = bool(inp.document_id) and inp.document_id == expected_doc
    _add(
        "DOCUMENT_ID_MATCH",
        expected_doc,
        inp.document_id,
        "SATISFIED" if match else "UNSATISFIED",
        ["DOCUMENT_ID_MATCH"] if match else ["DOCUMENT_ID_MISMATCH"],
    )

    # TARGET_RESOLVED
    target_ok = inp.target_status == "RESOLVED"
    _add(
        "TARGET_RESOLVED",
        "RESOLVED",
        inp.target_status,
        "SATISFIED"
        if target_ok
        else ("REVIEW" if inp.target_status == "REVIEW" else "UNSATISFIED"),
        ["TARGET_RESOLVED"] if target_ok else ["TARGET_NOT_RESOLVED"],
    )

    # LOCATION_RESOLVED
    loc_ok = inp.location_status == "RESOLVED"
    _add(
        "LOCATION_RESOLVED",
        "RESOLVED",
        inp.location_status,
        "SATISFIED"
        if loc_ok
        else ("REVIEW" if inp.location_status == "REVIEW" else "UNSATISFIED"),
        ["LOCATION_RESOLVED"] if loc_ok else ["LOCATION_NOT_RESOLVED"],
    )

    # SOURCE_FINGERPRINT_MATCH
    fp_status = inp.fingerprint_status or "AVAILABLE"
    if fp_status == "NOT_AVAILABLE":
        fp_pc_status, fp_reasons = "NOT_APPLICABLE", ["FINGERPRINT_NOT_AVAILABLE"]
        expected_fp = None
        observed_fp = None
    else:
        # Prefer explicit fingerprints; else derive from original_text when AVAILABLE
        expected_fp = inp.expected_original_text_fingerprint
        observed_fp = inp.observed_original_text_fingerprint
        if expected_fp is None and inp.original_text is not None and fp_status != "STALE":
            expected_fp = fingerprint_text(inp.original_text)["fingerprint"]
        if observed_fp is None and inp.original_text is not None and fp_status != "STALE":
            observed_fp = fingerprint_text(inp.original_text)["fingerprint"]
        if inp.expected_document_fingerprint and inp.observed_document_fingerprint:
            # Prefer document-level if both present
            expected_fp = inp.expected_document_fingerprint
            observed_fp = inp.observed_document_fingerprint
        fp_pc_status, fp_reasons = compare_fingerprints(
            expected_fp, observed_fp, fingerprint_status=fp_status
        )
    _add(
        "SOURCE_FINGERPRINT_MATCH",
        expected_fp,
        observed_fp,
        fp_pc_status,
        fp_reasons,
        {
            "fingerprint_status": fp_status,
            "algorithm": "SHA-256",
            "document_fingerprint": {
                "expected": inp.expected_document_fingerprint,
                "observed": inp.observed_document_fingerprint,
            },
            "block_fingerprint": {
                "expected": inp.expected_block_fingerprint,
                "observed": inp.observed_block_fingerprint,
            },
        },
    )

    # BLOCK_EXISTS
    block_ok = bool(inp.block_id) or bool(inp.section_id) or bool(inp.physical_candidate_id)
    _add(
        "BLOCK_EXISTS",
        True,
        block_ok,
        "SATISFIED" if block_ok else "UNSATISFIED",
        ["BLOCK_EXISTS"] if block_ok else ["BLOCK_MISSING"],
        {"block_id": inp.block_id, "section_id": inp.section_id},
    )

    # ORIGINAL_TEXT_MATCH (for UPDATE/REPLACE/DELETE)
    op = (inp.requested_operation or "").upper()
    if op in ("UPDATE", "REPLACE", "DELETE"):
        if inp.original_text is None:
            _add(
                "ORIGINAL_TEXT_MATCH",
                True,
                False,
                "UNSATISFIED",
                ["ORIGINAL_TEXT_MISSING"],
            )
        else:
            # Observational: observed equals expected when provided; else self-match
            expected_norm = normalize_for_fingerprint(inp.original_text)
            observed_raw = inp.metadata.get("observed_original_text", inp.original_text)
            observed_norm = normalize_for_fingerprint(observed_raw)
            ok = expected_norm == observed_norm
            _add(
                "ORIGINAL_TEXT_MATCH",
                expected_norm,
                observed_norm,
                "SATISFIED" if ok else "UNSATISFIED",
                ["ORIGINAL_TEXT_MATCH"] if ok else ["ORIGINAL_TEXT_MISMATCH"],
                {
                    "normalized_via": "fingerprint_normalize",
                    "semantic_normalize": normalize_text(inp.original_text),
                },
            )
    else:
        _add(
            "ORIGINAL_TEXT_MATCH",
            None,
            None,
            "NOT_APPLICABLE",
            ["ORIGINAL_TEXT_NOT_REQUIRED"],
        )

    # OPERATION_ALLOWED
    template_allowed = bool(caps.get("template_allowed"))
    _add(
        "OPERATION_ALLOWED",
        True,
        template_allowed,
        "SATISFIED" if template_allowed else "UNSATISFIED",
        ["OPERATION_ALLOWED"] if template_allowed else ["OPERATION_NOT_ALLOWED"],
    )

    # WRITER_CAPABILITY_SUPPORTED
    writer_supported = bool(caps.get("writer_supported"))
    _add(
        "WRITER_CAPABILITY_SUPPORTED",
        True,
        writer_supported,
        "SATISFIED" if writer_supported else "UNSATISFIED",
        (
            ["WRITER_CAPABILITY_SUPPORTED"]
            if writer_supported
            else ["WRITER_CAPABILITY_UNSUPPORTED"]
        ),
    )

    # HUMAN_APPROVAL_PRESENT
    if op == "DELETE":
        approved = bool(inp.human_approval_present)
        _add(
            "HUMAN_APPROVAL_PRESENT",
            True,
            approved,
            "SATISFIED" if approved else "UNSATISFIED",
            ["HUMAN_APPROVAL_PRESENT"] if approved else ["HUMAN_APPROVAL_MISSING"],
        )
    else:
        _add(
            "HUMAN_APPROVAL_PRESENT",
            None,
            inp.human_approval_present,
            "NOT_APPLICABLE",
            ["HUMAN_APPROVAL_NOT_REQUIRED"],
        )

    # OBSERVATIONAL_GATE_DISABLED — always UNSATISFIED for execution (gate forced off)
    # Meaning: the observational gate that disables activation is active.
    _add(
        "OBSERVATIONAL_GATE_DISABLED",
        False,  # we need gate disabled (=False means activation path closed) for exec
        True,  # gate is forced off (observational)
        "UNSATISFIED",  # blocks execution — correct for PR-24
        ["OBSERVATIONAL_GATE_FORCED_OFF", "ACTIVATION_NOT_ALLOWED"],
        {
            "observational_gate_forced_off": True,
            "activation_allowed": False,
            "external_activation_flag": caps.get("external_activation_flag", False),
        },
    )

    # Ensure deterministic type order
    order_index = {t: i for i, t in enumerate(PRECONDITION_ORDER)}
    out.sort(key=lambda p: (order_index.get(p.precondition_type, 99), p.precondition_id))
    return out
