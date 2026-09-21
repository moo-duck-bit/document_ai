# Document AI v2 — Pilot Presentation Deck

슬라이드 단위 원고입니다. PPT로 옮길 때 **제목 = 슬라이드 제목**, 불릿 = 본문.

---

## 1. 문제 정의

**제목:** 문서는 바뀌는데, 수정은 위험하다

- 요구사항·설계·제안서·보고서는 서로 연결되어 있음
- 한 줄 변경이 여러 표·섹션에 영향을 줌
- 사람은 위치를 찾기 어렵고, 자동 수정은 원본 손상 위험이 큼
- 필요: **찾고 → 보여주고 → 사람이 승인 → 복사본만 저장**

---

## 2. Document AI 소개

**제목:** Document AI v2

- North Star: 완성 문서로 학습해 새 케이스를 작성·갱신
- v2 핵심: Generic Template Engine + Domain Pack + Controlled Writer
- 오늘 범위: **실제 사용자가 쓰는 Pilot 제품**
- 하지 않는 것: 새 Benchmark 튜닝, 새 Domain Pack, 자동 승인

---

## 3. Architecture

**제목:** 두 층 구조

```
Pilot UI / CLI
    ↓
Workflow (parse → locate → patch contract → review)
    ↓
Domain Packs (EC-SW · General Report · Business Proposal)
    ↓
Controlled Writer (승인 · fingerprint · copy-only)
```

- Identity / Auto routing으로 Domain Pack 선택
- Physical locator unresolved → Writer 금지

---

## 4. Workflow

**제목:** 사용자 6단계

1. 업로드 (세션 복사본)
2. 문서 유형 · Domain Pack 확인
3. 변경 요청
4. 영향 분석
5. 항목별 승인 / 거절 / 보류
6. 결과 · 다운로드 · 사용성 평가

---

## 5. Demo

**제목:** 라이브 데모

| # | Domain | 시나리오 |
|---|--------|----------|
| A | EC-SW | Req.11 추적성 |
| B | General Report | 방법론 보강 |
| C | Business Proposal | 예산 변경 |

→ 상세 대사: `docs/pilot/DEMO_SCRIPT.md`

---

## 6. Benchmark

**제목:** 엔진 품질 (고정 결과)

- Holdout Document F1 **0.956**
- Holdout E2E **0.957**
- False Patch **0** / Unsafe Failure **0**
- Original Preservation **1.000**
- BP Required Top-1 **0.929** · GR Node Top-1 **1.000**

*Pilot 단계에서 Benchmark를 다시 돌리거나 튜닝하지 않음.*

---

## 7. Pilot

**제목:** Real User Pilot Package

- UI: `/pilot-v2`
- Demo dataset: `data/pilot/demo/` (12 scenarios)
- CLI: `run-pilot-demo` / `run-pilot-session` / `evaluate-pilot`
- Human Review: 10 dimensions
- Guide · Checklist · Bug template · Release notes

---

## 8. Safety

**제목:** 안전이 제품이다

- 원본 직접 수정 금지
- 승인 없는 Writer 금지
- stale fingerprint / path escape 차단
- session 간 artifact 접근 금지
- DELETE·고위험 셀: 별도 명시 승인 정책

---

## 9. Future Work

**제목:** 다음

1. 실제 참가자 Pilot 실행 · 메트릭 채움
2. 승인 게이트 유지한 Writer 텍스트 적용 확대
3. MDVP 연동 검토
4. (장기) KG / LLM free_text — Pilot 범위 밖

---

## Appendix — 한 장 요약

**Document AI v2 Pilot = 검증된 엔진 + 사람이 끝까지 통제하는 UI**

판정: `READY_FOR_PILOT_RELEASE`
