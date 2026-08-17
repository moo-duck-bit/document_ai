---
name: case-intake
description: 새 케이스 정보를 채팅·참고 문서·JSON에서 수집해 input.json(facts)으로 구조화합니다. form-fill 전 단계.
---

# Case Intake (케이스 입력)

form-fill **이전** 단계. 다양한 입력 채널을 **`input.json` 하나**로 통합.

## 권장 아키텍처 (3채널 → 1 canonical)

```
┌─────────────┐   ┌──────────────────┐   ┌─────────────┐
│  채팅        │   │  참고 문서 업로드   │   │  JSON 직접   │
│  (대화형)    │   │  (DOCX/PDF/메일)  │   │  (API/CLI)  │
└──────┬──────┘   └────────┬─────────┘   └──────┬──────┘
       │                   │                    │
       └───────────────────┼────────────────────┘
                           ▼
              ┌────────────────────────┐
              │  intake/extract        │
              │  (LLM + schema guide)  │
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │  input.json            │  ← form-fill의 단일 입력
              │  + 사용자 확인         │
              └────────────────────────┘
```

**왜 JSON을 중심에 두는가**
- form-fill·eval·API 재현성
- 채팅/문서는 **입력 UI**일 뿐, 저장 형식은 동일
- human-in-the-loop: 추출 후 사용자 확인 → 확정

## input.json 스키마

```json
{
  "case_id": "2026-001",
  "template_id": "proposal_it",
  "case_type": "제안서",
  "document_subtype": "IT용역",
  "facts": {
    "client_name": "○○공공기관",
    "project_title": "AI 문서 자동화 구축",
    "budget_krw": 80000000,
    "period_start": "2026-07-01",
    "period_end": "2026-12-31",
    "contact_name": "홍길동",
    "contact_email": "hong@example.com"
  },
  "free_text_hints": {
    "background": "기존 수기 보고서로 인한 지연...",
    "scope_summary": "RAG + 양식 자동작성 PoC"
  },
  "source_documents": [
    "data/intake/2026-001/rfp_summary.docx"
  ],
  "intake_channel": "chat+document",
  "confirmed": false,
  "confirmed_at": null
}
```

- **`facts`**: 스키마 필드와 1:1 매핑 (구조화, form-fill 우선 사용)
- **`free_text_hints`**: 채팅/문서에서 뽑은 서술형 힌트 (LLM free_text 필드용)
- **`confirmed`**: 사용자 승인 전에는 form-fill 실행 금지

## 채널 1: 채팅 (권장 — Primary UX)

### 흐름

1. Agent: template_id·case_type 확인
2. 스키마 기반 **필수 필드 checklist** 질문 (missing fields만)
3. 사용자 자유 서술 허용 → LLM이 facts + free_text_hints 추출
4. **요약 카드** 제시 → "이대로 진행할까요?"
5. `confirmed: true` → `data/cases/{case_id}/input.json` 저장

### 질문 전략

- required 필드 먼저 (회사명, 기간, 금액)
- optional / free_text는 "추가로 알려주실 내용?"
- 한 번에 3개 이하 질문 ( interview 스킬 참고)

### 추출 프롬프트 (structured output)

```text
스키마 필드 목록: {schema.fields}
사용자 메시지: {user_message}
대화 이력: {history}

JSON만 출력:
{
  "facts": { ... },
  "free_text_hints": { ... },
  "missing_required": ["field_id", ...],
  "clarifying_questions": ["...", ...]
}
```

## 채널 2: 참고 문서 추출 (권장 — Secondary)

### 적합한 참고 문서

| 유형 | 예시 | 추출 가능 |
|------|------|-----------|
| RFP/공고 | 입찰공고 DOCX | 예산, 기간, 요구사항 |
| 이전 제안서 | 과거 filled DOCX | 스타일·구조 참고 (case-retrieval) |
| 회의록/메일 | DOCX/PDF | facts + free_text_hints |
| Excel 견적 | xlsx | 금액, 항목 |

### 흐름

1. `pdf-parse` / python-docx로 텍스트 추출
2. `template_id`의 schema.fields 기준 **entity extraction**
3. 기존 `input.json`과 merge (채팅 값 우선 또는 사용자 선택)
4. 충돌 필드 → 사용자에게 선택지 제시

### 우선순위 (merge)

```
explicit chat answer  >  structured table in doc  >  LLM extraction from doc
```

## 채널 3: JSON / API (Power user)

```
POST /cases
{ "template_id": "...", "facts": { ... } }
```

CLI, 배치, 테스트용.

## template_id별 facts 프로필

### proposal_* (제안서)

```json
{
  "client_name": "string",
  "project_title": "string",
  "budget_krw": "number",
  "period_start": "date",
  "period_end": "date",
  "delivery_scope": "string"
}
```

### report_* (보고서)

```json
{
  "report_title": "string",
  "author_org": "string",
  "report_period": "string",
  "department": "string"
}
```

### application_* (신청서)

```json
{
  "applicant_name": "string",
  "applicant_id": "string",
  "application_date": "date",
  "program_name": "string"
}
```

공통 필드는 `schemas/_common.fields.json`에서 reuse.

## UX 권장 (최종)

| 사용자 | 추천 |
|--------|------|
| 일반 사용자 | **채팅** + (선택) 참고 DOCX 1개 첨부 |
| 반복 작성 | 이전 **완성본 유사 검색** + 채팅으로 diff만 |
| 개발/테스트 | JSON 직접 |

**MVP**: 채팅 → input.json → 사용자 확인 → form-fill  
**v2**: DOCX drag-drop → 자동 merge → 확인

## 검증

- [ ] required 필드 모두 채워질 때까지 `confirmed` false
- [ ] extraction confidence < 0.8 → 해당 필드 highlight
- [ ] intake 로그: `data/cases/{id}/intake_log.json`

## 다음 단계

`confirmed: true` input.json → `form-fill` → `document-render`
