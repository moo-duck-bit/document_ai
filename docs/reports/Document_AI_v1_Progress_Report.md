# Document AI v1 진행 보고

**기준:** Trial 1(Mindrium) 이후 ~ Document AI v1 1차 완성  
**최종 판정:** `DOCUMENT_AI_V1_COMPLETE`  
**회귀 테스트:** 964 passed / 0 failed  
**원본 문서 변경:** 0건 (복사본만 수정)  
**데모 UI:** Pilot UI (Run / Review / Writer)  
**PDF:** `docs/reports/Document_AI_v1_Progress_Report.pdf`

---

## 1. 지난 Trial 1 보고와의 연결

지난 Trial 1에서는 자연어 변경요청 → 요구사항 매핑 → 영향분석 → 원본 보존형 수정까지 Document Harness를 구현·테스트했습니다. 매핑과 구조/서식 보존 수정은 정상 동작했지만, ID/기존 연결 중심 Impact만으로는 의미적으로 연관된 항목을 충분히 찾지 못해 MDDR 등 관련 문서로 변경이 정확히 전파되지 않는 문제를 확인했습니다.

| 항목 | Trial 1 결과 |
|------|-------------|
| 요구사항 매핑 | 정상 |
| 구조·서식 보존형 부분 수정 | 정상 |
| Impact 분석 (ID/기존 연결 중심) | 부족 |
| MDDR 등 관련 문서 전파 | 미흡 |

그 이후 Document AI v1을 1차 완성했고, Pilot UI로 실제 실행 흐름을 확인할 수 있습니다.

---

## 2. 핵심 메시지

> 자연어 변경요청 + MDSR/MDDR → 관련 위치 탐색 → 안전 게이트 → 확실한 것만 복사본 수정 → Diff/Review 산출

- 위치 탐색 + 안전 수정: 상당 부분 해결
- 문서 간 의미 기반 전파: 부분 개선, 완전 해결은 아님

---

## 3. Harness와 Agent

| 이름 | 의미 | 현재 |
|------|------|------|
| Document Harness | 입력→실행→결과/검증 틀 | 시나리오 러너 + Pilot UI + pytest |
| Document Change Agent | B1~B5 오케스트레이터 | 파이프라인 실행자 |
| LLM Agent | 자율 생성형 에이전트 | 메인 아님 |

사람: 요청 작성·문서 첨부·검토/승인  
Agent: 탐색·영향/안전 판정·복사본 수정·리뷰 자료

핵심 구현: 검색 + 규칙/점수 판정 + 문서 패치 자동화

---

## 4. Pilot UI

### Run
- CR 자연어 입력 + MDSR/MDDR 첨부 → [분석 실행]
- Agent가 B1~B5 실행, 안전한 것만 복사본 수정, 원본 수정 금지
- `COMPLETED_NEEDS_REVIEW` = 자동 처리 종료 + 사람 최종 검토 요청

### Review
- 좌측: 요약 JSON + CHANGE_SUMMARY / REVIEW_REQUIRED / PATCH_DIFF / updated_*.docx
- 우측: before/after Diff, `patched=True`만 반영, 나머지는 REVIEW

---

## 5. B1~B5 (상세)

| 단계 | 내용 |
|------|------|
| B1 | MDSR/MDDR를 Req 블록으로 인덱싱 (req_id, title, body, locator). 중복 제거. 변경 없음 |
| B2 | Hybrid = 0.4×lexical + 0.6×TF-IDF cosine. Top-K=15. LLM 임베딩 아님. 정답 누수 금지 |
| B3 | relevance·facet·false-friend로 IMPACTED/UNCERTAIN/NOT. ID만으로 IMPACTED 금지 |
| B4 | IMPACTED만 게이트. CONSISTENT만 자동패치. NEEDS_REVIEW/CONFLICT는 차단 |
| B5 | CONSISTENT만 복사본 패치. MDDR 전파는 정렬 불충분 시 REVIEW. Diff 기록 |

PR18~25: Template → Structure → Locator → Contract → Controlled Writer  
안전: 원본 금지 / 승인 / Fingerprint / Rollback / Diff / Validation

---

## 6. 벤치마크·평가 기준

v1 완성 = “성능 완벽”이 아니라 **안전·회귀·실문서 시나리오 통과**.

| 층 | 기준 / 방법 | 결과 |
|----|-------------|------|
| 회귀 pytest | 고정 입력·게이트·Writer 불변식 | 964 passed |
| 안전 불변식 | 원본 fingerprint, flag 단독 차단, rollback | 원본 0 |
| Writer | 승인 후 복사본, Diff/Validation | PR-25 52 passed |
| 실문서 시나리오 | scenario-001 / Pilot CR, Diff·REVIEW 육안 | COMPLETED_NEEDS_REVIEW |

단계별: B2 순위·누수금지 / B3 ID-only 금지 / B4 CONSISTENT만 / B5 원본미수정 / Writer 미승인 차단

사람 평가(Trial): content_accuracy 등 6차원 1–5. UI: PASS/PARTIAL/FAIL.  
전파 Recall/Precision scorecard는 다음 과제(평가셋)에서 baseline.

---

## 7. Trial 1 대비 변화

| 구분 | Trial 1 | 현재 v1 |
|------|---------|---------|
| 탐색 | ID/연결 중심 | Hybrid + Impact |
| 전파 | MDDR 미흡 | 부분 개선, 완전 미완 |
| UI | 제한적 | Pilot UI |
| 검증 | Trial 리포트 | 964 + 시나리오 + Writer 안전 |

---

## 8. 현재 한계

- 자율 LLM Agent 아님
- 의미 기반 전파 완전성 미해결
- CR→Contract→Writer 일원화 고도화 필요
- HWP 미지원 (DOCX)
- 평가셋·scorecard baseline 확대 필요

---

## 9. 다음 우선순위

| 순위 | 과제 | 왜 | 어떻게 |
|------|------|----|--------|
| P0 | 실문서 평가셋 | 수치로 증명 | 시나리오 10 + baseline |
| P1 | 의미 기반 전파 | Trial 1 핵심 gap | REVIEW/SKIP 분석 → B3/B4 |
| P2 | CR→Contract→Writer | 실행 일원화 | E2E 데모 |
| P3 | UI 사용성 | 데모/협업 | 상태·하이라이트 |
| P4 | LLM 선택 도입 | 문안/REVIEW 보조 | 구조화 판정 LLM 금지 |

원칙: 원본 보호, fail-closed, 측정 후 개선

---

## 10. 결론

Document Harness + Document Change Agent로 탐색·안전 게이트·복사본 패치·리뷰까지 1차 완성.  
다음: 평가셋 baseline → 의미 전파 개선 → Contract/Writer 연결.  
**최종 판정:** `DOCUMENT_AI_V1_COMPLETE`
