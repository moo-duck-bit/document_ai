# -*- coding: utf-8 -*-
"""PR-23: Physical locator orchestrator (observational)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.document_parser.markdown_parser import parse_markdown_text
from document_ai.document_parser.normalization import normalize_document
from document_ai.document_parser.parser import SAMPLE_MARKDOWN_PROPOSAL, SAMPLE_MARKDOWN_REPORT
from document_ai.document_parser.structure import (
    DocumentModel,
    ListModel,
    ParagraphModel,
    SectionModel,
    TableModel,
)
from document_ai.physical_locator.locator_engine import locate_physical_target
from document_ai.physical_locator.schema import (
    PhysicalLocatorInput,
    PhysicalLocationCandidate,
    PrimaryPhysicalLocation,
)
from document_ai.physical_locator.validation import validate_physical_locator


def _sample_documents() -> dict[str, DocumentModel]:
    report = normalize_document(
        parse_markdown_text(
            SAMPLE_MARKDOWN_REPORT,
            document_id="sample_md_general_report_001",
            document_type="general_report",
        )
    )
    proposal = normalize_document(
        parse_markdown_text(
            SAMPLE_MARKDOWN_PROPOSAL,
            document_id="sample_md_business_proposal_001",
            document_type="business_proposal",
        )
    )
    # Duplicate-heading fixture for REVIEW ambiguity
    dup = DocumentModel(
        document_id="sample_dup_headings_001",
        document_type="general_report",
        title="중복 헤딩",
        source_format="object",
        sections=[
            SectionModel(
                section_id="sec_a",
                heading="결과",
                heading_level=1,
                order=1,
                paragraphs=[
                    ParagraphModel("p1", "결과 A", 1),
                    ParagraphModel("p2", "결과 A", 2),  # duplicate paragraph text
                ],
                tables=[
                    TableModel("t1", headers=["a", "b"], rows=[["1", "2"]], order=1),
                    TableModel("t2", headers=["a", "b"], rows=[["1", "2"]], order=2),
                ],
                lists=[
                    ListModel("l1", items=["x", "y"], order=1),
                    ListModel("l2", items=["x", "y"], order=2),
                ],
            ),
            SectionModel(
                section_id="sec_b",
                heading="결과",  # duplicate heading
                heading_level=1,
                order=2,
                paragraphs=[ParagraphModel("p3", "결과 B", 1)],
            ),
        ],
    )
    empty = DocumentModel(
        document_id="sample_empty_001",
        document_type="general_report",
        title="empty",
        source_format="object",
        sections=[],
    )
    return {
        report.document_id: report,
        proposal.document_id: proposal,
        dup.document_id: dup,
        empty.document_id: empty,
    }


def sample_physical_locator_inputs() -> list[PhysicalLocatorInput]:
    return [
        # MATCHED paragraph — data_sources under 방법론/데이터 출처
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-001",
            patch_target_candidate_id="PTC-0001",
            document_id="sample_md_general_report_001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            section_id="methodology",
            field_id="data_sources",
            target_status="RESOLVED",
            heading_path_hint=["방법론", "데이터 출처"],
            field_label_hint="데이터 출처",
            preferred_location_type="PARAGRAPH",
            metadata={"case": "matched_paragraph"},
        ),
        # MATCHED table — same section has a table
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-002",
            patch_target_candidate_id="PTC-0002",
            document_id="sample_md_general_report_001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            section_id="methodology",
            field_id="tables",
            target_status="RESOLVED",
            heading_path_hint=["방법론", "데이터 출처"],
            field_label_hint="표",
            preferred_location_type="TABLE",
            metadata={"case": "matched_table"},
        ),
        # MATCHED list — results key_findings
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-003",
            patch_target_candidate_id="PTC-0003",
            document_id="sample_md_general_report_001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.results.key_findings",
            section_id="results",
            field_id="key_findings",
            target_status="RESOLVED",
            heading_path_hint=["결과"],
            field_label_hint="핵심 발견",
            preferred_location_type="LIST",
            metadata={"case": "matched_list"},
        ),
        # REVIEW — duplicate headings
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-004",
            patch_target_candidate_id="PTC-0004",
            document_id="sample_dup_headings_001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.results.body",
            section_id="results",
            field_id="body",
            target_status="RESOLVED",
            heading_path_hint=["결과"],
            field_label_hint="본문",
            preferred_location_type="PARAGRAPH",
            metadata={"case": "duplicate_heading_review"},
        ),
        # UNRESOLVED — empty document
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-005",
            patch_target_candidate_id="PTC-0005",
            document_id="sample_empty_001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.approach",
            section_id="methodology",
            field_id="approach",
            target_status="RESOLVED",
            heading_path_hint=["방법론", "접근 방식"],
            preferred_location_type="PARAGRAPH",
            metadata={"case": "unresolved_empty"},
        ),
        # INVALID — broken document
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-006",
            patch_target_candidate_id="PTC-0006",
            document_id="does_not_exist_doc",
            template_id="general_report_v1",
            template_node_id="general_report_v1.methodology.data_sources",
            section_id="methodology",
            field_id="data_sources",
            target_status="RESOLVED",
            heading_path_hint=["방법론", "데이터 출처"],
            metadata={"case": "invalid_missing_doc"},
        ),
        # INVALID — invalid patch target status
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-007",
            patch_target_candidate_id="PTC-0007",
            document_id="sample_md_general_report_001",
            template_id="general_report_v1",
            template_node_id=None,
            section_id=None,
            field_id=None,
            target_status="INVALID",
            heading_path_hint=[],
            metadata={"case": "invalid_target"},
        ),
        # Proposal schedule paragraph
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-008",
            patch_target_candidate_id="PTC-0008",
            document_id="sample_md_business_proposal_001",
            template_id="business_proposal_v1",
            template_node_id="business_proposal_v1.execution_plan.schedule",
            section_id="execution_plan",
            field_id="schedule",
            target_status="RESOLVED",
            heading_path_hint=["수행 계획", "일정"],
            field_label_hint="일정",
            preferred_location_type="PARAGRAPH",
            metadata={"case": "proposal_schedule"},
        ),
        # Duplicate paragraph case on dup doc (body)
        PhysicalLocatorInput(
            physical_locator_input_id="PLI-009",
            patch_target_candidate_id="PTC-0009",
            document_id="sample_dup_headings_001",
            template_id="general_report_v1",
            template_node_id="general_report_v1.results.body",
            section_id="results",
            field_id="body",
            target_status="RESOLVED",
            heading_path_hint=["결과"],
            preferred_location_type="PARAGRAPH",
            metadata={"case": "duplicate_paragraph"},
        ),
    ]


ARTIFACT_TOP_K_LIMIT = 8


def build_summary(
    inputs: list[PhysicalLocatorInput],
    full_candidates: list[PhysicalLocationCandidate],
    artifact_candidates: list[PhysicalLocationCandidate],
    primaries: list[PrimaryPhysicalLocation],
    *,
    external_activation_flag: bool = False,
) -> dict[str, Any]:
    status_counts = Counter(p.location_status for p in primaries)
    type_counts = Counter(c.location_type for c in full_candidates)
    if status_counts.get("INVALID", 0) > 0:
        global_status = "INVALID"
    elif status_counts.get("UNRESOLVED", 0) > 0 or status_counts.get("REVIEW", 0) > 0:
        global_status = "REVIEW"
    else:
        global_status = "VALID"
    return {
        "stage": "physical_locator_summary",
        "input_count": len(inputs),
        "candidate_count": len(full_candidates),
        "full_candidate_count": len(full_candidates),
        "artifact_candidate_count": len(artifact_candidates),
        "artifact_top_k_limit": ARTIFACT_TOP_K_LIMIT,
        "resolved_count": status_counts.get("RESOLVED", 0),
        "review_count": status_counts.get("REVIEW", 0),
        "unresolved_count": status_counts.get("UNRESOLVED", 0),
        "invalid_count": status_counts.get("INVALID", 0),
        "location_type_counts": dict(sorted(type_counts.items())),
        "global_physical_locator_status": global_status,
        "external_activation_flag": external_activation_flag,
        "observational_gate_forced_off": True,
        "activation_allowed": False,
        "actual_docx_changed_count": 0,
        "actual_writer_called_count": 0,
        "actual_patch_created_count": 0,
        "actual_docx_changed": False,
        "actual_writer_called": False,
        "actual_patch_created": False,
        "note": "PR-23 observational physical locator. No document mutation.",
    }


def run_physical_locator_engine(
    *,
    inputs: list[PhysicalLocatorInput] | None = None,
    documents: dict[str, DocumentModel] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    from document_ai.impact.docx_activation_writer import is_docx_activation_enabled

    inputs = list(inputs) if inputs is not None else sample_physical_locator_inputs()
    documents = dict(documents) if documents is not None else _sample_documents()
    external_flag = bool(is_docx_activation_enabled(env=env or {}))

    full_candidates: list[PhysicalLocationCandidate] = []
    artifact_candidates: list[PhysicalLocationCandidate] = []
    primaries: list[PrimaryPhysicalLocation] = []

    for seq, inp in enumerate(
        sorted(inputs, key=lambda x: x.physical_locator_input_id), start=1
    ):
        doc = documents.get(inp.document_id)
        ranked, primary = locate_physical_target(inp, doc, seq=seq)
        full_candidates.extend(ranked)
        topk = ranked[:ARTIFACT_TOP_K_LIMIT] if ranked else []
        # Primary must be in artifact Top-K when present
        if primary.physical_candidate_id and ranked:
            if not any(
                c.physical_candidate_id == primary.physical_candidate_id for c in topk
            ):
                topk = [ranked[0]] + [
                    c
                    for c in topk
                    if c.physical_candidate_id != ranked[0].physical_candidate_id
                ]
                topk = topk[:ARTIFACT_TOP_K_LIMIT]
        artifact_candidates.extend(topk)
        primaries.append(primary)

    summary = build_summary(
        inputs,
        full_candidates,
        artifact_candidates,
        primaries,
        external_activation_flag=external_flag,
    )
    validation = validate_physical_locator(
        candidates=full_candidates,
        primaries=primaries,
        input_target_ids={i.patch_target_candidate_id for i in inputs},
        known_document_ids=set(documents.keys()),
        summary=summary,
        external_activation_flag=external_flag,
        artifact_candidates=artifact_candidates,
    )

    return {
        "stage": "physical_locator_engine",
        "schema_version": "physical_locator_v1",
        "inputs": [
            i.to_dict()
            for i in sorted(inputs, key=lambda x: x.physical_locator_input_id)
        ],
        "full_candidates": [c.to_dict() for c in full_candidates],
        "candidates": [c.to_dict() for c in artifact_candidates],  # artifact Top-K
        "artifact_candidates": [c.to_dict() for c in artifact_candidates],
        "primaries": [p.to_dict() for p in primaries],
        "summary": summary,
        "validation": validation,
        "artifact_meta": {
            "candidate_scope": "TOP_K_PER_TARGET",
            "top_k_limit": ARTIFACT_TOP_K_LIMIT,
            "full_candidate_count": len(full_candidates),
            "artifact_candidate_count": len(artifact_candidates),
        },
        "external_activation_flag": external_flag,
        "observational_gate_forced_off": True,
        "activation_allowed": False,
        "note": (
            "PR-23 observational Generic Physical Locator. "
            "Does not mutate DOCX/Markdown or call Writer. "
            "candidates artifact is Top-K; validation uses full_candidates."
        ),
        "actual_docx_changed": False,
        "actual_writer_called": False,
        "actual_patch_created": False,
    }
