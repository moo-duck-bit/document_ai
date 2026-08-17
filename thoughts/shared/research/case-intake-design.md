# 케이스 입력(Case Intake) 설계

## 결정 사항 (2026-06)

| 항목 | 선택 |
|------|------|
| 문서 포맷 | **DOCX** |
| 도메인 | **보고서, 신청서, 제안서** (+ 확장) |
| 케이스 입력 | **하이브리드**: 채팅(Primary) + 참고문서 추출(Secondary) → **input.json** |

## 왜 하이브리드인가

### 채팅만
- ✅ UX 좋음, 비전문가 친화
- ❌ 금액·날짜 오타, 재현·감사 어려움

### 문서 추출만
- ✅ RFP/공고에서 facts 대량 추출
- ❌ 사용자 의도·누락 보완 어려움

### JSON만
- ✅ 테스트·API·eval 최적
- ❌ 일반 사용자에게 불친절

→ **채팅 + 문서 추출 → input.json 확정(사용자 확인)** 이 균형점.

## Canonical 데이터 흐름

```
User (chat / upload DOCX)
    → case-intake (extract + merge)
    → input.json (confirmed: true)
    → form-fill → document-render → output.docx
```

## template_id 네이밍

```
proposal_{domain}   # 제안서  e.g. proposal_it, proposal_consulting
report_{domain}     # 보고서  e.g. report_quarterly, report_research
application_{prog}  # 신청서  e.g. application_grant, application_internal
```

## MVP 구현 순서

1. `schemas/proposal_it.schema.json` (placeholder DOCX 기준)
2. CLI: `intake from-json` (JSON → validate)
3. Chat intake: schema guided Q&A → input.json
4. Doc intake: reference DOCX → merge into input.json
5. FastAPI: `POST /intake/chat`, `POST /intake/document`

## 참고

- 스킬: `.cursor/skills/case-intake/SKILL.md`
- 예시: `data/cases/example_proposal/input.json`
