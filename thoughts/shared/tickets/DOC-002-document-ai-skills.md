---
title: "[DOC-002] Document AI 도메인 스킬 및 파이프라인 기반"
type: "Feature"
priority: "High"
status: "Done"
assignee: "@hsh71"
---

## 설명

Document AI 프로젝트에 PDF 파싱, OCR, 청킹, RAG, 평가를 위한 Cursor 도메인 스킬과
아키텍처 가이드를 추가한다.

## 완료 기준

- [x] `.cursor/skills/` — document-ai 오케스트레이터 + 5개 하위 스킬
- [x] `.cursor/agents/document-analyzer.md`
- [x] `AGENTS.md` 파이프라인 아키텍처 업데이트
- [x] `data/eval/golden_qa.jsonl` 템플릿
- [x] `.env.example`, `.gitignore`
- [ ] `src/document_ai/` 실제 코드 구현 (다음 티켓)

## 기술 상세

- 프로젝트 스킬은 `.cursor/skills/` (레포 로컬)
- 글로벌 워크플로우 스킬은 `~/.cursor/skills/` (하네스 install)

## 다음 티켓

- DOC-003: `src/document_ai/` ingest + parse MVP 구현
