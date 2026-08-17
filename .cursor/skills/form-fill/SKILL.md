---
name: form-fill
description: 빈 양식, 필드 스키마, 새 케이스 입력, 유사 완성본을 바탕으로 각 필드값을 추론하고 문서 초안을 생성합니다.
---

# Form Fill (필드값 추론·작성)

스키마 + 케이스 입력 + 유사 완성본 → **필드별 값** → 렌더러로 넘김.

## 입력

```python
@dataclass
class FillRequest:
    template_id: str
    schema: dict              # template-learn 출력
    case_input: dict          # input.json
    similar_cases: list[dict] # case-retrieval 출력 (structured fields)
```

## 출력

```python
@dataclass
class FillResult:
    field_values: dict[str, Any]   # field_id → value
    confidence: dict[str, float]   # field_id → 0~1
    sources: dict[str, str]        # field_id → "input" | "case_002" | "llm"
    warnings: list[str]
```

## 필드 채우기 우선순위

```
1. case_input.facts[field_id]     → confidence 1.0
2. rule_engine(field, case_input)   → 날짜/금액 포맷, derived
3. similar_cases[0][field_id]     → 유사 케이스 복사 (타입·케이스 유사도 확인)
4. similar_cases[1..k] majority   → 다수결 (enum)
5. LLM (free_text only)           → few-shot: similar case snippets
```

## LLM 프롬프트 (free_text 전용)

```text
당신은 {case_type} 문서 작성 assistant입니다.
아래 유사 사례의 작성 스타일을 따르되, 새 사실만 반영하세요.
금액·날짜·회사명은 제공된 facts를 그대로 사용하고 변경하지 마세요.

## 유사 사례 (few-shot)
{similar_case_excerpts}

## 이번 케이스 facts
{case_input.facts}

## 작성할 필드
- 필드: {field.label}
- 설명: {field.description}

## 출력
해당 필드에 들어갈 문단만 출력하세요.
```

## 규칙 엔진 예시

```python
def format_money_krw(amount: int) -> str:
    return f"{amount:,}원"

def format_money_korean(amount: int) -> str:
    # 금오천만원정 — domain library or table
    ...

def derive_end_date(start: str, months: int) -> str:
    ...
```

## 조건부 섹션

`schema.conditionals` 평가:
- `case_type == "용역"` → 용역 조항 포함
- `contract_amount > 100_000_000` → 특약 블록 추가

## 검증 (fill 직후)

- required 필드 non-empty
- type 검증 (date parse, money numeric)
- cross-field: `end_date >= start_date`
- confidence < 0.7 → `warnings` + human review flag

## human-in-the-loop

```json
{
  "needs_review": ["purpose_clause", "special_terms"],
  "draft_path": "data/cases/2024-001/output_draft.docx"
}
```

저신뢰 필드만 편집 UI/API로 노출 (Phase 2+).

## 다음 단계

`FillResult` → `document-render` 스킬
