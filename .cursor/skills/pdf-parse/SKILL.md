---
name: pdf-parse
description: PDF에서 텍스트·표·메타데이터·레이아웃을 추출합니다. PyMuPDF, pdfplumber, pymupdf4llm 등 선택과 구현 가이드.
---

# PDF 파싱

PDF 문서에서 구조화된 텍스트와 메타데이터를 추출합니다.

## 라이브러리 선택

| 라이브러리 | 적합한 경우 | 한계 |
|-----------|------------|------|
| **PyMuPDF (fitz)** | 빠른 텍스트 추출, 페이지별 처리 | 복잡한 표 레이아웃 |
| **pdfplumber** | 표(table) 추출, 좌표 기반 | 대용량 PDF 느릴 수 있음 |
| **pymupdf4llm** | LLM/RAG용 Markdown 변환 | 커스텀 레이아웃 제어 제한 |
| **Unstructured** | 다양한 포맷 통합 파이프라인 | 의존성 무거움 |

**권장 기본**: 텍스트 위주 → PyMuPDF, 표 많음 → pdfplumber, RAG 직전 → pymupdf4llm.

## 구현 체크리스트

### 1. PDF 유형 판별

```python
import fitz  # PyMuPDF

def classify_pdf(path: str) -> str:
    doc = fitz.open(path)
    text_len = sum(len(page.get_text()) for page in doc)
    if text_len < 50 * len(doc):  # 페이지당 텍스트 거의 없음
        return "scanned"  # → document-ocr 스킬로 위임
    return "text"
```

### 2. 텍스트 추출 (PyMuPDF)

- `page.get_text("text")` — 단순
- `page.get_text("dict")` — 블록·좌표 보존
- 페이지 번호·`metadata` 함께 저장

### 3. 표 추출 (pdfplumber)

```python
import pdfplumber

with pdfplumber.open(path) as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        text = page.extract_text()
```

### 4. 출력 스키마

```python
@dataclass
class ParsedPage:
    page_num: int
    text: str
    tables: list[list[list[str]]]  # optional
    metadata: dict

@dataclass
class ParsedDocument:
    source_path: str
    doc_type: str  # text | scanned | mixed
    pages: list[ParsedPage]
    metadata: dict  # title, author, created
```

JSONL 또는 Parquet로 `data/processed/`에 저장 권장.

## 한국어 PDF 주의

- **폰트 임베딩** 없으면 깨진 글자 → OCR 경로
- **HWP→PDF** 변환본은 레이아웃 깨짐 빈번 → 수동 샘플 검증
- **CID 폰트** 이슈: `get_text()` 결과 샘pling 후 품질 확인

## 검증

- [ ] 샘플 3종(텍스트 PDF, 스캔 PDF, 표 PDF) 수동 확인
- [ ] 페이지 수·문자 수 로그
- [ ] 빈 페이지·암호화 PDF 예외 처리

## 실패 시

- `scanned` 판정 → `document-ocr` 스킬
- 파싱 결과 품질 낮음 → `document-eval` 스킬로 측정 후 전략 변경
