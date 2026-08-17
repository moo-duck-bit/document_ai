---
name: case-retrieval
description: 새 케이스와 유사한 과거 완성본·필드값 패턴을 검색합니다. form-fill의 few-shot 근거로 사용.
---

# Case Retrieval (유사 케이스 검색)

일반 RAG(문단 검색)가 아니라 **케이스 단위** retrieval.

## 인덱스 구조

각 완성본을 **구조화된 케이스 레코드**로 저장:

```json
{
  "case_id": "case_002",
  "template_id": "contract_service",
  "case_type": "용역",
  "embedding_text": "용역 계약 5천만원 IT개발 주식회사A 주식회사B",
  "field_values": {
    "party_a_name": "주식회사 A",
    "contract_amount": 50000000,
    "purpose_clause": "..."
  },
  "metadata": {
    "amount_bucket": "10M-100M",
    "duration_months": 8,
    "industry": "IT"
  }
}
```

## embedding_text 구성

검색 품질을 위해 concatenation:

```
{case_type} {industry} {party_a} {party_b} {amount_bucket} {purpose 첫 200자}
```

## 검색

```python
def retrieve_similar_cases(
    query_case: dict,
    template_id: str,
    k: int = 3,
) -> list[dict]:
    # 1. metadata filter: same template_id (필수)
    # 2. optional: case_type match
    # 3. dense: embed(query_case.embedding_text)
    # 4. hybrid: BM25 on field_values text
    # 5. rerank: cross-encoder or amount/date proximity
```

## 유사도 시그널

| 시그널 | 가중 |
|--------|------|
| 같은 template_id | 필터 (필수) |
| case_type 일치 | 높음 |
| amount_bucket 근접 | 중 |
| embedding cosine | 중 |
| party industry | 낮 |

## form-fill 연동

반환 시 **전체 field_values** + **원문 snippet** (free_text few-shot용):

```python
{
  "case_id": "case_002",
  "score": 0.87,
  "field_values": {...},
  "snippets": {
    "purpose_clause": "갑은 을에게 ...",
    "special_terms": "..."
  }
}
```

## cold start (완성본 < 3건)

- retrieval skip → `form-fill`은 input.facts + schema defaults만
- 완성본 추가 시 점진적 품질 향상

## 평가

- golden: `(new_case, expected_similar_case_id)` pairs
- metric: Recall@1, Recall@3 among same template

## 구현

- `document-rag` 인프라 재사용 (Chroma collection per template_id)
- collection name: `cases_{template_id}`
