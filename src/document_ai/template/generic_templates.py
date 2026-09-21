# -*- coding: utf-8 -*-
"""PR-19: Generic document templates (report / proposal)."""

from __future__ import annotations

from document_ai.template.schema import (
    WRITER_SUPPORTED_OPERATIONS,
    FieldDefinition,
    LocatorHints,
    OperationPolicy,
    SectionDefinition,
    TemplateDefinition,
    TemplateNode,
)

_ALL_OPS = ["ADD", "UPDATE", "REPLACE", "CONSTRAIN", "DELETE", "LINK"]
_TITLE_OPS = ["UPDATE", "REPLACE"]
_BODY_OPS = ["ADD", "UPDATE", "REPLACE", "CONSTRAIN", "DELETE"]
_REF_OPS = ["ADD", "UPDATE", "DELETE", "LINK"]
_BUDGET_OPS = ["ADD", "UPDATE", "REPLACE", "DELETE"]


def _fld(
    field_id: str,
    display_name: str,
    *,
    field_type: str = "custom",
    content_type: str = "text",
    ops: list[str] | None = None,
    heading_path: list[str] | None = None,
) -> FieldDefinition:
    return FieldDefinition(
        field_id=field_id,
        display_name=display_name,
        field_type=field_type,
        required=False,
        editable=True,
        allowed_operations=list(ops or _BODY_OPS),
        content_type=content_type,
        locator_hints=LocatorHints(
            strategies=["heading_path", "field_label", "exact_text"],
            source_field=field_id,
            heading_path=list(heading_path or []),
            section_id=None,
            field_label=display_name,
            exact_text=None,
        ),
    )


def _sec(
    section_id: str,
    display_name: str,
    *,
    order: int,
    fields: list[FieldDefinition],
    parent: str | None = "document",
    section_type: str = "section",
) -> SectionDefinition:
    return SectionDefinition(
        section_id=section_id,
        display_name=display_name,
        section_type=section_type,
        parent_section_id=parent,
        order=order,
        repeatable=False,
        required=False,
        fields=fields,
    )


def build_general_report_template() -> TemplateDefinition:
    sections = [
        SectionDefinition(
            section_id="document",
            display_name="문서",
            section_type="document",
            parent_section_id=None,
            order=0,
            required=True,
            fields=[_fld("title", "문서 제목", field_type="title", ops=_TITLE_OPS)],
        ),
        _sec(
            "executive_summary",
            "요약",
            order=1,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["요약"]),
                _fld("body", "본문", field_type="body", heading_path=["요약"]),
            ],
        ),
        _sec(
            "background",
            "배경",
            order=2,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["배경"]),
                _fld("body", "본문", field_type="body", heading_path=["배경"]),
            ],
        ),
        _sec(
            "objectives",
            "목표",
            order=3,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["목표"]),
                _fld("body", "본문", field_type="body", heading_path=["목표"]),
            ],
        ),
        _sec(
            "methodology",
            "방법론",
            order=4,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["방법론"]),
                _fld("approach", "접근 방식", field_type="approach", heading_path=["방법론", "접근 방식"]),
                _fld(
                    "data_sources",
                    "데이터 출처",
                    field_type="data_sources",
                    heading_path=["방법론", "데이터 출처"],
                ),
                _fld(
                    "limitations",
                    "한계",
                    field_type="limitations",
                    heading_path=["방법론", "한계"],
                ),
            ],
        ),
        _sec(
            "results",
            "결과",
            order=5,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["결과"]),
                _fld("body", "본문", field_type="body", heading_path=["결과"]),
                _fld(
                    "key_findings",
                    "핵심 발견",
                    field_type="key_findings",
                    content_type="list",
                    heading_path=["결과", "핵심 발견"],
                ),
                _fld("tables", "표", field_type="table", content_type="table", heading_path=["결과"]),
            ],
        ),
        _sec(
            "discussion",
            "논의",
            order=6,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["논의"]),
                _fld("body", "본문", field_type="body", heading_path=["논의"]),
            ],
        ),
        _sec(
            "conclusion",
            "결론",
            order=7,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["결론"]),
                _fld("body", "본문", field_type="body", heading_path=["결론"]),
                _fld(
                    "recommendations",
                    "권고사항",
                    field_type="recommendations",
                    content_type="list",
                    heading_path=["결론", "권고사항"],
                ),
            ],
        ),
        _sec(
            "schedule",
            "일정",
            order=8,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["일정"]),
                _fld("body", "본문", field_type="schedule", heading_path=["일정"]),
                _fld(
                    "timeline",
                    "타임라인",
                    field_type="schedule",
                    heading_path=["일정", "타임라인"],
                ),
                _fld(
                    "milestones",
                    "마일스톤",
                    field_type="list",
                    content_type="list",
                    heading_path=["일정", "마일스톤"],
                ),
                _fld(
                    "tables",
                    "일정표",
                    field_type="table",
                    content_type="table",
                    heading_path=["일정", "일정표"],
                ),
            ],
        ),
        _sec(
            "references",
            "참고문헌",
            order=9,
            fields=[
                _fld(
                    "entries",
                    "항목",
                    field_type="references",
                    content_type="reference",
                    ops=_REF_OPS,
                    heading_path=["참고문헌"],
                )
            ],
        ),
        _sec(
            "appendix",
            "부록",
            order=10,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["부록"]),
                _fld("body", "본문", field_type="body", heading_path=["부록"]),
                _fld(
                    "attachments",
                    "첨부",
                    field_type="attachments",
                    content_type="attachment",
                    ops=_REF_OPS,
                    heading_path=["부록", "첨부"],
                ),
            ],
        ),
    ]
    return TemplateDefinition(
        template_id="general_report_v1",
        schema_version="template_schema_v1",
        document_type="general_report",
        display_name="일반 보고서",
        description="Generic report template (observational).",
        language="ko",
        source_format="docx",
        sections=sections,
        allowed_operations=list(_ALL_OPS),
        operation_policy=OperationPolicy(
            allowed_operations=list(_ALL_OPS),
            review_required_operations=["ADD", "DELETE", "LINK"],
        ),
        metadata={"family": "generic", "requirement_id_required": False},
    )


def build_business_proposal_template() -> TemplateDefinition:
    sections = [
        SectionDefinition(
            section_id="document",
            display_name="문서",
            section_type="document",
            parent_section_id=None,
            order=0,
            required=True,
            fields=[_fld("title", "문서 제목", field_type="title", ops=_TITLE_OPS)],
        ),
        _sec(
            "overview",
            "개요",
            order=1,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["개요"]),
                _fld("body", "본문", field_type="body", heading_path=["개요"]),
            ],
        ),
        _sec(
            "problem_statement",
            "문제 정의",
            order=2,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["문제 정의"]),
                _fld("body", "본문", field_type="body", heading_path=["문제 정의"]),
            ],
        ),
        _sec(
            "proposed_solution",
            "제안 솔루션",
            order=3,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["제안 솔루션"]),
                _fld("body", "본문", field_type="body", heading_path=["제안 솔루션"]),
                _fld(
                    "differentiators",
                    "차별점",
                    field_type="list",
                    content_type="list",
                    heading_path=["제안 솔루션", "차별점"],
                ),
            ],
        ),
        _sec(
            "scope",
            "범위",
            order=4,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["범위"]),
                _fld("body", "본문", field_type="body", heading_path=["범위"]),
            ],
        ),
        _sec(
            "execution_plan",
            "수행 계획",
            order=5,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["수행 계획"]),
                _fld(
                    "phases",
                    "단계",
                    field_type="list",
                    content_type="list",
                    heading_path=["수행 계획", "단계"],
                ),
                _fld(
                    "deliverables",
                    "산출물",
                    field_type="list",
                    content_type="list",
                    heading_path=["수행 계획", "산출물"],
                ),
                _fld(
                    "schedule",
                    "일정",
                    field_type="schedule",
                    content_type="list",
                    heading_path=["수행 계획", "일정"],
                ),
            ],
        ),
        _sec(
            "schedule",
            "일정",
            order=6,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["일정"]),
                _fld("body", "본문", field_type="schedule", heading_path=["일정"]),
            ],
        ),
        _sec(
            "budget",
            "예산",
            order=7,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["예산"]),
                _fld(
                    "summary",
                    "요약",
                    field_type="summary",
                    content_type="currency",
                    ops=_BUDGET_OPS,
                    heading_path=["예산", "요약"],
                ),
                _fld(
                    "items",
                    "항목",
                    field_type="budget_items",
                    content_type="table",
                    ops=_BUDGET_OPS,
                    heading_path=["예산", "항목"],
                ),
                _fld(
                    "assumptions",
                    "가정",
                    field_type="list",
                    content_type="list",
                    heading_path=["예산", "가정"],
                ),
            ],
        ),
        _sec(
            "expected_outcomes",
            "기대 효과",
            order=8,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["기대 효과"]),
                _fld("body", "본문", field_type="body", heading_path=["기대 효과"]),
            ],
        ),
        _sec(
            "risks",
            "위험 관리",
            order=9,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["위험 관리"]),
                _fld(
                    "items",
                    "위험 항목",
                    field_type="list_items",
                    content_type="list",
                    heading_path=["위험 관리"],
                ),
                _fld(
                    "mitigation",
                    "완화 방안",
                    field_type="list",
                    content_type="list",
                    heading_path=["위험 관리", "완화 방안"],
                ),
            ],
        ),
        _sec(
            "organization",
            "조직",
            order=10,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["조직"]),
                _fld("body", "본문", field_type="body", heading_path=["조직"]),
            ],
        ),
        _sec(
            "appendix",
            "부록",
            order=11,
            fields=[
                _fld("title", "제목", field_type="title", ops=_TITLE_OPS, heading_path=["부록"]),
                _fld("body", "본문", field_type="body", heading_path=["부록"]),
            ],
        ),
    ]
    return TemplateDefinition(
        template_id="business_proposal_v1",
        schema_version="template_schema_v1",
        document_type="business_proposal",
        display_name="사업 제안서",
        description="Generic business proposal template (observational).",
        language="ko",
        source_format="docx",
        sections=sections,
        allowed_operations=list(_ALL_OPS),
        operation_policy=OperationPolicy(
            allowed_operations=list(_ALL_OPS),
            review_required_operations=["ADD", "DELETE", "LINK"],
        ),
        metadata={"family": "generic", "requirement_id_required": False},
    )


def make_generic_node_id(template_id: str, section_id: str, field_id: str) -> str:
    """Deterministic generic node id (no requirement_id)."""
    return f"{template_id}.{section_id}.{field_id}"


def build_static_nodes_for_template(template: TemplateDefinition) -> list[TemplateNode]:
    """Create static section/field nodes for a generic template."""
    nodes: list[TemplateNode] = []
    doc_id = f"{template.template_id}.document"
    nodes.append(
        TemplateNode(
            template_node_id=doc_id,
            template_id=template.template_id,
            document_type=template.document_type,
            section_id="document",
            field_id="",
            parent_node_id=None,
            node_type="document",
            display_name=template.display_name,
            order=0,
            source_document=template.document_type,
            source_requirement_id=None,
            source_field="",
            allowed_operations=list(template.allowed_operations),
            editable=True,
            mapping_status="MAPPED",
            metadata={"requirement_id_optional": True},
        )
    )
    for sec in sorted(template.sections, key=lambda s: s.order):
        if sec.section_id == "document":
            for i, fld in enumerate(sec.fields):
                nid = make_generic_node_id(template.template_id, "document", fld.field_id)
                hints = fld.locator_hints
                hints.section_id = "document"
                nodes.append(
                    TemplateNode(
                        template_node_id=nid,
                        template_id=template.template_id,
                        document_type=template.document_type,
                        section_id="document",
                        field_id=fld.field_id,
                        parent_node_id=doc_id,
                        node_type="field",
                        display_name=fld.display_name,
                        order=i,
                        source_document=template.document_type,
                        source_requirement_id=None,
                        source_field=fld.field_id,
                        locator_hints=hints,
                        allowed_operations=list(fld.allowed_operations),
                        editable=fld.editable,
                        mapping_status="MAPPED",
                        metadata={"requirement_id_optional": True},
                    )
                )
            continue

        sec_node_id = f"{template.template_id}.{sec.section_id}"
        parent = doc_id
        if sec.parent_section_id and sec.parent_section_id != "document":
            parent = f"{template.template_id}.{sec.parent_section_id}"
        nodes.append(
            TemplateNode(
                template_node_id=sec_node_id,
                template_id=template.template_id,
                document_type=template.document_type,
                section_id=sec.section_id,
                field_id="",
                parent_node_id=parent,
                node_type=sec.section_type,
                display_name=sec.display_name,
                order=sec.order,
                source_document=template.document_type,
                source_requirement_id=None,
                source_field="",
                allowed_operations=list(template.allowed_operations),
                editable=True,
                mapping_status="MAPPED",
                metadata={"requirement_id_optional": True},
            )
        )
        for i, fld in enumerate(sec.fields):
            nid = make_generic_node_id(template.template_id, sec.section_id, fld.field_id)
            hints = fld.locator_hints
            hints.section_id = sec.section_id
            nodes.append(
                TemplateNode(
                    template_node_id=nid,
                    template_id=template.template_id,
                    document_type=template.document_type,
                    section_id=sec.section_id,
                    field_id=fld.field_id,
                    parent_node_id=sec_node_id,
                    node_type="field",
                    display_name=fld.display_name,
                    order=i,
                    source_document=template.document_type,
                    source_requirement_id=None,
                    source_field=fld.field_id,
                    locator_hints=hints,
                    allowed_operations=list(fld.allowed_operations),
                    editable=fld.editable,
                    mapping_status="MAPPED",
                    metadata={"requirement_id_optional": True},
                )
            )
    return nodes


def operation_capability_for(op: str, template: TemplateDefinition) -> dict[str, bool]:
    return {
        "template_allowed": op in template.allowed_operations,
        "writer_supported": op in WRITER_SUPPORTED_OPERATIONS,
    }
