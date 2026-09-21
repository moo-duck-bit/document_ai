# Final Trial Report — Trial 2 (Frozen)

> **Trial 2 Freeze: `true`**  
> trial_id: `trial-002-lockout-multireq`  
> scenario: **A1 lockout multi-requirement**  
> frozen_at: `2026-07-22T22:13:01Z` (see `execution_report.json`)  
> **Do not modify code, DOCX, or re-run pipelines to improve this result.**

## PASS/FAIL Decision

**Overall: PASS**

### Reason

**Acceptance Criteria Met**

PASS의 의미는 다음으로 **한정**한다:

> 기존 문서에 대한 자연어 변경 요청에서 의미적으로 관련된 요구사항 후보를 찾고,  
> 실제 영향 여부와 의미 충돌을 분리 판단한 뒤,  
> 안전하게 MDSR→MDDR 변경 전파를 수행할 수 있음을 **해당(lockout multi-req) 시나리오에서** 검증함.

이 PASS를 일반 Form-fill North Star 달성, dense semantic retrieval 완성, 또는 모든 문서 변경 유형의 일반화 성공으로 해석하지 않는다.

---

## Trial Objective

Trial 1에서 실패한 **의미 정합성**과 **MDDR 설계 전파**를, Exact-ID에 의존하지 않는 multi-requirement 변경 시나리오에서 재검증한다.

구현 검증(Implementation Validation) 범위:

- Semantic / hybrid retrieval
- Impact judgment (retrieval과 분리)
- Semantic consistency gate (patch 전)
- MDSR→MDDR propagation with explicit PATCHED / SKIPPED_WITH_REASON

## Hypothesis

Natural-language change request로부터 Exact-ID 없이 의미적으로 관련된 요구사항·설계 후보를 찾고,  
영향 판단·의미 충돌·전파를 단계별로 분리하며 추적 가능하게 남길 수 있는가?

## Scenario

**A1 — Lockout Multi-Requirement (Mindrium XA)**

- CR (`input/change_request.txt`): 연속 로그인 실패 시 계정 잠금, 관리자 알림/승인·자동 해제, UX 안내, 감사 기록  
- **Exact-ID 없음** (Req. 6 / 103 / 105 미포함)
- Documents: MDSR + MDDR (XXCS out of scope)
- Expected impact는 **평가 전용** (retrieval/ranking/judgment에 미주입)

---

## Acceptance Criteria

고정 기준: `ACCEPTANCE_CRITERIA.md`  
Post-hoc 평가: `validation/propagation/AC_STATUS.json` (8/8 PASS)

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Exact-ID 없이도 관련 Req 후보 검색 | **PASS** |
| 2 | Req.105 retrieval 후보 포함 | **PASS** |
| 3 | Retrieval ≠ Impact Judgment 분리 | **PASS** |
| 4 | Semantic consistency (Req 내부 모순 탐지/차단) | **PASS** |
| 5 | MDDR PATCHED 또는 SKIPPED_WITH_REASON | **PASS** |
| 6 | Propagation trace JSON | **PASS** |
| 7 | 원본 문서 구조 보존 (patch-in-place) | **PASS** |
| 8 | Cross-document propagation trace | **PASS** |

---

## Execution Summary

| Stage | Outcome | Artifact root |
|-------|---------|---------------|
| B1–B2 Lexical baseline | Frozen (not overwritten) | `retrieval/lexical_baseline/` |
| Hybrid retrieval | lexical / semantic(TF-IDF) / hybrid 비교 | `retrieval/hybrid/` |
| B3 Impact judgment | IMPACTED / NOT_IMPACTED / UNCERTAIN | `validation/impact_judgment/` |
| B4 Consistency gate | CONSISTENT / CONFLICT / NEEDS_REVIEW | `validation/semantic_consistency/` |
| B5 Propagation | PATCHED / SKIPPED_WITH_REASON | `validation/propagation/` + `generated/` |

Pipeline (증거 경로):

```
CR
 → Retrieval (hybrid)
 → Impact Judgment (B3)
 → Consistency Gate (B4)
 → Propagation / Patch (B5)
 → AC post-hoc
```

---

## Retrieval Results

Hybrid Top focus (document-aware; same ID not collapsed):

| Req | Doc | lexical | semantic | hybrid |
|-----|-----|--------:|---------:|-------:|
| Req.105 | MDSR | 13 | 8 | 8 |
| Req.105 | MDDR | 1 | 1 | 1 |
| Req.103 | MDSR | 2 | 3 | 2 |
| Req.103 | MDDR | 4 | 2 | 3 |
| Req.6 | MDSR | 3 | 5 | 5 |

- Req.6 / 103 / 105 recall 유지
- Top-5 FP 예: Req.101 (retrieval에 잔존) → **B3에서 NOT_IMPACTED**로 분리
- Semantic channel: **TF-IDF cosine** (dense embedding 아님)

Evidence: `retrieval/hybrid/comparison.json`, `COMPARISON.md`

## Impact Judgment Results (B3)

Focus:

| Candidate | Judgment |
|-----------|----------|
| MDDR/MDSR Req.105 | IMPACTED |
| MDSR/MDDR Req.103 | IMPACTED |
| MDSR/MDDR Req.6 | IMPACTED |
| MDSR/MDDR Req.101 | NOT_IMPACTED |

- IMPACTED ≠ 자동 patch 허용
- ID 동일만으로 IMPACTED 처리하지 않음 (테마·점수 근거)

Evidence: `validation/impact_judgment/decisions.json`

## Consistency Gate Results (B4)

| Req | Status | Auto-patch |
|-----|--------|------------|
| Req.105 | CONSISTENT | Yes |
| Req.103 | CONSISTENT | Yes |
| Req.6 | **CONFLICT** | **No** |

**Req.6 CONFLICT (Trial 1 재발 방지 핵심):**  
title/purpose = 인증 에러 UX vs CR = 계정 잠금 **정책** → 설명 덮어쓰기 시 내부 의미 충돌.  
정책은 Req.105로 매핑; Req.6 UX criteria 자동 보강은 의도적 skip.

Evidence: `validation/semantic_consistency/consistency_decisions.json`, `CONSISTENCY_REPORT.md`

## Propagation Results (B5)

| MDSR → MDDR | Outcome | MDSR patched |
|-------------|---------|--------------|
| 105 → 105 | **PATCHED** | Yes |
| 103 → 103 | **PATCHED** | Yes |
| 6 → 6 | **SKIPPED_WITH_REASON** | No |

- 동일 ID만으로 자동 전파하지 않음 (design responsibility 정렬 필요)
- MDDR 조용한 no-op 없음
- Diff: `validation/propagation/patch_diffs.json`, `PATCH_DIFFS.md`
- Outputs: `generated/patched_mdsr/output_mdsr.docx`, `generated/patched_mddr/output_mddr.docx`

---

## Evidence (canonical — do not modify)

| Path | Role |
|------|------|
| `input/change_request.txt` | NL CR (no Exact-ID) |
| `retrieval/lexical_baseline/` | B1–B2 lexical freeze |
| `retrieval/hybrid/` | Hybrid compare freeze |
| `validation/impact_judgment/` | B3 freeze |
| `validation/semantic_consistency/` | B4 |
| `validation/propagation/` | B5 + AC |
| `generated/patched_mdsr/`, `generated/patched_mddr/` | Patch outputs |
| `execution_report.json` | Machine-readable freeze + hashes |
| `ACCEPTANCE_CRITERIA.md` | Fixed AC |

Hashes: see `execution_report.json` → `canonical_evidence`.

---

## What Trial 2 Solved (vs Trial 1 FAIL items)

| Trial 1 FAIL | Trial 2 outcome |
|--------------|-----------------|
| 의미적 일관성 (Req.6 설명←정책 / 제목=UX 충돌) | B4 CONFLICT로 탐지·잘못된 patch 차단 |
| 요구사항 영향 식별 (Exact-ID only) | Exact-ID 없이 6/103/105 multi-req 후보 + B3 분리 판단 |
| 설계 전파 (MDDR 조용한 no-op) | 105/103 PATCHED, 6 SKIPPED_WITH_REASON + full trace |

Trial 1이 보여 준 **patch-in-place / 구조 보존** 능력은 유지하면서, 위의 실패 축을 본 시나리오에서 검증했다.

## Remaining Limitations (do not over-generalize PASS)

1. lockout multi-req **시나리오 1개**에 대한 검증
2. Semantic retrieval = **TF-IDF**, not dense embedding
3. B3/B4 = **rule/theme heuristic** 의존
4. **NEEDS_REVIEW** 경로의 실사례 검증 부족
5. Req.6 UX criteria 보강은 자동 미반영 (의도적 skip)
6. **XXCS** 전파 미검증
7. **신규 요구사항 생성** 시나리오 미검증
8. 빈 양식 + 새 케이스 **end-to-end Form-fill 품질**은 North Star 수준 미검증

## Lessons Learned

1. Retrieval 성공 ≠ patch 허용 — Judgment와 Consistency Gate가 필수 계층이다.
2. Trial 1형 실패는 “못 찾아서”가 아니라 “잘못된 필드에 정책을 넣어” 발생할 수 있다 → B4가 핵심이다.
3. MDDR은 PATCHED 또는 SKIPPED_WITH_REASON으로 **명시 종료**해야 하며, SHA 동일만으로 성공을 주장하면 안 된다 (Trial 1 교훈).
4. Hybrid(TF-IDF)는 MDSR Req.105 rank를 개선했지만 FP(Req.101)는 judgment가 걸러야 한다.
5. PASS는 시나리오 한정 증거이며, 다음 Trial에서 일반화 가설을 별도로 세워야 한다.

## Next Trial Recommendation

구현하지 않음. 후보만 기록 (선택용):

1. **Trial 3a — Dense / document-aware retrieval hardening**  
   목적: TF-IDF 한계·MDSR Req.105 rank·FP demotion을 dense embedding + document-type priors로 재검증.

2. **Trial 3b — NEEDS_REVIEW / UX-only refine path**  
   목적: CONFLICT가 아닌 경계 케이스와 Req.6 UX criteria 선택적 보강, NEEDS_REVIEW 실사례 확보.

3. **Trial 3c — XXCS (or new-req) propagation slice**  
   목적: 설계 이후 검증 문서(또는 신규 Req 생성)로의 전파·skip 규칙을 최소 수직 슬라이스로 검증.

North Star(빈 양식 + 새 케이스 E2E)는 위 슬라이스들이 쌓인 뒤의 별도 Trial로 두는 것을 권장한다.

---

## Trial 2 Freeze

종료. 추가 수정·재패치·재실행으로 결과를 “더 좋게” 만들지 않는다.  
다음 작업은 새 Trial 설계 승인 후에만 시작한다.
