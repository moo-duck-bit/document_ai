# -*- coding: utf-8 -*-
"""PR-18: Template inventory + orchestration."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.template.adapters import (
    build_mddr_template,
    build_mdsr_template,
    map_artifacts_to_template_nodes,
)
from document_ai.template.registry import TemplateRegistry
from document_ai.template.validation import validate_template_layer


def build_template_inventory(
    registry: TemplateRegistry,
    mappings: list[dict[str, Any]],
) -> dict[str, Any]:
    templates = registry.list_templates()
    nodes = registry.list_nodes()
    section_count = sum(len(t.sections) for t in templates)
    field_count = sum(len(f) for t in templates for s in t.sections for f in [s.fields])
    by_doc: dict[str, Any] = {}
    for t in templates:
        alias = (t.metadata or {}).get("source_document_alias") or t.document_type
        by_doc[str(alias)] = {
            "template_id": t.template_id,
            "document_type": t.document_type,
            "section_count": len(t.sections),
            "field_count": sum(len(s.fields) for s in t.sections),
            "node_count": sum(1 for n in nodes if n.template_id == t.template_id),
            "mapped_artifact_count": sum(
                1
                for m in mappings
                if m.get("template_id") == t.template_id and m.get("mapping_status") == "MAPPED"
            ),
        }
    return {
        "stage": "template_inventory",
        "template_count": len(templates),
        "section_count": section_count,
        "field_count": field_count,
        "node_count": len(nodes),
        "mapping_total_count": len(mappings),
        "documents": by_doc,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def build_template_summary(
    registry: TemplateRegistry,
    mappings: list[dict[str, Any]],
    *,
    global_template_status: str,
) -> dict[str, Any]:
    templates = registry.list_templates()
    nodes = registry.list_nodes()
    section_count = sum(len(t.sections) for t in templates)
    field_count = sum(len(s.fields) for t in templates for s in t.sections)
    status_counts = Counter(str(m.get("mapping_status") or "") for m in mappings)
    method_counts = Counter(str(m.get("mapping_method") or "") for m in mappings)
    reason_counts: Counter[str] = Counter()
    for m in mappings:
        for c in m.get("mapping_reason_codes") or []:
            reason_counts[str(c)] += 1
    doc_counts = Counter(str(m.get("document") or "UNKNOWN") for m in mappings)
    template_counts = Counter(str(m.get("template_id") or "NONE") for m in mappings)

    return {
        "stage": "template_summary",
        "template_count": len(templates),
        "document_type_count": len({t.document_type for t in templates}),
        "section_count": section_count,
        "field_count": field_count,
        "node_count": len(nodes),
        "mapping_total_count": len(mappings),
        "mapped_count": status_counts.get("MAPPED", 0),
        "review_count": status_counts.get("REVIEW", 0),
        "unmapped_count": status_counts.get("UNMAPPED", 0),
        "invalid_count": status_counts.get("INVALID", 0),
        "document_counts": dict(sorted(doc_counts.items())),
        "template_counts": dict(sorted(template_counts.items())),
        "mapping_method_counts": dict(sorted(method_counts.items())),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "global_template_status": global_template_status,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def run_template_abstraction_layer(
    *,
    review_items: list[Any] | None = None,
    patches: list[Any] | None = None,
    preview_entries: list[Any] | None = None,
    gate_results: list[Any] | None = None,
    activation_items: list[Any] | None = None,
) -> dict[str, Any]:
    """Initialize registry, register MDSR/MDDR, map artifacts, validate."""
    registry = TemplateRegistry()
    registry.register_template(build_mdsr_template())
    registry.register_template(build_mddr_template())

    mappings = map_artifacts_to_template_nodes(
        registry,
        review_items=review_items,
        patches=patches,
        preview_entries=preview_entries,
        gate_results=gate_results,
        activation_items=activation_items,
    )
    # provisional summary for validation count checks
    provisional = build_template_summary(
        registry, mappings, global_template_status="REVIEW"
    )
    inventory = build_template_inventory(registry, mappings)
    validation = validate_template_layer(
        registry,
        mappings=mappings,
        summary=provisional,
        inventory=inventory,
        review_items=review_items if isinstance(review_items, list) else None,
    )
    summary = build_template_summary(
        registry,
        mappings,
        global_template_status=str(validation.get("global_template_status") or "REVIEW"),
    )
    # re-validate summary counts with final summary
    validation = validate_template_layer(
        registry,
        mappings=mappings,
        summary=summary,
        inventory=inventory,
    )

    return {
        "stage": "template_abstraction_layer",
        "schema_version": "template_schema_v1",
        "registry": registry.to_registry_payload(),
        "inventory": inventory,
        "nodes": {
            "stage": "template_nodes",
            "node_count": len(registry.list_nodes()),
            "nodes": [n.to_dict() for n in registry.list_nodes()],
        },
        "mappings": {
            "stage": "template_mappings",
            "mapping_count": len(mappings),
            "mappings": mappings,
        },
        "summary": summary,
        "validation": validation,
        "note": (
            "PR-18 observational template abstraction. "
            "Does not mutate Gate/Review/Writer or DOCX."
        ),
    }
