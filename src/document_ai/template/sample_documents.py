# -*- coding: utf-8 -*-
"""PR-19: Static sample generic documents (fixtures only)."""

from __future__ import annotations

from typing import Any


def build_sample_general_report_001() -> dict[str, Any]:
    return {
        "sample_document_id": "sample_general_report_001",
        "template_id": "general_report_v1",
        "document_type": "general_report",
        "title": "연구 진행 보고서",
        "sections": {
            "executive_summary": {
                "title": "요약",
                "body": "본 보고서는 연구 진행 현황을 요약한다.",
            },
            "background": {
                "title": "배경",
                "body": "기존 문서 작성 자동화 수요가 증가하고 있다.",
            },
            "objectives": {
                "title": "목표",
                "body": "변경 검토 패키지의 범용성을 검증한다.",
            },
            "methodology": {
                "title": "방법론",
                "approach": "정적 Template 기반 매핑",
                "data_sources": "내부 artifact 및 샘플 fixture",
                "limitations": "실제 DOCX 파싱은 포함하지 않음",
            },
            "results": {
                "title": "결과",
                "body": "일반 보고서 Template Node가 생성되었다.",
                "key_findings": ["requirement_id 없이도 Node 구성 가능"],
                "tables": [],
            },
            "conclusion": {
                "title": "결론",
                "body": "범용 Template Pack이 기존 Layer와 공존한다.",
                "recommendations": ["후속 PR에서 Markdown/DOCX mapping 확장"],
            },
        },
        "note": "Static sample — does not modify Scenario-001.",
    }


def build_sample_business_proposal_001() -> dict[str, Any]:
    return {
        "sample_document_id": "sample_business_proposal_001",
        "template_id": "business_proposal_v1",
        "document_type": "business_proposal",
        "title": "문서 AI 사업 제안서",
        "sections": {
            "overview": {
                "title": "개요",
                "body": "문서 변경 자동화 솔루션을 제안한다.",
            },
            "problem_statement": {
                "title": "문제 정의",
                "body": "문서 유형별 수동 수정 비용이 크다.",
            },
            "proposed_solution": {
                "title": "제안 솔루션",
                "body": "Template Abstraction + Review Package",
                "differentiators": ["문서 유형 비종속", "PASS-only DOCX activation"],
            },
            "execution_plan": {
                "title": "수행 계획",
                "phases": ["분석", "구현", "검증"],
                "deliverables": ["Template Pack", "Mapping Artifact"],
                "schedule": "1~4주 단계 수행",
            },
            "budget": {
                "title": "예산",
                "summary": "(금액 미기재)",
                "items": [],
                "assumptions": ["통화 값 자동 생성 없음"],
            },
            "expected_outcomes": {
                "title": "기대 효과",
                "body": "다양한 문서 유형에 동일 Pipeline 적용",
            },
            "risks": {
                "title": "위험 관리",
                "items": ["Locator 미구현"],
                "mitigation": ["후속 PR에서 heading_path 검색"],
            },
        },
        "note": "Static sample — does not modify Scenario-001.",
    }


def list_sample_documents() -> list[dict[str, Any]]:
    return [
        build_sample_general_report_001(),
        build_sample_business_proposal_001(),
    ]
