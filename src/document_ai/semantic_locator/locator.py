# -*- coding: utf-8 -*-
"""PR-21: Semantic Locator Engine orchestration (observational)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.semantic_locator.ranking import build_match_results
from document_ai.semantic_locator.schema import (
    SemanticLocatorInput,
    SemanticMatchResult,
    TemplateNodeCandidate,
)
from document_ai.semantic_locator.thresholds import GENERIC_TEMPLATE_IDS
from document_ai.semantic_locator.validation import validate_semantic_locator
from document_ai.template.generic_templates import (
    build_business_proposal_template,
    build_general_report_template,
    build_static_nodes_for_template,
)


def load_generic_node_candidates(
    *,
    template_ids: set[str] | None = None,
) -> list[TemplateNodeCandidate]:
    """Load field-level generic template nodes as candidates."""
    wanted = template_ids or set(GENERIC_TEMPLATE_IDS)
    builders = {
        "general_report_v1": build_general_report_template,
        "business_proposal_v1": build_business_proposal_template,
    }
    out: list[TemplateNodeCandidate] = []
    for tid in sorted(wanted):
        if tid not in builders:
            continue
        template = builders[tid]()
        for node in build_static_nodes_for_template(template):
            if not node.field_id:
                continue  # skip document/section shells
            hints = node.locator_hints.to_dict() if hasattr(node.locator_hints, "to_dict") else {}
            out.append(
                TemplateNodeCandidate(
                    template_node_id=node.template_node_id,
                    template_id=node.template_id,
                    section_id=node.section_id,
                    field_id=node.field_id,
                    display_name=node.display_name,
                    locator_hints=hints,
                    source_requirement_id=node.source_requirement_id,
                    allowed_operations=list(node.allowed_operations),
                    metadata={"requirement_id_optional": True},
                )
            )
    out.sort(key=lambda n: n.template_node_id)
    return out


def sample_locator_inputs() -> list[SemanticLocatorInput]:
    """Deterministic sample inputs covering required PR-21 cases."""
    return [
        SemanticLocatorInput(
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-001",
            template_id="general_report_v1",
            heading_path=["방법론", "데이터 출처"],
            heading_text="데이터 출처",
            section_name="데이터 출처",
            field_label="데이터 출처",
            candidate_text="방법론 데이터 출처",
            metadata={"case": "exact_path_data_sources"},
        ),
        SemanticLocatorInput(
            document_id="sample_md_business_proposal_001",
            locator_candidate_id="LC-SAMPLE-002",
            template_id="business_proposal_v1",
            heading_path=["수행 계획", "일정"],
            heading_text="일정",
            section_name="일정",
            field_label="일정",
            candidate_text="수행 계획 일정",
            metadata={"case": "exact_path_execution_schedule"},
        ),
        SemanticLocatorInput(
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-003",
            template_id="general_report_v1",
            heading_path=["결과"],
            heading_text="결과",
            section_name="결과",
            field_label=None,
            candidate_text="결과",
            metadata={"case": "ambiguous_results_heading"},
        ),
        SemanticLocatorInput(
            document_id="sample_md_business_proposal_001",
            locator_candidate_id="LC-SAMPLE-004",
            template_id="business_proposal_v1",
            heading_path=["일정"],
            heading_text="일정",
            section_name="일정",
            field_label=None,
            candidate_text="일정",
            metadata={"case": "ambiguous_schedule_heading"},
        ),
        SemanticLocatorInput(
            document_id="sample_md_general_report_001",
            locator_candidate_id="LC-SAMPLE-005",
            template_id="general_report_v1",
            heading_path=["존재하지 않는 섹션"],
            heading_text="존재하지 않는 섹션",
            section_name="존재하지 않는 섹션",
            candidate_text="존재하지 않는 섹션",
            metadata={"case": "unknown_section"},
        ),
    ]


def _primary_results(results: list[SemanticMatchResult]) -> list[SemanticMatchResult]:
    return [r for r in results if r.rank == 1]


def build_summary(
    inputs: list[SemanticLocatorInput],
    nodes: list[TemplateNodeCandidate],
    results: list[SemanticMatchResult],
) -> dict[str, Any]:
    primary = _primary_results(results)
    status_counts = Counter(r.match_status for r in primary)
    reason_counts: Counter[str] = Counter()
    for r in primary:
        for c in r.reason_codes:
            reason_counts[c] += 1
    template_counts = Counter(
        r.template_id for r in primary if r.template_id and r.match_status == "MATCHED"
    )
    ambiguous = sum(1 for r in primary if r.ambiguity_status == "AMBIGUOUS")

    def _avg(attr: str) -> float:
        vals = [getattr(r, attr) for r in primary]
        if not vals:
            return 0.0
        return round(sum(vals) / len(vals), 4)

    # Global status: INVALID if any INVALID primary; else REVIEW if any REVIEW/UNMAPPED; else VALID
    if status_counts.get("INVALID", 0) > 0:
        global_status = "INVALID"
    elif status_counts.get("REVIEW", 0) > 0 or status_counts.get("UNMAPPED", 0) > 0:
        global_status = "REVIEW"
    else:
        global_status = "VALID"

    return {
        "stage": "semantic_locator_summary",
        "input_count": len(inputs),
        "template_candidate_count": len(
            {n.template_id for n in nodes}
        ),
        "node_candidate_count": len(nodes),
        "matched_count": status_counts.get("MATCHED", 0),
        "review_count": status_counts.get("REVIEW", 0),
        "unmapped_count": status_counts.get("UNMAPPED", 0),
        "invalid_count": status_counts.get("INVALID", 0),
        "average_rule_score": _avg("rule_score"),
        "average_semantic_score": _avg("semantic_score"),
        "average_combined_score": _avg("combined_score"),
        "ambiguous_count": ambiguous,
        "template_counts": dict(sorted(template_counts.items())),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "global_semantic_locator_status": global_status,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": (
            "PR-21 observational semantic locator. "
            "No patch, DOCX write, LLM, or remote embedding."
        ),
    }


def run_semantic_locator_engine(
    *,
    inputs: list[SemanticLocatorInput] | None = None,
    nodes: list[TemplateNodeCandidate] | None = None,
    emit_all_ranks: bool = True,
) -> dict[str, Any]:
    """Run observational semantic locator on sample or provided inputs."""
    inputs = list(inputs) if inputs is not None else sample_locator_inputs()
    nodes = list(nodes) if nodes is not None else load_generic_node_candidates()

    all_results: list[SemanticMatchResult] = []
    for i, inp in enumerate(sorted(inputs, key=lambda x: x.locator_candidate_id), start=1):
        ranked = build_match_results(
            inp,
            nodes,
            match_seq=i,
            known_template_ids=set(GENERIC_TEMPLATE_IDS),
        )
        if emit_all_ranks:
            # keep top-5 alternatives max for artifact size
            all_results.extend(ranked[:5])
        else:
            all_results.extend([r for r in ranked if r.rank == 1])

    summary = build_summary(inputs, nodes, all_results)
    validation = validate_semantic_locator(
        results=all_results,
        nodes=nodes,
        input_ids={i.locator_candidate_id for i in inputs},
        summary=summary,
    )

    # Ranked matches: primary only, sorted by locator id
    ranked_primary = sorted(
        _primary_results(all_results),
        key=lambda r: r.locator_candidate_id,
    )

    return {
        "stage": "semantic_locator_engine",
        "schema_version": "semantic_locator_v1",
        "inputs": [i.to_dict() for i in sorted(inputs, key=lambda x: x.locator_candidate_id)],
        "template_node_candidates": [n.to_dict() for n in nodes],
        "match_results": [r.to_dict() for r in all_results],
        "ranked_matches": [r.to_dict() for r in ranked_primary],
        "summary": summary,
        "validation": validation,
        "note": (
            "PR-21 observational Generic Template Semantic Locator Engine. "
            "Does not mutate documents, Change Review, or DOCX."
        ),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }
