---
name: document-ai
description: Document AI 파이프라인. PDF/OCR/RAG/평가 + 양식 자동 작성(form-fill) 요청 시 적합한 하위 스킬로 라우팅.
---

# Document AI 오케스트레이터

## 최종 목표 (North Star)

> **완성 문서로 학습 → 빈 양식 + 새 케이스 → 자동 문서 작성**

이 목표 관련 작업은 **`form-fill-agent`** 스킬을 최우선으로 따릅니다.

## 라우팅

### 양식 자동 작성 (핵심)

| 사용자 의도 | 스킬 |
|-------------|------|
| 전체 목표·아키텍처 | `form-fill-agent` |
| **채팅 + 참고 DOCX → input.json** | `case-intake` |
| 양식·필드 스키마 학습 | `template-learn` |
| 유사 완성본 검색 | `case-retrieval` |
| 필드값 추론 | `form-fill` |
| DOCX/PDF 출력 | `document-render` |

### 기반 파이프라인

| 사용자 의도 | 스킬 |
|-------------|------|
| PDF 텍스트/표 추출 | `pdf-parse` |
| 스캔본 OCR | `document-ocr` |
| RAG 청킹 | `document-chunk` |
| 벡터 검색·API | `document-rag` |
| 품질 평가 | `document-eval` |

## 전체 흐름

```
[학습] 완성본(+양식) → parse → template-learn → case-index
[작성] 채팅/DOCX → case-intake → input.json → case-retrieval → form-fill → render
[검증] document-eval (field F1)
```

## 시작 전 확인

1. **입력 형식**: PDF(텍스트/스캔), DOCX, HWP, 이미지?
2. **언어**: 한국어/영어/혼합?
3. **목표**: 검색 QA, 요약, 정보 추출, 분류?
4. **제약**: 로컬 only vs API, 예산, 지연 시간

불명확하면 `interview` 스킬 또는 사용자에게 2–3개 질문.

## 프로젝트 컨벤션

- 코드: `src/document_ai/` (생성 시)
- 설정: `config/` 또는 `.env` (API 키는 커밋 금지)
- 샘플 문서: `data/samples/` (gitignore 대상 가능)
- 실험 노트: `thoughts/shared/research/`
- 플랜: `thoughts/shared/plans/`

## 서브에이전트

- `document-analyzer` — 기존 파이프라인 코드 분석
- `codebase-locator` — 관련 모듈 탐색
- `web-search-researcher` — 라이브러리·모델 최신 정보

## 완료 기준

- 파이프라인 각 단계 입·출력 형식이 명시됨
- 실패 케이스(빈 PDF, OCR 실패, 인코딩) 처리 방안 있음
- `document-eval`로 최소 1개 검증 방법 정의
