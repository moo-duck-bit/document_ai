# -*- coding: utf-8 -*-
"""PR-18: MDSR/MDDR adapters and artifact→node mapping."""

from __future__ import annotations

from typing import Any

from document_ai.impact.patch_plan import MDDR_FIELDS, MDSR_FIELDS
from document_ai.template.registry import TemplateRegistry
from document_ai.template.schema import (
    VALID_OPERATIONS,
    WRITER_SUPPORTED_OPERATIONS,
    FieldDefinition,
    LocatorHints,
    OperationPolicy,
    SectionDefinition,
    TemplateDefinition,
    TemplateNode,
    make_template_node_id,
    slugify_requirement_id,
)

_ALL_OPS = ["ADD", "UPDATE", "REPLACE", "CONSTRAIN", "DELETE", "LINK"]
_FIELD_OPS = ["UPDATE", "REPLACE", "CONSTRAIN"]
_REVIEW_OPS = ["ADD", "DELETE", "LINK"]


def _field_def(field_id: str, display_name: str, field_type: str) -> FieldDefinition:
    return FieldDefinition(
        field_id=field_id,
        display_name=display_name,
        field_type=field_type,
        required=False,
        editable=True,
        allowed_operations=list(_FIELD_OPS) + list(_REVIEW_OPS),
        content_type="text",
        locator_hints=LocatorHints(strategies=["requirement_id_field", "exact_text"]),
    )


def build_mdsr_template() -> TemplateDefinition:
    fields = [
        _field_def("requirement_id", "요구사항 ID", "requirement_id"),
        _field_def("title", "제목", "title"),
        _field_def("description", "설명", "description"),
        _field_def("purpose", "목적", "paragraph"),
        _field_def("criteria", "기준", "criteria"),
    ]
    # Only fields that exist in MDSR_FIELDS (+ requirement_id as structural)
    fields = [
        f
        for f in fields
        if f.field_id == "requirement_id" or f.field_id in MDSR_FIELDS
    ]
    return TemplateDefinition(
        template_id="mdsr_v1",
        schema_version="template_schema_v1",
        document_type="software_requirements",
        display_name="소프트웨어 요구사항 명세서",
        description="MDSR template adapter (observational).",
        language="ko",
        source_format="docx",
        sections=[
            SectionDefinition(
                section_id="document",
                display_name="문서",
                section_type="document",
                parent_section_id=None,
                order=0,
                required=True,
            ),
            SectionDefinition(
                section_id="requirements",
                display_name="요구사항",
                section_type="requirement_group",
                parent_section_id="document",
                order=1,
                repeatable=True,
                required=True,
                fields=fields,
            ),
        ],
        allowed_operations=list(_ALL_OPS),
        operation_policy=OperationPolicy(
            allowed_operations=list(_ALL_OPS),
            review_required_operations=list(_REVIEW_OPS),
        ),
        metadata={"source_document_alias": "MDSR", "adapter": "mdsr_v1"},
    )


def build_mddr_template() -> TemplateDefinition:
    fields = [
        _field_def("requirement_id", "요구사항 ID", "requirement_id"),
        _field_def("title", "제목", "title"),
        _field_def("design_body", "설계 본문", "description"),
        _field_def("design_condition", "설계 조건", "condition"),
    ]
    fields = [
        f
        for f in fields
        if f.field_id == "requirement_id" or f.field_id in MDDR_FIELDS
    ]
    return TemplateDefinition(
        template_id="mddr_v1",
        schema_version="template_schema_v1",
        document_type="software_design",
        display_name="소프트웨어 설계 명세서",
        description="MDDR template adapter (observational).",
        language="ko",
        source_format="docx",
        sections=[
            SectionDefinition(
                section_id="document",
                display_name="문서",
                section_type="document",
                parent_section_id=None,
                order=0,
                required=True,
            ),
            SectionDefinition(
                section_id="requirements",
                display_name="설계 항목",
                section_type="requirement_group",
                parent_section_id="document",
                order=1,
                repeatable=True,
                required=True,
                fields=fields,
            ),
        ],
        allowed_operations=list(_ALL_OPS),
        operation_policy=OperationPolicy(
            allowed_operations=list(_ALL_OPS),
            review_required_operations=list(_REVIEW_OPS),
        ),
        metadata={"source_document_alias": "MDDR", "adapter": "mddr_v1"},
    )


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(getattr(obj, "__dict__", {}) or {})


def _doc_to_template_id(document: str) -> str | None:
    d = (document or "").strip().upper()
    if d == "MDSR":
        return "mdsr_v1"
    if d == "MDDR":
        return "mddr_v1"
    return None


def _allowed_fields_for_doc(document: str) -> set[str]:
    d = (document or "").strip().upper()
    if d == "MDSR":
        return set(MDSR_FIELDS) | {"requirement_id"}
    if d == "MDDR":
        return set(MDDR_FIELDS) | {"requirement_id"}
    return set()


def ensure_requirement_nodes(
    registry: TemplateRegistry,
    *,
    document: str,
    requirement_id: str,
    field: str,
) -> TemplateNode | None:
    """Create/get deterministic field node for a requirement+field pair."""
    tid = _doc_to_template_id(document)
    if not tid:
        return None
    template = registry.get_template(tid)
    if not template:
        return None
    slug = slugify_requirement_id(requirement_id)
    if not slug:
        return None
    if field not in _allowed_fields_for_doc(document):
        return None

    doc_root = f"{tid}.document"
    group_id = f"{tid}.requirements"
    req_section_id = f"requirements.{slug}"
    parent_id = f"{tid}.{req_section_id}"

    if registry.get_node(doc_root) is None:
        registry.register_node(
            TemplateNode(
                template_node_id=doc_root,
                template_id=tid,
                document_type=template.document_type,
                section_id="document",
                field_id="",
                parent_node_id=None,
                node_type="document",
                display_name=template.display_name,
                order=0,
                source_document=document.upper(),
                allowed_operations=list(template.allowed_operations),
            )
        )
    if registry.get_node(group_id) is None:
        registry.register_node(
            TemplateNode(
                template_node_id=group_id,
                template_id=tid,
                document_type=template.document_type,
                section_id="requirements",
                field_id="",
                parent_node_id=doc_root,
                node_type="requirement_group",
                display_name="requirements",
                order=1,
                source_document=document.upper(),
                allowed_operations=list(template.allowed_operations),
            )
        )
    if registry.get_node(parent_id) is None:
        registry.register_node(
            TemplateNode(
                template_node_id=parent_id,
                template_id=tid,
                document_type=template.document_type,
                section_id=req_section_id,
                field_id="",
                parent_node_id=group_id,
                node_type="requirement",
                display_name=str(requirement_id),
                order=0,
                source_document=document.upper(),
                source_requirement_id=requirement_id,
                source_field="",
                locator_hints=LocatorHints(
                    strategies=["requirement_id_field"],
                    source_requirement_id=requirement_id,
                ),
                allowed_operations=list(template.allowed_operations),
                editable=True,
                mapping_status="MAPPED",
            )
        )

    node_id = make_template_node_id(tid, requirement_slug=slug, field_id=field)
    existing = registry.get_node(node_id)
    if existing:
        return existing

    field_ops = list(_FIELD_OPS) + list(_REVIEW_OPS)
    for sec in template.sections:
        for fld in sec.fields:
            if fld.field_id == field:
                field_ops = list(fld.allowed_operations) or field_ops
                break

    allowed = sorted(_allowed_fields_for_doc(document))
    order = allowed.index(field) if field in allowed else 0
    node = TemplateNode(
        template_node_id=node_id,
        template_id=tid,
        document_type=template.document_type,
        section_id=req_section_id,
        field_id=field,
        parent_node_id=parent_id,
        node_type="field",
        display_name=field,
        order=order,
        source_document=document.upper(),
        source_requirement_id=requirement_id,
        source_field=field,
        locator_hints=LocatorHints(
            strategies=["requirement_id_field", "exact_text"],
            source_requirement_id=requirement_id,
            source_field=field,
        ),
        allowed_operations=field_ops,
        editable=True,
        mapping_status="MAPPED",
    )
    registry.register_node(node)
    return node


def map_artifacts_to_template_nodes(
    registry: TemplateRegistry,
    *,
    review_items: list[Any] | None = None,
    patches: list[Any] | None = None,
    preview_entries: list[Any] | None = None,
    gate_results: list[Any] | None = None,
    activation_items: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Map existing artifacts to template nodes without mutating them."""
    reviews = [_as_dict(x) for x in (review_items or [])]
    # Prefer review items as primary; fall back to gate/preview/patches
    if not reviews:
        for src in (gate_results or []) or (preview_entries or []) or (patches or []):
            d = _as_dict(src)
            reviews.append(
                {
                    "review_item_id": f"CRI-{d.get('patch_id')}",
                    "patch_id": d.get("patch_id"),
                    "atomic_change_id": d.get("atomic_change_id"),
                    "activation_item_id": f"DA-{d.get('patch_id')}",
                    "document": d.get("document"),
                    "requirement_id": d.get("requirement_id"),
                    "field": d.get("field"),
                    "change_type": d.get("operation") or d.get("change_type") or "",
                }
            )

    act_map = {
        str(_as_dict(a).get("patch_id") or ""): _as_dict(a) for a in (activation_items or [])
    }
    patch_map = {
        str(_as_dict(p).get("patch_id") or ""): _as_dict(p) for p in (patches or [])
    }

    mappings: list[dict[str, Any]] = []
    seen_review: set[str] = set()

    for rev in sorted(
        reviews,
        key=lambda r: (
            str(r.get("atomic_change_id") or ""),
            str(r.get("document") or ""),
            str(r.get("requirement_id") or ""),
            str(r.get("field") or ""),
            str(r.get("patch_id") or ""),
        ),
    ):
        rid = str(rev.get("review_item_id") or f"CRI-{rev.get('patch_id')}")
        if rid in seen_review:
            mappings.append(
                {
                    "mapping_id": f"TM-{rid}-DUP",
                    "template_id": None,
                    "template_node_id": None,
                    "patch_id": rev.get("patch_id"),
                    "atomic_change_id": rev.get("atomic_change_id"),
                    "review_item_id": rid,
                    "activation_item_id": rev.get("activation_item_id"),
                    "document": rev.get("document"),
                    "requirement_id": rev.get("requirement_id"),
                    "field": rev.get("field"),
                    "mapping_status": "INVALID",
                    "mapping_method": "unknown",
                    "mapping_reason_codes": ["DUPLICATE_REVIEW_ITEM_MAPPING"],
                    "operation_capability": {},
                }
            )
            continue
        seen_review.add(rid)

        document = str(rev.get("document") or "").strip()
        requirement_id = rev.get("requirement_id")
        field = str(rev.get("field") or "").strip()
        patch_id = str(rev.get("patch_id") or "")
        op = str(
            rev.get("change_type")
            or (patch_map.get(patch_id) or {}).get("operation")
            or ""
        )
        reasons: list[str] = []
        status = "MAPPED"
        method = "requirement_id_field"
        template_id = _doc_to_template_id(document)
        node = None

        # Collect all independent missing causes for requirement-based templates.
        if not document:
            reasons.append("MISSING_DOCUMENT")
        if requirement_id is None or str(requirement_id).strip() == "":
            reasons.append("MISSING_REQUIREMENT_ID")
        if not field:
            reasons.append("MISSING_FIELD")
        elif document and field not in _allowed_fields_for_doc(document):
            reasons.append("UNKNOWN_FIELD")
        elif document and not template_id:
            reasons.append("UNKNOWN_DOCUMENT_TYPE")

        fatal = {
            "MISSING_DOCUMENT",
            "MISSING_REQUIREMENT_ID",
            "UNKNOWN_FIELD",
            "UNKNOWN_DOCUMENT_TYPE",
        }
        if any(r in fatal for r in reasons):
            status = "UNMAPPED"
            method = "unknown"
        elif "MISSING_FIELD" in reasons:
            status = "REVIEW"
            method = "unknown"
        else:
            node = ensure_requirement_nodes(
                registry,
                document=document,
                requirement_id=str(requirement_id),
                field=field,
            )
            if node is None:
                status = "UNMAPPED"
                reasons.append("NODE_CREATE_FAILED")
                method = "unknown"
            else:
                status = "MAPPED"
                method = "explicit_adapter"
                if node.source_document.upper() != document.upper():
                    status = "INVALID"
                    reasons.append("DOCUMENT_MISMATCH")
                if str(node.source_requirement_id) != str(requirement_id):
                    status = "INVALID"
                    reasons.append("REQUIREMENT_MISMATCH")
                if node.source_field != field:
                    status = "INVALID"
                    reasons.append("FIELD_MISMATCH")

        act = act_map.get(patch_id) or {}
        cap = {}
        if op:
            cap = {
                op: {
                    "template_allowed": op in VALID_OPERATIONS
                    and (
                        not template_id
                        or op
                        in (
                            (registry.get_template(template_id).allowed_operations)
                            if template_id and registry.get_template(template_id)
                            else list(VALID_OPERATIONS)
                        )
                    ),
                    "writer_supported": op in WRITER_SUPPORTED_OPERATIONS,
                }
            }

        mappings.append(
            {
                "mapping_id": f"TM-{rid}",
                "template_id": template_id if status in ("MAPPED", "REVIEW") else template_id,
                "template_node_id": node.template_node_id if node else None,
                "patch_id": patch_id,
                "atomic_change_id": rev.get("atomic_change_id"),
                "review_item_id": rid,
                "activation_item_id": rev.get("activation_item_id")
                or act.get("activation_item_id")
                or f"DA-{patch_id}",
                "document": document,
                "requirement_id": requirement_id,
                "field": field,
                "mapping_status": status,
                "mapping_method": method,
                "mapping_reason_codes": reasons,
                "operation": op,
                "operation_capability": cap,
            }
        )

    return mappings
