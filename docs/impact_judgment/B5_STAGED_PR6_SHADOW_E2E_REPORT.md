# B5 Staged Architecture — PR-6 Shadow End-to-End 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR7`  
**범위:** ACU + Cross-ID discovery + Provenance + B5a/b/c + B6를 **shadow-only** staged decision path 하나로 연결  
**일자:** 2026-07-25

---

## 1. PR-6 목표

지금까지 분리 구현된 shadow 컴포넌트를 비교·평가용 **Shadow End-to-End Staged Decision Path** 하나로 연결한다.

> **Shadow Patch Plan ≠ Actual DOCX Mutation.**  
> Actual 경로(B3 → B4 → same-ID B5 → legacy whole-CR DOCX)는 변경하지 않는다.

---

## 2. 이전 독립 Shadow 컴포넌트

| PR | 컴포넌트 | PR-6에서의 역할 |
|----|----------|-----------------|
| PR-1 | B5a / B5b / B5c 인터페이스 | ACU별 alignment + shadow `decide_propagation` |
| PR-2 | Cross-ID Design Candidate Discovery | ACU별 shadow 후보 풀 |
| PR-3 | Evidence Provenance / Lineage | 쌍 단위 DIRECT/SUPPORTING/GENERIC/DERIVED/CONFLICTING |
| PR-4 | Atomic Change Units | 오케스트레이션용 독립 변경 단위 |
| PR-5 | B6 Semantic Patch Planning | CLEAR_OWNER + PATCH/EXTEND 시 ACU 범위 계획 |

---

## 3. Staged Shadow E2E 아키텍처

모듈: `src/document_ai/impact/staged_shadow_e2e.py`  
진입점: `run_staged_shadow_e2e(...)`

```text
CR
 ↓
Atomic Change Units (PR-4)
 ↓  (ACU별 독립 처리)
ACU-aware candidate context
 ↓
B5a Design Candidate Discovery (same_id + b3_impacted_mddr + allowed uncertain)
 ↓
B5b Responsibility Alignment (ACU source_span 기준, whole CR 아님)
 ↓
Evidence Provenance / Lineage (PR-3)
 ↓
Shadow Owner Recommendation (분석 전용)
 ↓
B5c Shadow Propagation Decision (actual과 분리)
 ↓
B6 Semantic Patch Planning (ACU semantic_intent)
 ↓
Shadow Patch Plan + Legacy vs Staged 비교
```

Actual 경로는 유지:

```text
CR → B3 whole-CR → B4 → B5 same-ID → legacy whole-CR patch → DOCX
```

---

## 4. ACU 오케스트레이션

각 ACU는 자체 파이프라인을 실행한다. Whole-CR B5 결과를 모든 ACU에 **복사하지 않는다**.

ACU별 처리:

1. requirement context에 대해 후보 탐색 (B3/B4는 **prior context만**)
2. ACU span ↔ design alignment
3. provenance 요약
4. owner status 추천
5. `shadow_decision` 생성
6. 정당화되면 B6 plan 생성

B3 IMPACTED / B4 CONSISTENT를 ACU owner로 **자동 가정하지 않는다**.

---

## 5. Candidate Discovery 통합

ACU별 평가 소스 (shadow only):

- `same_id`
- `b3_impacted_mddr`
- PR-2의 allowed uncertain / 기타 shadow pool 항목

Actual owner 선택·DOCX mutation에는 **사용하지 않는다**.

---

## 6. Provenance 통합

각 ACU → design candidate 쌍에 기록:

- DIRECT / SUPPORTING / GENERIC / DERIVED(prior) / CONFLICTING
- unique independent groups (lineage 인식; stage 간 이중 집계 금지)

CLEAR_OWNER는 추가로 design 내 **non-weak** ACU action/object hit(`_strong_acu_hits`)를 요구한다. Generic-token 또는 prior-only evidence만으로는 owner를 clear할 수 없다.

---

## 7. Owner Recommendation 스키마

```text
ShadowOwnerProposal:
  atomic_change_id
  candidates[]
  recommended_owner          # 분석 전용; actual patch owner 아님
  recommendation_status      # CLEAR_OWNER | MULTIPLE_PLAUSIBLE |
                             # NO_SAFE_OWNER | NEEDS_REVIEW
  evidence / reason
  shadow_decision
```

CLEAR_OWNER 조건:

- discriminative(non-weak) responsibility evidence
- generic-only 아님
- prior-only 아님
- 지배적 conflicting evidence 없음
- 다른 후보 대비 책임 연결이 설명 가능

단독 CLEAR 사유로 금지: same-ID, confidence 하나만 높음, generic overlap, B3/B4 prior만, weak lexical overlap.

---

## 8. B5c Shadow Decision

Actual B5c와 분리. 값:

| Decision | 대표 트리거 |
|----------|-------------|
| PATCH_EXISTING / EXTEND_EXISTING | CLEAR_OWNER + alignment |
| NEW_DESIGN_CANDIDATE | NO_SAFE_OWNER 경로 |
| SKIP | 실행 가능한 후보 없음 |
| NEEDS_REVIEW | MULTIPLE_PLAUSIBLE / 모호 |

필드명: `shadow_decision` (actual `propagation_decision`을 덮어쓰지 않음).

---

## 9. B6 통합

| Owner status | B6 shadow 동작 |
|--------------|----------------|
| CLEAR_OWNER + PATCH/EXTEND | PLANNED plans; ACU 기반 `semantic_intent` |
| MULTIPLE_PLAUSIBLE | NEEDS_REVIEW plan |
| NO_SAFE_OWNER | NEW_DESIGN / REVIEW plan |
| SKIP | plan 없음 |

Whole-CR 텍스트를 `semantic_intent`에 복사하지 않는다.

---

## 10. Legacy vs Staged 비교

| Legacy (actual) | Staged shadow |
|-----------------|---------------|
| Whole CR → same-ID owners → whole-CR append | ACU-N → candidate designs → owner status → shadow decision → ACU-scoped plan |

산출물: `output/trace/legacy_vs_staged_shadow.json`  
Scenario-001 hard-code 없음.

---

## 11. Safety Invariants

코드/테스트로 강제:

| ID | Invariant |
|----|-----------|
| A | Shadow가 actual `propagation_decision`을 바꾸지 않음 |
| B | Shadow가 `allow_mdsr_patch`를 바꾸지 않음 |
| C | Shadow가 patched Req IDs를 바꾸지 않음 |
| D | Shadow가 DOCX bytes/hash를 바꾸지 않음 |
| E | Frozen scenario/trial artifact 미수정 |

---

## 12. Synthetic Tests

`tests/test_b5_staged_pr6_shadow_e2e.py`

| ID | 케이스 |
|----|--------|
| A | One ACU + same-ID true owner → CLEAR_OWNER |
| B | Same-ID false + stronger cross-ID → cross-ID 추천; actual 불변 |
| C | Multiple plausible → MULTIPLE_PLAUSIBLE |
| D | No safe owner → NO_SAFE_OWNER / NEW_DESIGN 또는 REVIEW |
| E | Generic-only → CLEAR_OWNER 금지 |
| F | Prior-only → CLEAR_OWNER 금지 |
| G | Multi-ACU CR → ACU별 다른 recommendation |
| H | One ACU → multiple artifact plans |
| I | Provenance lineage end-to-end 보존 |
| J | Legacy actual outputs 불변 |
| K | Deterministic execution/order |

다중 도메인: Inventory / Reservation / Reporting fixture (medical/security만 사용하지 않음).

---

## 13. Full pytest

```text
python -m pytest -q
→ 457 passed in 157.84s (0 failed, 0 skipped)
```

PR-5 기준 443; PR-6 staged shadow E2E 테스트 +14. 회귀 없음.

---

## 14. Freeze Integrity

미수정 / 재실행 없음:

- `scenario-001` (+ b3v2 / b4v2 / b5v2 rerun)
- Trial 1 / Trial 2

Scenario-001 keyword rule·threshold tuning 없음.

---

## 15. Known Limitations

- staged path는 **shadow only**
- actual path는 legacy / same-ID 유지
- actual owner selection **미전환**
- actual DOCX는 여전히 legacy whole-CR patch
- ACU-aware actual B3/B4 **미활성**
- final prose generation 미재설계
- semantic validation은 아직 staged-aware 아님
- `recommended_owner`는 DOCX mutation에 절대 사용 금지

---

## 16. 다음 PR 권고 (PR-7)

후보 다음 단계 (게이트 유지, Scenario hard-code 금지):

- CLEAR_OWNER shadow plan의 feature-flag **preview** 또는 dual-write 비교 메트릭
- 또는 ACU intent 대상 staged-aware semantic validation
- 계속 보류: actual owner switch, cross-ID actual 활성화, whole-CR append 제거, Scenario rerun

**최종 판정:** `READY_FOR_STAGED_B5_PR7`

---

## Trace Artifacts (runner)

| 파일 | 내용 |
|------|------|
| `staged_shadow_execution.json` | E2E 전체 결과 + `table_rows` + CR summary |
| `acu_owner_candidates_shadow.json` | ACU별 후보 풀 |
| `acu_owner_recommendations_shadow.json` | Owner proposal + 집계 |
| `staged_patch_plan_shadow.json` | staged path의 B6 plans |
| `legacy_vs_staged_shadow.json` | Actual vs shadow decision 대비 |

연결 체인: CR span → ACU → requirement context → design candidates → evidence lineage → alignment → owner recommendation → shadow decision → patch plan.
