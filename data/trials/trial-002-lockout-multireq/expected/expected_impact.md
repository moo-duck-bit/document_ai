# Trial 2 Expected Impact Table (A1)

> **용도:** Trial 2 평가용 expected impact 기준  
> **아님:** 모델/검색기에 정답을 주입하는 gold force-feed  
> case: Mindrium XA · documents: MDSR / MDDR (XXCS out of scope)

---

## 1. 요약 표

| ID | Document | Semantic role | Expected judgment | Expected action | Notes |
|----|----------|---------------|-------------------|-----------------|-------|
| Req. 6 | MDSR | 사용자 UX / 잠금·재시도 **안내** | impacted | update UX-oriented fields only (설명·기준 중 안내 관련); 제목·목적과 정합 유지 | Trial 1은 설명만 잠금 정책으로 바꿔 충돌 → Trial 2는 consistency gate 대상 |
| Req. 105 | MDSR (+ MDDR 설계) | 로그인 실패 횟수·임계치·**계정 잠금 정책** | impacted | 정책·잠금·자동 해제 관련 내용 반영 후보 | **첫 검증 포인트:** retrieval top-k에 포함 |
| Req. 103 | MDSR (+ MDDR 설계) | 보안 이벤트 / **감사 기록** | impacted | 실패·잠금·해제 이벤트 감사 범위 확장 후보 | CR 마지막 문장과 직접 연결 |
| Req. 102 | MDSR/MDDR | 인증·토큰 | uncertain → often not_impacted | 기본은 skip; 토큰 무효화와 잠금 연동 시에만 재검토 | IA-07 peer이나 이번 CR 중심 아님 |
| Req. 201 | MDSR/MDDR | 대시보드 인증 | not_impacted (default) | SKIPPED_WITH_REASON | 모바일 잠금 정책과 약관련 |
| IA-07 | XXCS/trace | 연속 로그인 실패 시 로그인 제한 | supporting evidence | traceability hint only (XXCS 패치 제외) | Req.6·105·201 등과 연결 |

---

## 2. MDDR 설계

| Design block | Linked req | Expected judgment | Action rule |
|--------------|------------|-------------------|-------------|
| MDDR Req. 6 | Req. 6 | impacted or uncertain | UX 안내 설계만 조정 후보; 정책 본체는 105 |
| MDDR Req. 105 | Req. 105 | **impacted** | 연속 실패·임계치·잠금 이벤트 설계 갱신 후보 → **PATCHED** 또는 범위 밖이면 **SKIPPED_WITH_REASON** |
| MDDR Req. 103 | Req. 103 | impacted | 감사 대상에 잠금/해제 포함 여부 판단 → PATCHED / SKIPPED_WITH_REASON |

**규칙:** MDDR에 대해 “아무 기록 없이 no-op” 금지. 반드시:

- `PATCHED`, 또는  
- `SKIPPED_WITH_REASON` (+ reason 문자열)

---

## 3. Retrieval 성공 기준 (expected, 주입 아님)

| Check | Criterion |
|-------|-----------|
| R1 | Exact-ID 없이도 후보 집합에 **Req. 105** 포함 |
| R2 | **Req. 6**, **Req. 103** 중 최소 하나가 top-k에 포함 (권장: 둘 다) |
| R3 | 각 후보에 document, score, evidence snippet, rank 기록 |
| R4 | retrieval ≠ impact: 후보 중 not_impacted / uncertain 가능 |

---

## 4. Consistency (Req. 6)

변경 후 Req.6 **제목 · 설명 · 목적 · 기준**이 서로 모순이면:

- 자동 강행 patch 금지  
- `consistency_warning` 또는 remapping 대상으로 기록  

Expected: Trial 1형 “설명=잠금 정책 / 제목=인증 에러 UX” 재발 시 **FAIL**.

---

## 5. JSON 스키마 (평가용, optional machine-readable)

`expected_impact.json` 참고.

---

## 6. 고정 원칙

- 실행 중 이 표를 “통과시키기 위해” 축소·완화하지 않음  
- Trial 1 DOCX를 재패치해 성공으로 만들지 않음  
- 실패 시 그대로 freeze
