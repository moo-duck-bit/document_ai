---
title: "[DOC-003] Form Fill Agent — 완성본 학습 → 빈 양식 자동 작성"
type: "Feature"
priority: "High"
status: "Planned"
assignee: "@hsh71"
---

## 확정 요구사항

| 항목 | 결정 |
|------|------|
| 포맷 | **DOCX** |
| 문서 종류 | **보고서, 신청서, 제안서** |
| 케이스 입력 | **채팅(Primary) + 참고 DOCX 추출(Secondary) → input.json (사용자 확인)** |

## 설명

완성 DOCX를 학습해, 빈 양식 + 확정된 `input.json`으로 새 케이스 문서를 자동 생성.

## 사용자 스토리

> IT 제안서 양식이 있고 과거 제안서 5건이 있다.
> 채팅으로 거래처·예산·기간을 알려주고, RFP DOCX를 첨부하면
> Agent가 facts를 정리해 확인받은 뒤 제안서 초안 DOCX를 만든다.

## 완료 기준

- [ ] template_id별 schema (proposal / report / application)
- [ ] case-intake: 채팅 → input.json + confirmed
- [ ] case-intake: 참고 DOCX → facts merge
- [ ] form-fill + document-render → output.docx
- [ ] golden_fields.jsonl 필드 F1 ≥ 90%

## template_id (1차)

- `proposal_it` — IT 제안서
- `report_quarterly` — 분기 보고서
- `application_grant` — 신청서

## 미결

- [ ] 실제 DOCX 양식·완성본 샘플 (사용자 제공)

## 참고

- `thoughts/shared/plans/form-fill-agent-master.md`
- `thoughts/shared/research/case-intake-design.md`
