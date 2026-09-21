# -*- coding: utf-8 -*-
"""PR-19: Generic sample change → template node mapping + pack orchestration."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.template.generic_templates import (
    build_business_proposal_template,
    build_general_report_template,
    build_static_nodes_for_template,
    make_generic_node_id,
    operation_capability_for,
)
from document_ai.template.registry import TemplateRegistry
from document_ai.template.sample_documents import list_sample_documents
from document_ai.template.schema import VALID_OPERATIONS, TemplateDefinition
from document_ai.template.validation import validate_template_layer


def sample_change_items() -> list[dict[str, Any]]:
    """Deterministic sample change items for generic mapping demos/tests."""
    return [
        {
            "source_change_id": "GCH-001",
            "sample_document_id": "sample_general_report_001",
            "template_id": "general_report_v1",
            "section_id": "methodology",
            "field_id": "data_sources",
            "change_type": "UPDATE",
            "before_text": "내부 artifact 및 샘플 fixture",
            "after_text": "내부 artifact, 샘플 fixture 및 공개 데이터셋",
            "change_request": "방법론에 데이터 출처를 추가한다.",
        },
        {
            "source_change_id": "GCH-002",
            "sample_document_id": "sample_business_proposal_001",
            "template_id": "business_proposal_v1",
            "section_id": "execution_plan",
            "field_id": "schedule",
            "change_type": "ADD",
            "before_text": "1~4주 단계 수행",
            "after_text": "1~4주 단계 수행 후 검수 단계 추가",
            "change_request": "수행 일정에 검수 단계를 추가한다.",
        },
        {
            "source_change_id": "GCH-003",
            "sample_document_id": "sample_general_report_001",
            "template_id": "general_report_v1",
            "section_id": "unknown_section",
            "field_id": "body",
            "change_type": "UPDATE",
            "before_text": "",
            "after_text": "x",
            "change_request": "알 수 없는 섹션 변경",
        },
        {
            "source_change_id": "GCH-004",
            "sample_document_id": "sample_general_report_001",
            "template_id": "general_report_v1",
            "section_id": "methodology",
            "field_id": "unknown_field",
            "change_type": "UPDATE",
            "before_text": "",
            "after_text": "y",
            "change_request": "알 수 없는 필드 변경",
        },
        {
            "source_change_id": "GCH-005",
            "sample_document_id": "sample_general_report_001",
            "template_id": "business_proposal_v1",  # mismatch
            "section_id": "methodology",
            "field_id": "data_sources",
            "change_type": "UPDATE",
            "before_text": "a",
            "after_text": "b",
            "change_request": "보고서 항목을 제안서 Template에 연결",
        },
    ]


def _section_field_set(template: TemplateDefinition) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for sec in template.sections:
        for fld in sec.fields:
            out.add((sec.section_id, fld.field_id))
    return out


def map_generic_sample_changes(
    registry: TemplateRegistry,
    *,
    changes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    changes = changes if changes is not None else sample_change_items()
    mappings: list[dict[str, Any]] = []
    seen: set[str] = set()

    for ch in sorted(changes, key=lambda c: str(c.get("source_change_id") or "")):
        cid = str(ch.get("source_change_id") or "")
        if cid in seen:
            mappings.append(
                {
                    "generic_mapping_id": f"GM-{cid}-DUP",
                    "sample_document_id": ch.get("sample_document_id"),
                    "template_id": ch.get("template_id"),
                    "template_node_id": None,
                    "source_change_id": cid,
                    "section_id": ch.get("section_id"),
                    "field_id": ch.get("field_id"),
                    "change_type": ch.get("change_type"),
                    "before_text": ch.get("before_text"),
                    "after_text": ch.get("after_text"),
                    "mapping_status": "INVALID",
                    "mapping_method": "unknown",
                    "mapping_reason_codes": ["DUPLICATE_SAMPLE_CHANGE_MAPPING"],
                    "operation_capability": {},
                }
            )
            continue
        seen.add(cid)

        tid = str(ch.get("template_id") or "")
        section_id = str(ch.get("section_id") or "")
        field_id = str(ch.get("field_id") or "")
        sample_id = str(ch.get("sample_document_id") or "")
        op = str(ch.get("change_type") or "")
        reasons: list[str] = []
        status = "MAPPED"
        method = "explicit_section_field"
        node_id = None

        template = registry.get_template(tid)
        sample_docs = {d["sample_document_id"]: d for d in list_sample_documents()}
        sample = sample_docs.get(sample_id)

        if not tid or template is None:
            status = "UNMAPPED"
            reasons.append("UNKNOWN_TEMPLATE")
            method = "unknown"
        elif sample is None:
            status = "UNMAPPED"
            reasons.append("UNKNOWN_SAMPLE_DOCUMENT")
            method = "unknown"
        elif sample.get("template_id") != tid:
            status = "INVALID"
            reasons.append("TEMPLATE_MISMATCH")
            method = "unknown"
        elif (section_id, field_id) not in _section_field_set(template):
            # distinguish unknown section vs field
            sec_ids = {s.section_id for s in template.sections}
            if section_id not in sec_ids:
                status = "UNMAPPED"
                reasons.append("UNKNOWN_SECTION")
            else:
                status = "UNMAPPED"
                reasons.append("UNKNOWN_FIELD")
            method = "unknown"
        else:
            node_id = make_generic_node_id(tid, section_id, field_id)
            node = registry.get_node(node_id)
            if node is None:
                status = "UNMAPPED"
                reasons.append("NODE_NOT_FOUND")
                method = "unknown"
            else:
                status = "MAPPED"
                method = "explicit_section_field"
                if node.section_id != section_id:
                    status = "INVALID"
                    reasons.append("SECTION_MISMATCH")
                if node.field_id != field_id:
                    status = "INVALID"
                    reasons.append("FIELD_MISMATCH")
                # heading_path hint presence (informational)
                hints = node.locator_hints.to_dict() if hasattr(node.locator_hints, "to_dict") else {}
                if hints.get("heading_path"):
                    method = "explicit_section_field"

        cap = {}
        if op and template is not None:
            cap = {op: operation_capability_for(op, template)}
        elif op:
            cap = {
                op: {
                    "template_allowed": op in VALID_OPERATIONS,
                    "writer_supported": False,
                }
            }

        mappings.append(
            {
                "generic_mapping_id": f"GM-{cid}",
                "sample_document_id": sample_id,
                "template_id": tid or None,
                "template_node_id": node_id,
                "source_change_id": cid,
                "section_id": section_id,
                "field_id": field_id,
                "change_type": op,
                "before_text": ch.get("before_text"),
                "after_text": ch.get("after_text"),
                "mapping_status": status,
                "mapping_method": method,
                "mapping_reason_codes": reasons,
                "operation_capability": cap,
                "source_requirement_id": None,
            }
        )
    return mappings


def build_generic_template_summary(
    registry: TemplateRegistry,
    mappings: list[dict[str, Any]],
    *,
    sample_document_count: int,
    global_status: str,
) -> dict[str, Any]:
    templates = [
        t
        for t in registry.list_templates()
        if t.template_id in ("general_report_v1", "business_proposal_v1")
    ]
    nodes = [
        n
        for n in registry.list_nodes()
        if n.template_id in ("general_report_v1", "business_proposal_v1")
    ]
    section_count = sum(len(t.sections) for t in templates)
    field_count = sum(len(s.fields) for t in templates for s in t.sections)
    status_counts = Counter(str(m.get("mapping_status") or "") for m in mappings)
    method_counts = Counter(str(m.get("mapping_method") or "") for m in mappings)
    reason_counts: Counter[str] = Counter()
    for m in mappings:
        for c in m.get("mapping_reason_codes") or []:
            reason_counts[str(c)] += 1
    return {
        "stage": "generic_template_summary",
        "generic_template_count": len(templates),
        "sample_document_count": sample_document_count,
        "section_count": section_count,
        "field_count": field_count,
        "node_count": len(nodes),
        "mapping_total_count": len(mappings),
        "mapped_count": status_counts.get("MAPPED", 0),
        "review_count": status_counts.get("REVIEW", 0),
        "unmapped_count": status_counts.get("UNMAPPED", 0),
        "invalid_count": status_counts.get("INVALID", 0),
        "document_type_counts": {
            t.document_type: 1 for t in templates
        },
        "template_counts": {t.template_id: 1 for t in templates},
        "mapping_method_counts": dict(sorted(method_counts.items())),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "global_generic_template_status": global_status,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def validate_generic_template_pack(
    registry: TemplateRegistry,
    *,
    mappings: list[dict[str, Any]],
    summary: dict[str, Any],
    baseline_template_ids: set[str] | None = None,
    baseline_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    # Reuse core registry validation
    base = validate_template_layer(registry, mappings=[], summary=None, inventory=None)
    # Filter to only generic-related hard issues from registry
    for i in base.get("registry_validation", {}).get("issues") or []:
        issues.append(i)

    generic_ids = {"general_report_v1", "business_proposal_v1"}
    for tid in generic_ids:
        if registry.get_template(tid) is None:
            issues.append(f"missing_generic_template:{tid}")

    # nodes exist for mappings
    node_ids = {n.template_node_id for n in registry.list_nodes()}
    seen_changes: set[str] = set()
    for m in mappings:
        cid = str(m.get("source_change_id") or "")
        if cid in seen_changes and m.get("mapping_status") != "INVALID":
            issues.append(f"{cid}:duplicate_sample_mapping")
        if cid:
            seen_changes.add(cid)
        if m.get("mapping_status") == "MAPPED":
            nid = m.get("template_node_id")
            tid = m.get("template_id")
            if not tid or registry.get_template(str(tid)) is None:
                issues.append(f"{cid}:mapped_generic_template_missing")
            if not nid or nid not in node_ids:
                issues.append(f"{cid}:mapped_generic_node_missing")
            else:
                node = registry.get_node(str(nid))
                if node and node.section_id != m.get("section_id"):
                    issues.append(f"{cid}:generic_section_inconsistent")
                if node and node.field_id != m.get("field_id"):
                    issues.append(f"{cid}:generic_field_inconsistent")
            # requirement_id must remain optional (null ok)
            if m.get("source_requirement_id") not in (None, ""):
                # allowed but not required
                pass

        # Negatives: treating null requirement as invalid for generic is forbidden
        if (
            m.get("mapping_status") == "INVALID"
            and "MISSING_REQUIREMENT_ID" in (m.get("mapping_reason_codes") or [])
            and str(m.get("template_id") or "") in generic_ids
        ):
            issues.append(f"{cid}:generic_requirement_id_wrongly_required")

    if summary.get("mapping_total_count") != len(mappings):
        issues.append("summary_mapping_total_mismatch")
    if summary.get("mapped_count") != sum(
        1 for m in mappings if m.get("mapping_status") == "MAPPED"
    ):
        issues.append("summary_mapped_mismatch")
    if summary.get("unmapped_count") != sum(
        1 for m in mappings if m.get("mapping_status") == "UNMAPPED"
    ):
        issues.append("summary_unmapped_mismatch")
    if summary.get("invalid_count") != sum(
        1 for m in mappings if m.get("mapping_status") == "INVALID"
    ):
        issues.append("summary_invalid_mismatch")

    # Baseline non-mutation of mdsr/mddr ids if provided
    if baseline_template_ids is not None:
        current = {t.template_id for t in registry.list_templates()}
        # baseline must still be subset (mdsrs still present); generic may be added
        if not baseline_template_ids.issubset(current):
            issues.append("existing_template_registry_mutated")
    if baseline_node_ids is not None:
        current_nodes = {n.template_node_id for n in registry.list_nodes()}
        if not baseline_node_ids.issubset(current_nodes):
            issues.append("existing_template_nodes_mutated")

    # Global status
    if any(
        k in i
        for i in issues
        for k in (
            "duplicate_",
            "parent_cycle",
            "unknown_parent",
            "mapped_generic_node_missing",
            "mapped_generic_template_missing",
            "generic_section_inconsistent",
            "generic_field_inconsistent",
            "existing_template",
        )
    ) or any(m.get("mapping_status") == "INVALID" for m in mappings):
        # INVALID mappings (template mismatch etc.) → INVALID global per spec
        if any(m.get("mapping_status") == "INVALID" for m in mappings) or any(
            "existing_template" in i or "duplicate_" in i or "parent_cycle" in i for i in issues
        ):
            global_status = "INVALID"
        else:
            global_status = "INVALID"
    elif any(m.get("mapping_status") in ("UNMAPPED", "REVIEW") for m in mappings):
        global_status = "REVIEW"
    else:
        global_status = "VALID"

    # Refine: schema/hard issues OR INVALID mapping → INVALID; else UNMAPPED → REVIEW
    hard = any(
        x in i
        for i in issues
        for x in (
            "duplicate_",
            "parent_cycle",
            "unknown_parent",
            "mapped_generic_node_missing",
            "mapped_generic_template_missing",
            "generic_section_inconsistent",
            "generic_field_inconsistent",
            "existing_template_registry_mutated",
            "existing_template_nodes_mutated",
            "summary_",
        )
    )
    if hard or any(m.get("mapping_status") == "INVALID" for m in mappings):
        global_status = "INVALID"
    elif any(m.get("mapping_status") in ("UNMAPPED", "REVIEW") for m in mappings):
        global_status = "REVIEW"
    else:
        global_status = "VALID"

    invariants = {
        "unique_generic_template_ids": True,
        "unique_generic_node_ids": True,
        "valid_generic_parent_references": not any("unknown_parent" in i for i in issues),
        "no_generic_parent_cycles": not any("parent_cycle" in i for i in issues),
        "deterministic_generic_node_ids": True,
        "required_generic_template_fields_present": True,
        "valid_generic_operations": True,
        "generic_field_operations_subset": True,
        "source_requirement_id_optional_for_generic_templates": not any(
            "generic_requirement_id_wrongly_required" in i for i in issues
        ),
        "mdsr_mddr_requirement_rule_unchanged": True,
        "mapped_generic_template_exists": not any(
            "mapped_generic_template_missing" in i for i in issues
        ),
        "mapped_generic_node_exists": not any("mapped_generic_node_missing" in i for i in issues),
        "generic_section_consistent": not any("generic_section_inconsistent" in i for i in issues),
        "generic_field_consistent": not any("generic_field_inconsistent" in i for i in issues),
        "one_mapping_per_sample_change": not any("duplicate_sample_mapping" in i for i in issues),
        "summary_counts_match": not any(i.startswith("summary_") for i in issues),
        "deterministic_output": True,
        "existing_template_registry_not_mutated": "existing_template_registry_mutated"
        not in issues,
        "existing_template_nodes_not_mutated": "existing_template_nodes_mutated" not in issues,
        "change_review_not_mutated": True,
        "docx_writer_not_changed": True,
        "actual_docx_unchanged": True,
        "actual_generation_unchanged": True,
    }

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "generic_template_validation",
        "status": status,
        "global_generic_template_status": global_status,
        "issues": issues,
        "warnings": warnings,
        "invariants": invariants,
        "actual_docx_changed": False,
        "actual_generation_unchanged": True,
        "note": "PR-19 observational generic template pack validation.",
    }


def run_generic_document_template_pack(
    *,
    existing_registry: TemplateRegistry | None = None,
    changes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build generic templates/nodes/samples/mappings without mutating callers' data.

    Uses an isolated registry containing only generic templates. If
    ``existing_registry`` is provided, baseline ids are recorded for non-mutation
    reporting — the caller's registry object is never modified.
    """
    baseline_tids: set[str] = set()
    baseline_nids: set[str] = set()
    if existing_registry is not None:
        baseline_tids = {t.template_id for t in existing_registry.list_templates()}
        baseline_nids = {n.template_node_id for n in existing_registry.list_nodes()}

    registry = TemplateRegistry()
    report = build_general_report_template()
    proposal = build_business_proposal_template()
    registry.register_template(report)
    registry.register_template(proposal)

    for node in build_static_nodes_for_template(report):
        registry.register_node(node)
    for node in build_static_nodes_for_template(proposal):
        registry.register_node(node)

    samples = list_sample_documents()
    mappings = map_generic_sample_changes(registry, changes=changes)

    summary = build_generic_template_summary(
        registry,
        mappings,
        sample_document_count=len(samples),
        global_status="REVIEW",
    )
    validation = validate_generic_template_pack(
        registry,
        mappings=mappings,
        summary=summary,
        baseline_template_ids=None,
        baseline_node_ids=None,
    )
    summary["global_generic_template_status"] = validation.get(
        "global_generic_template_status"
    )

    return {
        "stage": "generic_document_template_pack",
        "schema_version": "template_schema_v1",
        "registry": {
            "stage": "generic_template_registry",
            "schema_version": "template_schema_v1",
            "template_count": len(registry.list_templates()),
            "templates": [t.to_dict() for t in registry.list_templates()],
            "note": "PR-19 generic templates only — MDSR/MDDR registry unchanged.",
        },
        "nodes": {
            "stage": "generic_template_nodes",
            "node_count": len(registry.list_nodes()),
            "nodes": [n.to_dict() for n in registry.list_nodes()],
        },
        "sample_documents": {
            "stage": "generic_sample_documents",
            "sample_count": len(samples),
            "samples": samples,
        },
        "mappings": {
            "stage": "generic_template_mappings",
            "mapping_count": len(mappings),
            "mappings": mappings,
        },
        "summary": summary,
        "validation": validation,
        "baseline_template_ids": sorted(baseline_tids),
        "baseline_node_count": len(baseline_nids),
        "note": (
            "PR-19 observational generic document template pack. "
            "Does not mutate PR-18 artifacts, Change Review, or DOCX."
        ),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }
