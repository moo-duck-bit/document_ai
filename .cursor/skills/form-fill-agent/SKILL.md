---
name: form-fill-agent
description: 완성된 문서로부터 양식·필드·작성 패턴을 학습하고, 빈 양식과 새 케이스 정보로 문서를 자동 작성하는 에이전트. 최종 목표의 핵심 오케스트레이터.
---

# Form Fill Agent (양식 자동 작성 에이전트)

**최종 목표**: 완성 문서(ground truth)를 학습해, 빈 양식 + 새 케이스 입력만으로 **유사한 완성 문서**를 자동 생성.

## 핵심 개념

| 용어 | 설명 |
|------|------|
| **양식(Template)** | 빈 필드·레이블·표 구조가 정의된 문서 |
| **완성본(Filled Example)** | 실제 케이스에 맞게 작성된 문서 |
| **필드 스키마(Schema)** | 양식에서 추출한 필드 ID, 레이블, 타입, 제약 |
| **케이스(Case)** | 한 건의 작성 맥락 (입력 데이터 + 메타) |
| **유사 케이스** | 새 케이스와 조건·유형이 비슷한 과거 완성본 |

## 전체 파이프라인

```
[학습 Phase — 오프라인]
  완성본 + (선택) 대응 양식
    → parse/OCR
    → template-learn (스키마·필드 매핑)
    → case-index (케이스별 구조화 저장 + 임베딩)

[작성 Phase — 런타임]
  채팅/참고 DOCX → case-intake → input.json (confirmed)
  빈 양식 + input.json
    → template-learn (필드 목록)
    → case-retrieval (유사 완성본)
    → form-fill → document-render
```

## 하위 스킬 라우팅

| 단계 | 스킬 |
|------|------|
| PDF/스캔 파싱 | `pdf-parse`, `document-ocr` |
| **케이스 입력** | **`case-intake`** |
| 양식·필드 구조 학습 | `template-learn` |
| 유사 케이스 검색 | `case-retrieval` (document-rag 확장) |
| 필드값 생성 | `form-fill` |
| 파일 출력 | `document-render` |
| 품질 검증 | `document-eval` |

## Case 입력 형식 (권장)

`data/cases/{case_id}/input.json`:

```json
{
  "case_id": "2024-001",
  "case_type": "계약서_용역",
  "facts": {
    "갑_회사명": "주식회사 A",
    "을_회사명": "주식회사 B",
    "계약금액": "50000000",
    "계약기간_시작": "2024-04-01",
    "계약기간_종료": "2024-12-31"
  },
  "notes": "표준 용역 계약, VAT 별도"
}
```

`facts` 키는 스키마 필드 ID와 매칭. 부족한 필드는 유사 케이스 + LLM으로 보완.

## 학습 데이터 구조

```
data/
├── templates/
│   └── contract_service.docx      # 빈 양식
├── examples/
│   └── contract_service/
│       ├── case_001_filled.docx   # 완성본
│       ├── case_002_filled.docx
│       └── ...
├── schemas/
│   └── contract_service.schema.json  # template-learn 출력
└── cases/
    └── {case_id}/
        ├── input.json
        └── output.docx
```

## form-fill 추론 전략 (우선순위)

1. **직접 매핑**: `input.facts`에 값 있으면 그대로 사용
2. **유사 케이스 복사·수정**: retrieval top-1~3 완성본에서 필드값 참고, diff 적용
3. **규칙 엔진**: 날짜 형식, 금액 한글 변환, 조건부 문단 (if case_type)
4. **LLM 생성**: free-text 문단(목적, 특약) — **반드시** 유사 케이스를 few-shot으로 제공

**Hallucination 방지**: 고정 필드(금액, 날짜, 이름)는 LLM 생성 금지 → facts 또는 유사 케이스에서만.

## API (목표)

```
POST /learn/template     — 양식 + 완성본 N건 → schema 저장
POST /generate           — { template_id, case_input } → output file
GET  /schemas/{id}       — 필드 스키마 조회
POST /validate           — 생성본 vs 기대값 필드 비교
```

## 시작 전 사용자에게 확인

1. **문서 포맷**: DOCX / HWP / PDF / 혼합?
2. **도메인**: 계약서, 보고서, 신청서, 의료/법률 등?
3. **케이스 입력**: **채팅 + (선택) 참고 DOCX** → `input.json` 확정 (권장). JSON/API는 테스트용.
4. **완성본 수**: 유형당 최소 3–5건 (few-shot 품질)
5. **출력**: Word 편집 가능 vs PDF 최종본?

## MVP 순서 (권장)

1. DOCX 빈 양식 1종 + 완성본 3건
2. `template-learn` → schema.json
3. `case-retrieval` → 유사 케이스 1건 retrieval
4. `form-fill` → python-docx로 필드 채우기
5. `document-eval` → 필드별 exact match

## 완료 기준 (최종 목표)

- [ ] 새 case_type 추가 시 완성본만 추가하면 동작 (재학습 최소)
- [ ] 빈 양식 + input.json → 편집 가능한 출력 문서
- [ ] 필드 정확도 ≥ 90% (도메인별 golden set)
- [ ] 유사하지 않은 케이스에서도 합리적 초안 (human-in-the-loop)
