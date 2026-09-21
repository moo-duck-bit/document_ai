# -*- coding: utf-8 -*-
"""PR-22: Patch targeting orchestrator (observational)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.patch_targeting.intent_builder import build_patch_intent
from document_ai.patch_targeting.preview import build_activation_preview
from document_ai.patch_targeting.schema import (
    ActivationPreview,
    PatchIntent,
    PatchTargetCandidate,
    PatchTargetingInput,
)
from document_ai.patch_targeting.target_resolver import resolve_patch_target
from document_ai.patch_targeting.validation import validate_patch_targeting
from document_ai.semantic_locator.locator import load_generic_node_candidates
from document_ai.semantic_locator.schema import TemplateNodeCandidate


def sample_patch_targeting_inputs() -> list[PatchTargetingInput]:
    """Deterministic samples covering required PR-22 scenarios."""
    return [
        # 1. MATCHED + UPDATE + writer supported
        PatchTargetingInput(
            change_id="CHG-001",
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-001",
            semantic_match_id="SM-0001-001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            requested_operation="UPDATE",
            change_type="UPDATE",
            source_text="내부 artifact 및 샘플 fixture",
            proposed_text="내부 artifact, 샘플 fixture 및 공개 데이터셋",
            match_status="MATCHED",
            combined_score=0.87,
            score_margin=0.79,
            ambiguity_status="CLEAR",
            match_reason_codes=["HEADING_PATH_MATCH", "FIELD_LABEL_MATCH"],
            match_evidence={
                "rule_components": {"heading_path_exact": 1.0, "field_label": 1.0}
            },
            metadata={"case": "matched_update"},
        ),
        # 2. MATCHED + ADD + writer unsupported
        PatchTargetingInput(
            change_id="CHG-002",
            document_id="sample_md_business_proposal_001",
            locator_candidate_id="LC-SAMPLE-002",
            semantic_match_id="SM-0002-001",
            template_id="business_proposal_v1",
            template_node_id="business_proposal_v1.execution_plan.schedule",
            requested_operation="ADD",
            change_type="ADD",
            source_text="1~4주 단계 수행",
            proposed_text="검수 단계 추가",
            match_status="MATCHED",
            combined_score=0.85,
            score_margin=0.60,
            ambiguity_status="CLEAR",
            match_reason_codes=["HEADING_PATH_MATCH"],
            match_evidence={
                "matched_heading_path": ["수행 계획", "일정"],
                "rule_components": {"heading_path_exact": 1.0},
            },
            metadata={"case": "matched_add", "parent_section_id": "execution_plan"},
        ),
        # 3. REVIEW semantic match
        PatchTargetingInput(
            change_id="CHG-003",
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-003",
            semantic_match_id="SM-0003-001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.results.body",
            requested_operation="UPDATE",
            change_type="UPDATE",
            source_text="결과",
            proposed_text="결과 본문 보강",
            match_status="REVIEW",
            combined_score=0.69,
            score_margin=0.001,
            ambiguity_status="AMBIGUOUS",
            match_reason_codes=["AMBIGUOUS_TOP_MATCH"],
            match_evidence={"rule_components": {"heading_text": 1.0}},
            metadata={"case": "semantic_review"},
        ),
        # 4. UNMAPPED
        PatchTargetingInput(
            change_id="CHG-004",
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-005",
            semantic_match_id="SM-0005-001",
            template_id="general_report_v1",
            template_node_id=None,
            requested_operation="UPDATE",
            change_type="UPDATE",
            source_text="",
            proposed_text="x",
            match_status="UNMAPPED",
            combined_score=0.0,
            score_margin=0.0,
            ambiguity_status="CLEAR",
            match_reason_codes=["LOW_SCORE"],
            metadata={"case": "unmapped"},
        ),
        # 5. INVALID semantic
        PatchTargetingInput(
            change_id="CHG-005",
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-BAD",
            semantic_match_id="SM-INVALID-001",
            template_id="not_a_template",
            template_node_id=None,
            requested_operation="UPDATE",
            change_type="UPDATE",
            proposed_text="y",
            match_status="INVALID",
            combined_score=0.0,
            ambiguity_status="CLEAR",
            match_reason_codes=["TEMPLATE_NOT_FOUND"],
            metadata={"case": "semantic_invalid"},
        ),
        # 6. Ambiguous DELETE
        PatchTargetingInput(
            change_id="CHG-006",
            document_id="sample_md_business_proposal_001",
            locator_candidate_id="LC-SAMPLE-004",
            semantic_match_id="SM-0004-001",
            template_id="business_proposal_v1",
            template_node_id="business_proposal_v1.schedule.body",
            requested_operation="DELETE",
            change_type="DELETE",
            source_text="일정 본문",
            proposed_text=None,
            match_status="MATCHED",
            combined_score=0.69,
            score_margin=0.001,
            ambiguity_status="AMBIGUOUS",
            match_reason_codes=["AMBIGUOUS_TOP_MATCH"],
            match_evidence={"rule_components": {"heading_text": 1.0}},
            metadata={"case": "ambiguous_delete"},
        ),
        # 7. Missing proposed_text UPDATE
        PatchTargetingInput(
            change_id="CHG-007",
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-001",
            semantic_match_id="SM-0001-001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            requested_operation="UPDATE",
            change_type="UPDATE",
            source_text="기존",
            proposed_text="",
            match_status="MATCHED",
            combined_score=0.87,
            score_margin=0.79,
            ambiguity_status="CLEAR",
            match_reason_codes=["HEADING_PATH_MATCH"],
            match_evidence={
                "rule_components": {"heading_path_exact": 1.0}
            },
            metadata={"case": "missing_proposed"},
        ),
        # 8. Template allowed Writer unsupported (LINK)
        PatchTargetingInput(
            change_id="CHG-008",
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-001",
            semantic_match_id="SM-0001-001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.references.entries",
            requested_operation="LINK",
            change_type="LINK",
            source_text="ref",
            proposed_text="link",
            match_status="MATCHED",
            combined_score=0.82,
            score_margin=0.20,
            ambiguity_status="CLEAR",
            match_reason_codes=["HEADING_PATH_MATCH"],
            match_evidence={
                "rule_components": {"heading_path_exact": 1.0}
            },
            metadata={
                "case": "link_writer_unsupported",
                "link_source": "A",
                "link_target": "B",
            },
        ),
        # 9. Generic requirement_id=None (normal MATCHED UPDATE)
        PatchTargetingInput(
            change_id="CHG-009",
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-001",
            semantic_match_id="SM-0001-001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.approach",
            requested_operation="UPDATE",
            change_type="UPDATE",
            source_text="정적 Template 기반 매핑",
            proposed_text="정적 Template + Semantic Locator 기반 매핑",
            match_status="MATCHED",
            combined_score=0.84,
            score_margin=0.50,
            ambiguity_status="CLEAR",
            match_reason_codes=["HEADING_PATH_MATCH", "GENERIC_REQUIREMENT_ID_OPTIONAL"],
            match_evidence={
                "rule_components": {"heading_path_exact": 1.0}
            },
            metadata={"case": "generic_req_null", "source_requirement_id": None},
        ),
    ]


def _lookup_node(
    nodes: list[TemplateNodeCandidate],
    template_node_id: str | None,
) -> TemplateNodeCandidate | None:
    if not template_node_id:
        return None
    for n in nodes:
        if n.template_node_id == template_node_id:
            return n
    return None


def process_one(
    inp: PatchTargetingInput,
    *,
    seq: int,
    nodes: list[TemplateNodeCandidate],
) -> tuple[PatchIntent, PatchTargetCandidate, ActivationPreview]:
    node = _lookup_node(nodes, inp.template_node_id)
    intent = build_patch_intent(inp, seq=seq, node=node)
    target = resolve_patch_target(
        intent,
        seq=seq,
        node=node,
        match_status=inp.match_status,
        combined_score=inp.combined_score,
        score_margin=inp.score_margin,
        ambiguity_status=inp.ambiguity_status,
    )
    preview = build_activation_preview(
        intent,
        target,
        seq=seq,
        allowed_operations=list(node.allowed_operations) if node else [],
    )
    return intent, target, preview


def build_summary(
    inputs: list[PatchTargetingInput],
    intents: list[PatchIntent],
    targets: list[PatchTargetCandidate],
    previews: list[ActivationPreview],
) -> dict[str, Any]:
    intent_counts = Counter(i.intent_status for i in intents)
    target_counts = Counter(t.target_status for t in targets)
    preview_counts = Counter(p.preview_status for p in previews)
    op_counts = Counter(i.requested_operation for i in intents)
    tmpl_counts = Counter(i.template_id for i in intents if i.template_id)
    reason_counts: Counter[str] = Counter()
    for i in intents:
        for r in i.reason_codes:
            reason_counts[r] += 1

    # Global status priority: INVALID > BLOCKED > REVIEW > VALID
    if intent_counts.get("INVALID", 0) > 0 or preview_counts.get("PREVIEW_INVALID", 0) > 0:
        global_status = "INVALID"
    elif intent_counts.get("BLOCKED", 0) > 0 or preview_counts.get("PREVIEW_BLOCKED", 0) > 0:
        # PREVIEW_BLOCKED is expected for activation-disabled eligible cases;
        # only raise BLOCKED if intent BLOCKED exists OR all are blocked without eligible
        if intent_counts.get("BLOCKED", 0) > 0:
            global_status = "BLOCKED"
        elif intent_counts.get("REVIEW_REQUIRED", 0) > 0:
            global_status = "REVIEW"
        elif intent_counts.get("ELIGIBLE", 0) > 0:
            # Eligible intents with preview blocked by activation → REVIEW (safe observational)
            global_status = "REVIEW"
        else:
            global_status = "BLOCKED"
    elif intent_counts.get("REVIEW_REQUIRED", 0) > 0:
        global_status = "REVIEW"
    else:
        global_status = "VALID"

    return {
        "stage": "patch_targeting_summary",
        "input_count": len(inputs),
        "eligible_count": intent_counts.get("ELIGIBLE", 0),
        "review_required_count": intent_counts.get("REVIEW_REQUIRED", 0),
        "blocked_count": intent_counts.get("BLOCKED", 0),
        "invalid_count": intent_counts.get("INVALID", 0),
        "resolved_target_count": target_counts.get("RESOLVED", 0),
        "review_target_count": target_counts.get("REVIEW", 0),
        "unresolved_target_count": target_counts.get("UNRESOLVED", 0),
        "invalid_target_count": target_counts.get("INVALID", 0),
        "preview_ready_count": preview_counts.get("PREVIEW_READY", 0),
        "preview_review_count": preview_counts.get("PREVIEW_REVIEW", 0),
        "preview_blocked_count": preview_counts.get("PREVIEW_BLOCKED", 0),
        "preview_invalid_count": preview_counts.get("PREVIEW_INVALID", 0),
        "operation_counts": dict(sorted(op_counts.items())),
        "template_counts": dict(sorted(tmpl_counts.items())),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "template_allowed_count": sum(1 for t in targets if t.template_allowed),
        "writer_supported_count": sum(1 for t in targets if t.writer_supported),
        "activation_allowed_count": sum(1 for t in targets if t.activation_allowed),
        "actual_patch_created_count": 0,
        "actual_document_changed_count": 0,
        "actual_writer_called_count": 0,
        "global_patch_targeting_status": global_status,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": (
            "PR-22 observational patch targeting. "
            "No actual patch, DOCX write, or writer call."
        ),
    }


def run_patch_targeting_engine(
    *,
    inputs: list[PatchTargetingInput] | None = None,
    nodes: list[TemplateNodeCandidate] | None = None,
) -> dict[str, Any]:
    inputs = list(inputs) if inputs is not None else sample_patch_targeting_inputs()
    nodes = list(nodes) if nodes is not None else load_generic_node_candidates()
    node_ids = {n.template_node_id for n in nodes}

    intents: list[PatchIntent] = []
    targets: list[PatchTargetCandidate] = []
    previews: list[ActivationPreview] = []

    for seq, inp in enumerate(
        sorted(inputs, key=lambda x: x.change_id), start=1
    ):
        intent, target, preview = process_one(inp, seq=seq, nodes=nodes)
        intents.append(intent)
        targets.append(target)
        previews.append(preview)

    summary = build_summary(inputs, intents, targets, previews)
    validation = validate_patch_targeting(
        intents=intents,
        targets=targets,
        previews=previews,
        input_change_ids={i.change_id for i in inputs},
        known_nodes=node_ids,
        summary=summary,
    )

    return {
        "stage": "patch_targeting_engine",
        "schema_version": "patch_targeting_v1",
        "inputs": [i.to_dict() for i in sorted(inputs, key=lambda x: x.change_id)],
        "intents": [i.to_dict() for i in intents],
        "targets": [t.to_dict() for t in targets],
        "previews": [p.to_dict() for p in previews],
        "summary": summary,
        "validation": validation,
        "note": (
            "PR-22 observational Generic Patch Targeting / Patch Intent Bridge. "
            "Does not mutate documents, Change Review, or call DOCX Writer."
        ),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "actual_patch_created": False,
        "actual_writer_called": False,
    }
