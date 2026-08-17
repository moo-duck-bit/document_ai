---
name: document-eval
description: Document AI 파이프라인 품질 평가. 파싱/OCR/RAG 정확도, 리콜, latency, 골든 QA 셋 관리.
---

# Document AI Evaluation

파싱·OCR·청킹·RAG 각 단계와 end-to-end 품질을 측정합니다.

## 평가 레벨

| 레벨 | 대상 | 지표 |
|------|------|------|
| **L1 Parse** | PDF/OCR 출력 | CER, 필드 추출 F1 |
| **L2 Chunk** | 청크 품질 | 절단율, 평균 길이, 주제 일관성 |
| **L3 Retrieval** | 검색 | Recall@k, MRR, nDCG |
| **L4 Generation** | RAG 답변 | Faithfulness, Answer Relevance |
| **L5 E2E** | 사용자 질의 | Human eval, task success rate |

## 골든 QA 셋

`data/eval/golden_qa.jsonl` 형식:

```json
{"id": "q001", "question": "계약 해지 조건은?", "expected_doc": "contract.pdf", "expected_pages": [3, 4], "reference_answer": "30일 전 서면 통보...", "tags": ["legal", "korean"]}
```

최소 **10문항**으로 시작, 도메인별 확장.

## RAG 자동 평가

### Retrieval

```python
def recall_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int) -> float:
    top_k = set(retrieved_ids[:k])
    return len(top_k & gold_ids) / len(gold_ids) if gold_ids else 0.0
```

### Generation (LLM-as-judge 또는 RAGAS)

```bash
pip install ragas
```

```python
from ragas.metrics import faithfulness, answer_relevancy
# dataset: question, answer, contexts, ground_truth
```

**Faithfulness**: 답변이 컨텍스트에 근거하는가  
**Answer Relevance**: 질문에 답하는가

## OCR 평가

```python
def cer(reference: str, hypothesis: str) -> float:
    # Levenshtein distance / len(reference)
    ...
```

샘플 페이지 5–10장에 정답 텍스트 수동 작성 후 CER < 5% 목표(도메인별 조정).

## 리포트 템플릿

`thoughts/shared/research/eval-{date}.md`:

```markdown
# Document AI 평가 리포트 — YYYY-MM-DD

## 설정
- Embedding: ...
- Chunk: size=1000, overlap=150
- k=5, rerank=on/off

## Retrieval
| Metric | Value |
|--------|-------|
| Recall@5 | 0.82 |
| MRR | 0.71 |

## Generation (n=20)
| Metric | Value |
|--------|-------|
| Faithfulness | 0.88 |
| Answer Relevance | 0.85 |

## 실패 케이스
1. q007 — 표 데이터 누락 → chunk 전략 변경 필요

## 다음 실험
- [ ] Hybrid search 추가
- [ ] chunk_size 800으로 축소
```

## CI 연동 (선택)

```yaml
# .github/workflows/eval.yml
- run: python -m scripts.run_eval --min-recall 0.75
```

회귀 방지: 지표 하락 시 PR fail.

## 워크플로우

1. baseline 측정 (현재 설정)
2. 변경 1가지만 적용 (chunk size, model, rerank)
3. 동일 golden set으로 재측정
4. `thoughts/shared/research/`에 결과 기록

## 완료 기준

- [ ] golden_qa.jsonl ≥ 10문항
- [ ] Recall@5, Faithfulness 수치 보고
- [ ] 실패 3건 이상 원인 분석
