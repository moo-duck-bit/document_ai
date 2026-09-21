# -*- coding: utf-8 -*-
"""PR-20: Document Structure Mapping Engine orchestration (observational)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.document_parser.docx_parser import parse_docx_file
from document_ai.document_parser.locator_candidates import build_locator_candidates
from document_ai.document_parser.markdown_parser import parse_markdown_file, parse_markdown_text
from document_ai.document_parser.normalization import (
    build_section_tree,
    document_from_object,
    normalize_document,
)
from document_ai.document_parser.structure import DocumentModel, LocatorCandidate
from document_ai.document_parser.validation import validate_document_structure

SAMPLE_MARKDOWN_REPORT = """# 연구 진행 보고서

## 요약

본 보고서는 연구 진행 현황을 요약한다.

## 배경

기존 문서 작성 자동화 수요가 증가하고 있다.

## 목표

변경 검토 패키지의 범용성을 검증한다.

## 방법론

### 접근 방식

정적 Template 기반 매핑

### 데이터 출처

내부 artifact 및 샘플 fixture

| 출처 | 설명 |
| --- | --- |
| artifact | 내부 산출물 |
| fixture | 샘플 데이터 |

## 결과

일반 보고서 Template Node가 생성되었다.

- requirement_id 없이도 Node 구성 가능
- Locator Candidate 생성 가능

## 결론

범용 Template Pack이 기존 Layer와 공존한다.
"""

SAMPLE_MARKDOWN_PROPOSAL = """# 문서 AI 사업 제안서

## 개요

문서 변경 자동화 솔루션을 제안한다.

## 문제 정의

문서 유형별 수동 수정 비용이 크다.

## 제안 솔루션

Template Abstraction + Review Package

1. 분석
2. 구현
3. 검증

## 수행 계획

### 일정

1~4주 단계 수행

## 예산

금액은 별도 합의

## 위험 관리

- Locator 미구현
"""


def compute_document_statistics(
    doc: DocumentModel,
    candidates: list[LocatorCandidate],
) -> dict[str, Any]:
    heading_count = sum(1 for s in doc.sections if s.heading_level > 0)
    return {
        "stage": "document_statistics",
        "document_id": doc.document_id,
        "heading_count": heading_count,
        "section_count": len(doc.sections),
        "paragraph_count": sum(len(s.paragraphs) for s in doc.sections),
        "table_count": sum(len(s.tables) for s in doc.sections),
        "list_count": sum(len(s.lists) for s in doc.sections),
        "candidate_count": len(candidates),
    }


def build_structure_summary(
    docs: list[DocumentModel],
    candidates_by_doc: dict[str, list[LocatorCandidate]],
    validations: list[dict[str, Any]],
) -> dict[str, Any]:
    all_cands = [c for cs in candidates_by_doc.values() for c in cs]
    stats = {
        "heading_count": 0,
        "section_count": 0,
        "paragraph_count": 0,
        "table_count": 0,
        "list_count": 0,
        "candidate_count": len(all_cands),
    }
    for d in docs:
        st = compute_document_statistics(d, candidates_by_doc.get(d.document_id, []))
        for k in (
            "heading_count",
            "section_count",
            "paragraph_count",
            "table_count",
            "list_count",
        ):
            stats[k] += st[k]

    statuses = [str(v.get("status") or "") for v in validations]
    if any(s == "INVALID" for s in statuses):
        validation_status = "INVALID"
    elif any(s == "VALID_WITH_WARNINGS" for s in statuses):
        validation_status = "VALID_WITH_WARNINGS"
    else:
        validation_status = "VALID"

    return {
        "stage": "document_structure_summary",
        "document_count": len(docs),
        **stats,
        "validation_status": validation_status,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": (
            "PR-20 observational structure mapping. "
            "No semantic matching, LLM, or DOCX mutation."
        ),
    }


def map_document_structure(doc: DocumentModel) -> dict[str, Any]:
    """Normalize one document and produce candidates + validation."""
    normalized = normalize_document(doc)
    candidates = build_locator_candidates(normalized)
    validation = validate_document_structure(normalized, candidates=candidates)
    stats = compute_document_statistics(normalized, candidates)
    return {
        "model": normalized,
        "document": normalized.to_dict(),
        "section_tree": build_section_tree(normalized),
        "locator_candidates": candidates,
        "locator_candidates_payload": [c.to_dict() for c in candidates],
        "statistics": stats,
        "validation": validation,
    }


def run_document_structure_mapping_engine(
    *,
    markdown_texts: list[dict[str, Any]] | None = None,
    docx_paths: list[str | Path] | None = None,
    objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run observational structure mapping on sample / provided inputs.

    Default: static markdown samples + PR-19 sample objects (no Scenario DOCX mutation).
    """
    docs: list[DocumentModel] = []

    if markdown_texts is None and docx_paths is None and objects is None:
        from document_ai.template.sample_documents import list_sample_documents

        markdown_texts = [
            {
                "text": SAMPLE_MARKDOWN_REPORT,
                "document_id": "sample_md_general_report_001",
                "document_type": "general_report",
            },
            {
                "text": SAMPLE_MARKDOWN_PROPOSAL,
                "document_id": "sample_md_business_proposal_001",
                "document_type": "business_proposal",
            },
        ]
        objects = list_sample_documents()

    for item in markdown_texts or []:
        docs.append(
            parse_markdown_text(
                str(item.get("text") or ""),
                document_id=str(item.get("document_id") or "md_doc"),
                document_type=str(item.get("document_type") or "unknown"),
                title=item.get("title"),
                metadata=item.get("metadata"),
            )
        )

    for path in docx_paths or []:
        docs.append(parse_docx_file(path))

    for obj in objects or []:
        docs.append(document_from_object(obj))

    results = [map_document_structure(doc) for doc in docs]
    normalized_docs = [r["model"] for r in results]
    candidates_by_doc = {
        r["model"].document_id: r["locator_candidates"] for r in results
    }
    validations = [r["validation"] for r in results]
    summary = build_structure_summary(normalized_docs, candidates_by_doc, validations)

    return {
        "stage": "document_structure_mapping_engine",
        "schema_version": "document_structure_v1",
        "documents": [r["document"] for r in results],
        "section_trees": [r["section_tree"] for r in results],
        "locator_candidates": {
            did: [c.to_dict() for c in cs]
            for did, cs in sorted(candidates_by_doc.items())
        },
        "statistics": {
            "documents": [r["statistics"] for r in results],
            "aggregate": {
                k: summary[k]
                for k in (
                    "heading_count",
                    "section_count",
                    "paragraph_count",
                    "table_count",
                    "list_count",
                    "candidate_count",
                )
            },
        },
        "validation": {
            "stage": "document_validation",
            "documents": validations,
            "status": summary["validation_status"],
        },
        "summary": summary,
        "note": (
            "PR-20 observational Document Structure Mapping Engine. "
            "Does not select Template Nodes, run semantic matching, or mutate DOCX."
        ),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


__all__ = [
    "SAMPLE_MARKDOWN_REPORT",
    "SAMPLE_MARKDOWN_PROPOSAL",
    "compute_document_statistics",
    "build_structure_summary",
    "map_document_structure",
    "run_document_structure_mapping_engine",
    "parse_markdown_text",
    "parse_markdown_file",
    "parse_docx_file",
]
