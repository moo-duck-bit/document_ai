# Document AI Pilot UI — 테스트 시나리오

대상: `http://127.0.0.1:8765` (또는 LAN `http://<host-ip>:8765`)  
전제: `docker compose up -d` 로 Pilot UI가 떠 있는 상태

채점:

| 결과 | 의미 |
|------|------|
| PASS | 기대와 동일 |
| PARTIAL | 동작은 하나 품질/리뷰 이슈 |
| FAIL | UI/파이프라인 오류 |

---

## 사전 체크 (S0)

**목적:** UI·API가 살아 있는지 확인

1. 브라우저에서 Pilot UI 접속
2. 상단 탭 `1. Run` / `2. Review` / `3. Writer` 표시 확인
3. (선택) `http://127.0.0.1:8765/api/pilot/health` → `{"ok": true}`

**기대:** 페이지 로드, health ok  
**결과:** [ ]

---

## S1. 데모 시나리오 복사 실행 (가장 쉬운 E2E)

**목적:** 업로드 없이 UI 전체 흐름 확인

1. `1. Run` 탭
2. “기존 시나리오 경로”가 `data/user_scenarios/scenario-001` 인지 확인
3. **데모 시나리오 복사 후 실행** 클릭
4. 상태 문구가 `실행 중…` → `완료: <run_id> · COMPLETED...` 로 바뀌는지 확인  
   (문서 크기에 따라 **수 분** 소요 가능)
5. 자동으로 `2. Review` 탭으로 이동하는지 확인

**기대:**
- `run_id` 생성 (`demo-copy_YYYYMMDD_...`)
- status가 `COMPLETED` / `COMPLETED_NEEDS_REVIEW` 등 `COMPLETED*` 계열
- Review에 CHANGE_SUMMARY / REVIEW_REQUIRED / PATCH_DIFF 중 하나 이상 표시
- Artifacts에 `updated_MDSR.docx`, `updated_MDDR.docx` 링크 존재 가능
- freeze 원본 `scenario-001` 입력 파일이 수정되지 않음 (복사본만 `_pilot/`에 생성)

**기록:**
- run_id: ________
- status: ________
- 결과: PASS / PARTIAL / FAIL

---

## S2. Review 문서 확인

**목적:** 사람 리뷰 UX

전제: S1 완료 후 해당 run 선택

1. `2. Review`에서 Summary JSON 표시 확인
2. 세그먼트 버튼 전환:
   - CHANGE_SUMMARY
   - REVIEW_REQUIRED
   - PATCH_DIFF
3. Artifacts 링크 클릭 → 파일 다운로드/열림 확인

**기대:**
- 세그먼트마다 본문이 바뀜 (비어 있어도 “(empty)”가 아닌 실제 md일 가능성 높음)
- docx/json 다운로드 가능
- Summary에 `input_hashes_unchanged` 관련 표시

**결과:** [ ]

---

## S3. 직접 업로드 실행 (실문서)

**목적:** 사용자 문서 경로 검증

준비물:
- MDSR.docx (파일명에 MDSR/mdsr/요구사항 권장)
- MDDR.docx (파일명에 MDDR/mddr/설계 권장)
- 변경 요청 텍스트

1. `1. Run`
2. Scenario name: `pilot-manual-001`
3. Change request 예시:

```text
대시보드 관련 설명을 더 명확하게 수정한다.
환자 조회/활동 상태와 관련된 요구사항이 영향받을 수 있다.
```

4. MDSR / MDDR 파일 선택
5. top-k = 15
6. **분석 실행**

**기대:**
- 완료 후 Review로 이동
- `_pilot/<run_id>/input/reference/` 에 업로드 파일 존재
- 원본 업로드 파일(내 PC의 원본 경로)은 그대로
- status `COMPLETED*` 또는 `FAILED`(실패 시 error 메시지 표시)

**기록:**
- run_id: ________
- IMPACTED/REVIEW/PATCHED 느낌(Summary): ________
- 결과: PASS / PARTIAL / FAIL

---

## S4. Recent runs 재진입

**목적:** 이력 복원

1. `1. Run` 하단 Recent runs에서 이전 run 클릭
2. Review가 다시 로드되는지 확인
3. Run ID를 수동 입력 후 **불러오기**도 확인

**기대:** 동일 run 내용 재표시  
**결과:** [ ]

---

## S5. Writer — Approval REJECT

**목적:** 승인 거부 시 Writer 차단

1. `3. Writer` 탭, Run ID 확인
2. Decision = `REJECTED`
3. **승인 저장**
4. **Writer 실행**

**기대:**
- 승인 저장은 성공 (`ok: true`, decision REJECTED)
- Writer 실행은 실패/400 계열  
  (메시지에 approval decision must be APPROVED… 등)

**결과:** [ ]

---

## S6. Writer — Approval APPROVED + 실행

**목적:** Controlled Writer copy-only 경로

1. Decision = `APPROVED`
2. Approved by = 본인 이름
3. Reason = `pilot ui test`
4. **승인 저장**
5. **Writer 실행** (수십 초 가능)

**기대:**
- `ok: true`
- `summary.original_changed_count == 0`
- `writer_results`에 APPLIED / BLOCKED / REJECTED / ROLLED_BACK 혼재 가능
- validation status가 VALID 또는 이슈 명시
- 호스트의 `data/user_scenarios/_pilot/<run_id>/pilot/writer_engine_result.json` 생성

**기록:**
- original_changed_count: ________
- patch_success_count: ________
- 결과: PASS / PARTIAL / FAIL

---

## S7. 잘못된 입력 (네거티브)

**목적:** 실패가 안전하게 보이는지

| 단계 | 행동 | 기대 |
|------|------|------|
| S7-1 | Change request 비우고 실행 | 실행 불가/에러 |
| S7-2 | MDSR만 넣고 MDDR 없이 실행 | required 또는 에러 |
| S7-3 | 존재하지 않는 Run ID 불러오기 | 에러 메시지 |
| S7-4 | 승인 없이 Writer 실행 | approval required |

**결과:** S7-1 [ ] S7-2 [ ] S7-3 [ ] S7-4 [ ]

---

## S8. LAN 외부 접속 (선택)

**목적:** Docker 외부 진입

1. 같은 Wi-Fi의 다른 기기에서 `http://192.168.x.x:8765` 접속
2. S0 + S1 간단 확인

**기대:** UI 표시 및 실행 가능  
**주의:** 인증 없음 → 연구실 LAN만  
**결과:** [ ]

---

## S9. 품질 관점 체크리스트 (실문서 Pilot용)

S1 또는 S3 결과물에 대해 사람이 채점:

| # | 질문 | Y/N |
|---|------|-----|
| 1 | CHANGE_SUMMARY만 보고 무엇이 바뀌려는지 이해되는가 | |
| 2 | REVIEW_REQUIRED가 있으면 이유가 납득되는가 | |
| 3 | updated_*.docx를 열었을 때 원본 대비 의도치 않은 서식 붕괴가 없는가 | |
| 4 | 자동 패치가 없어도 “리뷰로 넘긴 판단”이 합리적인가 | |
| 5 | Writer 적용 후에도 원본 변경 0인가 | |

종합: PASS / PARTIAL / FAIL  
메모: ________________________

---

## 권장 실행 순서 (첫날)

```text
S0 → S1 → S2 → S5 → S6 → S7 → (시간 되면) S3 → S9
```

---

## 결과 기록 템플릿

```text
날짜:
테스터:
환경: Docker / Local
접속 URL:

S0:
S1: run_id=   status=   결과=
S2: 결과=
S3: run_id=   결과=
S4: 결과=
S5: 결과=
S6: original_changed=   결과=
S7: 결과=
S8: 결과=
S9: 종합=

이슈:
1)
2)
```

---

## 참고 경로

| 항목 | 경로 |
|------|------|
| Pilot runs | `data/user_scenarios/_pilot/` |
| Review 산출물 | `_pilot/<run_id>/output/review/` |
| 업데이트 문서 | `_pilot/<run_id>/output/documents/` |
| Writer 결과 | `_pilot/<run_id>/pilot/writer_engine_result.json` |
| Pipeline Writer artifacts | `_pilot/<run_id>/output/writer/` |
