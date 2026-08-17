# Document AI 기술 스택 리서치

## 요약

한국어 문서 RAG PoC에는 **Python + PyMuPDF + BGE-M3 + Chroma + FastAPI** 조합이
로컬 개발·확장 균형이 좋다. 스캔 PDF 비중이 높으면 PaddleOCR 추가.

## PDF 파싱

| 도구 | 용도 |
|------|------|
| PyMuPDF | 빠른 텍스트, 페이지 메타 |
| pdfplumber | 표 추출 |
| pymupdf4llm | Markdown 변환 (RAG 직전) |

스캔 PDF: 텍스트 길이 heuristic → OCR 분기.

## OCR

| 도구 | 한국어 | 비고 |
|------|--------|------|
| Tesseract kor | ○ | 전처리 필요 |
| PaddleOCR | ◎ | 표·레이아웃 |
| EasyOCR | ○ | PoC 빠름 |
| Vision API | ◎ | 비용 |

## Embedding (한국어)

| 모델 | 차원 | 비고 |
|------|------|------|
| BAAI/bge-m3 | 1024 | multilingual SOTA급 |
| intfloat/multilingual-e5-small | 384 | 가벼움 |
| OpenAI text-embedding-3-small | 1536 | API |

## Vector DB

| DB | PoC | Production |
|----|-----|------------|
| Chroma | ◎ | embedded |
| FAISS | ○ | 파일 기반 |
| Qdrant | ○ | self-host/cloud |
| pgvector | ○ | Postgres 통합 |

## RAG Framework

- **LangChain**: 생태계 넓음, 문서 많음
- **LlamaIndex**: 인덱싱 특화
- PoC는 LangChain → 복잡해지면 LlamaIndex 또는 커스텀

## 평가

- **RAGAS**: faithfulness, answer_relevancy
- **Custom**: Recall@k (golden_qa.jsonl)
- OCR: CER (character error rate)

## 권장 PoC 순서

1. 텍스트 PDF 1개 → parse → chunk → embed → Chroma
2. CLI query 5문항 수동 테스트
3. golden_qa 10문항 + Recall@5
4. 스캔 PDF → OCR 추가
5. FastAPI `/query` 엔드포인트

## 참고 링크

- [PyMuPDF docs](https://pymupdf.readthedocs.io/)
- [BGE-M3 HuggingFace](https://huggingface.co/BAAI/bge-m3)
- [RAGAS](https://docs.ragas.io/)
