# Document AI 도메인 스킬 구현 플랜

## 개요

Cursor Agent가 Document AI 작업(PDF, OCR, RAG 등)을 일관되게 수행하도록
프로젝트 전용 스킬·에이전트·평가 템플릿을 구축한다.

## 현재 상태

- 하네스 fork + 글로벌 한국어 워크플로우 스킬 설치 완료 (DOC-001)
- 애플리케이션 코드 없음 — 스킬/가이드만 존재

## 목표 상태

- `.cursor/skills/`에 6개 document AI 스킬
- `document-analyzer` 에이전트
- AGENTS.md에 파이프라인 다이어그램·스택·디렉터리 규약
- eval golden set 템플릿

## Phase 1: 도메인 스킬 — ✅ 완료

- [x] document-ai (orchestrator)
- [x] pdf-parse, document-ocr, document-chunk, document-rag, document-eval

## Phase 2: 에이전트 & 문서 — ✅ 완료

- [x] document-analyzer
- [x] AGENTS.md
- [x] .env.example, .gitignore
- [x] golden_qa.jsonl 템플릿

## Phase 3: MVP 코드 (다음 작업 — DOC-003)

### 개요
최소 ingest → parse → chunk 파이프라인

### 변경 사항
- `src/document_ai/parse/pdf.py` — PyMuPDF wrapper
- `src/document_ai/chunk/splitter.py`
- `tests/test_parse.py`
- `pyproject.toml` / requirements.txt

### 성공 기준
- [ ] 샘플 PDF 1개 파싱 CLI
- [ ] pytest 통과

## 참고

- 티켓: `thoughts/shared/tickets/DOC-002-document-ai-skills.md`
- 리서치: `thoughts/shared/research/document-ai-stack.md`
