# -*- coding: utf-8 -*-
"""Reason-code → Korean human-friendly text mapping for pilot review cards."""

from __future__ import annotations

REASON_KO: dict[str, str] = {
    # ec_sw document impact / identifier evidence
    "exact_requirement": "요구사항 식별자가 정확히 일치합니다.",
    "EXACT_IDENTIFIER_MATCH": "요구사항 식별자가 정확히 일치합니다.",
    "NORMALIZED_IDENTIFIER_MATCH": "표기가 다르지만 동일한 요구사항 식별자로 판단됩니다.",
    "CROSS_DOCUMENT_IDENTIFIER_MATCH": "다른 문서에서 참조된 식별자와 연결됩니다.",
    "SEMANTIC_SECTION_MATCH": "문구는 다르지만 의미상 관련된 항목입니다.",
    "semantic_only_review": "정확한 식별자는 없지만 의미상 검토가 필요합니다.",
    "no_semantic_only_patch": "의미 기반 판단만으로는 자동 반영하지 않습니다.",
    "ambiguous_identifier": "식별자가 모호하여 검토가 필요합니다.",
    "malformed_identifier": "식별자 표기가 잘못되었습니다.",
    "malformed_id_only": "식별자 표기가 잘못되어 자동 반영할 수 없습니다.",
    "malformed_id_not_exact": "식별자 표기가 정확하지 않습니다.",
    "malformed_plus_semantic": "식별자 오류와 의미적 유사성이 함께 발견되었습니다.",
    "no_evidence": "변경 근거가 없습니다.",
    "no_substantive_evidence": "실질적인 변경 근거가 없습니다.",
    "role_or_presence_only": "문서가 업로드되었을 뿐, 내용상 근거는 없습니다.",
    "role_or_presence_only_no_role_only_impacted": "역할만으로는 영향 문서로 판단하지 않습니다.",
    "default_unrelated": "변경 요청과 관련이 없는 것으로 판단됩니다.",
    "indirect_or_review_evidence": "간접적인 근거가 있어 사람 검토가 필요합니다.",
    "independent_substantive_evidence": "독립적인 실질 근거가 확인되었습니다.",
    "impacted_requires_substantive_evidence": "영향 판정에는 실질적인 근거가 필요합니다.",
    "RANK_TIER_1": "가장 신뢰도가 높은 최우선 후보입니다.",
    "TIER_1": "가장 신뢰도가 높은 최우선 후보입니다.",
    "STABLE_BASE_EXACT": "안정 식별자 기준으로 정확히 일치합니다.",
    # generic template / structural matching
    "template_section_token_overlap": "요청 문구와 템플릿 섹션 단어가 겹칩니다.",
    "template_section_concept_match": "요청 의미와 템플릿 섹션 주제가 일치합니다.",
    "paragraph_token_overlap": "요청 문구와 문서 문단의 단어가 겹칩니다.",
    "paragraph_concept_match": "요청 의미와 문서 문단 주제가 일치합니다.",
    "no_overlap": "요청과 겹치는 내용이 없습니다.",
    "template_only_hit": "템플릿상으로만 관련이 있으며 실제 문서 근거는 아직 없습니다.",
    # writer / capability gate
    "CONTROLLED_WRITER_DISABLED": "통제된 문서 작성 기능이 비활성화되어 있습니다 (관리자 설정 필요).",
    "EXTERNAL_FEATURE_FLAG_OFF": "외부 활성화 플래그가 꺼져 있습니다.",
    "APPROVAL_NOT_GRANTED": "명시적인 승인(APPROVED)이 없습니다.",
    "FINGERPRINT_INVALID": "원본 문서 지문(체크섬)이 일치하지 않습니다.",
    "SPAN_KIND_NOT_SOURCE_ABSOLUTE": "패치 위치 정보가 안전 기준을 충족하지 않습니다.",
    "CONTRACT_NOT_READY_FOR_REVIEW": "패치 계약이 아직 검토 준비 상태가 아닙니다.",
    "OPERATION_UNSUPPORTED": "지원되지 않는 작업 유형입니다.",
    "WRITER_ADAPTER_UNSUPPORTED": "지원되지 않는 문서 작성 어댑터입니다.",
    "OPERATION_ADAPTER_MISMATCH": "작업 유형과 어댑터가 일치하지 않습니다.",
    "ACTIVATION_ALLOWED": "모든 안전 조건을 충족하여 실행이 허용됩니다.",
    "ACTIVATION_BLOCKED": "안전 조건 미충족으로 실행이 차단되었습니다.",
    # pilot-local writer gates
    "NOT_APPROVED": "승인된 항목이 없습니다.",
    "WRITE_DISABLED": "쓰기 기능이 비활성화되어 있습니다 (--writer-enabled 필요).",
    "ROUTING_NOT_CONFIRMED": "문서 종류(라우팅)가 아직 확정되지 않았습니다.",
    "FINGERPRINT_MISMATCH": "업로드 시점과 현재 문서 내용이 다릅니다.",
    "COPY_SOURCE_COLLISION": "사본 경로가 원본 경로와 동일하여 차단되었습니다.",
    "CONTROLLED_WRITER_ENV_DISABLED": "서버 환경변수(CONTROLLED_WRITER_ENABLED)가 꺼져 있습니다.",
    # identity
    "REPORT_PROPOSAL_AMBIGUOUS": "보고서인지 제안서인지 모호합니다. 확인이 필요합니다.",
    "MDSR_MDDR_AMBIGUOUS": "요구사항명세서와 설계명세서 중 어느 것인지 모호합니다.",
    "USER_HINT_CONTENT_CONFLICT": "사용자가 지정한 문서 종류와 실제 내용이 다릅니다.",
    "CROSS_PACK_AMBIGUOUS": "여러 문서군에 걸쳐 모호합니다. 확인이 필요합니다.",
    # workflow writer statuses
    "SKIPPED_NOT_APPROVED": "승인되지 않아 건너뛰었습니다.",
    "SKIPPED_WRITE_DISABLED": "쓰기 기능이 꺼져 있어 건너뛰었습니다.",
    "BLOCKED_ENGINE_GATE": "엔진 안전 게이트에 의해 차단되었습니다.",
    "BLOCKED_REVIEW_ITEM": "사람 검토가 필요한 항목이라 차단되었습니다.",
    "SKIPPED_REVIEW_ITEM": "검토 대기 항목이라 건너뛰었습니다.",
}

_FALLBACK_TEMPLATE = "검토가 필요한 항목입니다 (사유 코드: {code})."


def translate_code(code: str) -> str:
    if not code:
        return ""
    if code in REASON_KO:
        return REASON_KO[code]
    upper = code.upper()
    if upper in REASON_KO:
        return REASON_KO[upper]
    lower = code.lower()
    if lower in REASON_KO:
        return REASON_KO[lower]
    return _FALLBACK_TEMPLATE.format(code=code)


def translate_codes(codes: list[str] | None, *, sep: str = " ") -> str:
    if not codes:
        return "구체적인 사유 정보가 없습니다."
    seen: list[str] = []
    for c in codes:
        text = translate_code(str(c))
        if text and text not in seen:
            seen.append(text)
    return sep.join(seen)
