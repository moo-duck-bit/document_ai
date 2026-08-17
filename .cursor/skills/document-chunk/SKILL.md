---
name: document-chunk
description: RAG용 문서 청킹 전략과 구현. 고정 크기, 의미 단위, 계층적, 표/코드 보존 청킹.
---

# Document Chunking

파싱/OCR 결과를 RAG에 적합한 청크로 분할합니다.

## 청킹 전략

| 전략 | 설명 | 적합 |
|------|------|------|
| **Fixed-size** | 토큰/문자 수 + overlap | 빠른 baseline |
| **Recursive** | `\n\n`, `\n`, `.` 순 분할 | 일반 텍스트 |
| **Semantic** | 임베딩 유사도로 경계 | 긴 문서, 주제 전환 많음 |
| **Structure-aware** | 제목·표·리스트 단위 | 매뉴얼, 논문, 법률 |
| **Parent-child** | 작은 청크 검색 + 큰 부모 컨텍스트 | 정밀 검색 + 풍부 답변 |

## 권장 파라미터 (baseline)

```python
CHUNK_SIZE = 512       # tokens (또는 1000–1500 chars 한국어)
CHUNK_OVERLAP = 64     # tokens (~10–15%)
SEPARATORS = ["\n\n", "\n", ". ", "。", " ", ""]
```

한국어는 **문자 수**로 시작하고, 임베딩 모델 토큰 한도에 맞춰 조정.

## LangChain 예시

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n## ", "\n\n", "\n", ". ", " ", ""],
)
chunks = splitter.split_text(full_text)
```

## 청크 메타데이터 (필수)

각 청크에 검색·인용에 필요한 메타데이터:

```python
@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    text: str
    page_nums: list[int]
    section_title: str | None
    chunk_index: int
    source_path: str
    char_start: int | None
    char_end: int | None
```

**인용(citation)** 응답을 위해 `page_nums`, `source_path` 반드시 포함.

## 특수 콘텐츠

| 유형 | 처리 |
|------|------|
| **표** | Markdown 테이블로 유지, 단일 청크 또는 행 단위 |
| **코드** | fenced block 분리, overlap 최소화 |
| **각주** | 본문 청크에 병합 또는 별도 청크 + link |
| **다국어** | 언어 태그 메타데이터 |

## Parent-Child 패턴

```
Parent (2000 tokens) — LLM 컨텍스트용
  └── Child (400 tokens) — 벡터 검색용
```

검색: child embedding → 매칭 parent를 LLM에 전달.

## 검증

- [ ] 청크 길이 분포 히스토그램 (극단적 짧/김 청크 < 5%)
- [ ] overlap으로 문장 중간 절단 최소화 (샘플 20개 수동)
- [ ] 동일 질의로 retrieval 테스트 → `document-eval`

## 다음 단계

청크 → 임베딩 → `document-rag`
