---
title: "[DOC-001] Cursor 하네스 고도화"
type: "Feature"
priority: "High"
status: "Done"
assignee: "@hsh71"
---

## 설명

ai-engineering-harness를 fork하여 Cursor 지원, 한국어 워크플로우 스킬, document_AI 프로젝트 하네스 초기화를 수행.

## 완료 기준

- [x] upstream repo clone
- [x] cursor/ 디렉터리 (한국어 agents + skills)
- [x] manifest.json, setup.sh, install.ps1 업데이트
- [x] document_AI thoughts/ 구조 생성

## 기술 상세

- Cursor agents: `~/.cursor/agents/` (kebab-case)
- Cursor skills: `~/.cursor/skills/`
- Windows: `install.ps1 -Tool cursor`
