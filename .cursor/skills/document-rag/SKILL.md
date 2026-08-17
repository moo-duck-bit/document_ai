---
name: document-rag
description: 문서 RAG 파이프라인 설계·구현. 임베딩, 벡터 DB, 검색, 리랭킹, 프롬프트, API 엔드포인트.
---

# Document RAG

청크된 문서를 임베딩·저장·검색하여 질의응답 파이프라인을 구축합니다.

## 아키텍처

```
Ingest:  문서 → parse/OCR → chunk → embed → vector store
Query:   질문 → embed → retrieve → (rerank) → LLM → 답변 + citation
```

## 스택 선택

| 레이어 | 로컬/무료 | 프로덕션 |
|--------|----------|----------|
| **Embedding** | `multilingual-e5-small`, BGE-M3 | OpenAI `text-embedding-3-small`, Cohere |
| **Vector DB** | Chroma, FAISS | Pinecone, Qdrant, pgvector |
| **LLM** | Ollama (llama3, exaone) | GPT-4o, Claude |
| **Framework** | LangChain, LlamaIndex | 동일 + 커스텀 |

**한국어 문서**: multilingual 또는 한국어 특화 임베딩(BGE-M3, KoSimCSE) 권장.

## Ingest 파이프라인

```python
# 의사 코드
for doc in documents:
    parsed = parse_or_ocr(doc)
    chunks = chunk(parsed)
    for c in chunks:
        vector = embed(c.text)
        store.upsert(id=c.chunk_id, vector=vector, metadata=c.to_dict())
```

- **배치 임베딩** API rate limit 고려
- **doc_id** 기준 삭제·재인덱싱 지원

## Retrieval

### Baseline

```python
results = store.similarity_search(query_embedding, k=5)
```

### 개선 (순서대로 적용)

1. **Hybrid**: BM25(키워드) + dense vector, RRF 병합
2. **Reranker**: cross-encoder (`bge-reranker-v2-m3`)
3. **Query expansion**: HyDE, multi-query
4. **Metadata filter**: `doc_type`, `date`, `section`

## 프롬프트 템플릿

```text
다음 컨텍스트만 사용해 질문에 답하세요. 컨텍스트에 없으면 "제공된 문서에서 찾을 수 없습니다"라고 답하세요.
각 주장 뒤에 [출처: 파일명, p.N] 형식으로 인용하세요.

## 컨텍스트
{context}

## 질문
{question}
```

## API 설계 (FastAPI 예시)

```
POST /ingest          — 문서 업로드·인덱싱
POST /query           — { "question": "...", "filters": {} }
GET  /documents       — 인덱스된 문서 목록
DELETE /documents/{id} — 문서 삭제
```

## 설정 (.env.example)

```env
EMBEDDING_MODEL=BAAI/bge-m3
VECTOR_DB_PATH=./data/chroma
LLM_PROVIDER=openai
OPENAI_API_KEY=          # 커밋 금지
TOP_K=5
RERANK_ENABLED=true
```

## 흔한 실패

| 증상 | 원인 | 대策 |
|------|------|------|
| 관련 없는 답 | 청크 품질/k 너무 작음 | chunk/rerank 조정 |
| hallucination | 프롬프트·컨텍스트 부족 | citation 강제, "모름" 허용 |
| 한국어 검색 약함 | 영어-only embedding | multilingual 모델 |
| 느림 | 매 query embed+LLM | 캐시, smaller k |

## 검증

- [ ] 골든 QA 셋 10–20문항 → `document-eval`
- [ ] latency p95 측정
- [ ] 인덱스 증분 업데이트 테스트

## 다음 단계

구현 후 반드시 `document-eval` 스킬로 평가.
