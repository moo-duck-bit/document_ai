---
name: template-learn
description: 빈 양식과 완성본을 분석해 필드 스키마(레이블, 위치, 타입, 매핑)를 추출·학습합니다.
---

# Template Learn (양식·스키마 학습)

빈 양식과 완성 문서 쌍에서 **어떤 필드가 어디에 있는지** 학습합니다.

## 입력

- **빈 양식** (template): placeholders, 빈 칸, `[    ]`, `___`, form fields
- **완성본** (≥1): 동일 양식에 값이 채워진 문서

## 출력

`data/schemas/{template_id}.schema.json`:

```json
{
  "template_id": "contract_service",
  "format": "docx",
  "fields": [
    {
      "field_id": "party_a_name",
      "label": "갑 회사명",
      "type": "string",
      "required": true,
      "location": { "type": "bookmark", "name": "PARTY_A" },
      "examples": ["주식회사 A", "㈜테스트"]
    },
    {
      "field_id": "contract_amount",
      "label": "계약금액",
      "type": "money_krw",
      "required": true,
      "location": { "type": "table", "sheet": 0, "row": 5, "col": 2 }
    },
    {
      "field_id": "purpose_clause",
      "label": "계약 목적",
      "type": "free_text",
      "required": true,
      "location": { "type": "paragraph", "after_heading": "제1조 (목적)" }
    }
  ],
  "conditionals": [
    {
      "if": { "case_type": "용역" },
      "include_sections": ["용역범위", "납품"]
    }
  ]
}
```

## 학습 방법

### 1. DOCX (권장 MVP)

```python
from docx import Document

# Content controls, bookmarks, tables 순 탐색
# 빈 양식 vs 완성본 diff → 값이 들어간 셀/문단 = 필드
```

- **python-docx**: paragraphs, tables, runs
- **양식 필드**: Word Content Control (`w:sdt`) 있으면 ID 직접 사용
- **없으면**: 레이블 텍스트 + 인접 빈 run/셀 heuristic

### 2. PDF 양식

- AcroForm fields (`get_fields()`) 있으면 직접 추출
- 없으면: 레이블 bbox + 빈 영역 OCR 좌표 매칭

### 3. 완성본 N건으로 패턴 강화

- 동일 label → 다른 값 = **variable field**
- 모든 완성본 동일 = **static boilerplate** (생성 시 복사)
- 케이스 타입별 다른 섹션 = **conditional**

## 필드 타입

| type | 검증 |
|------|------|
| string | non-empty |
| date | ISO or YYYY-MM-DD |
| money_krw | 숫자, 천단위 |
| enum | allowed values |
| free_text | LLM 허용 (길이 제한) |
| table_row | 표 행 반복 |

## 정렬(Alignment) 알고리즘

```
for each filled_example:
  parse → blocks[]
align template blocks with filled blocks (sequence + fuzzy label match)
diff(empty, filled) → field candidates
merge across examples → schema.fields
```

## 검증

- [ ] 스키마 필드 수 ≈ 수동 라벨링 필드 수 (±10%)
- [ ] 완성본 1건 replay: schema + values → reconstruct → diff < 5%
- [ ] `document-eval` field-level F1

## 실패 시

- 양식마다 레이아웃 다름 → template_id별 스키마 분리
- HWP → `document-ocr` + 수동 schema 보조
