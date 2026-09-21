# B5 Staged Architecture — PR-7 ACU Semantic Integrity 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR8`  
**범위:** ACU Semantic Integrity & Scope Isolation (shadow path ACU 품질)  
**일자:** 2026-07-25

---

## 1. PR-7 목표

PR-6 shadow E2E의 병목이 actual owner activation이 아니라 **ACU 품질**임을 반영해:

- 복수 책임 재분해
- actor / recipient / affected_entity 역할 분리
- ACU별 evidence scope 격리
- 과도한 AMBIGUOUS 완화

를 수행한다. Actual owner / cross-ID / DOCX path는 **변경하지 않는다**.

---

## 2. PR-6에서 관찰된 실패

Account-lock synthetic CR 기준 관찰:

| 문제 | 증상 |
|------|------|
| 복수 책임 병합 | ACU-001에 잠금+알림 혼재 → MULTIPLE_PLAUSIBLE |
| 역할 혼합 | 관리자를 actor로 오인 (실제 recipient) |
| cross-ACU facet 유입 | `로그인` ⊃ `로그` 오탐으로 산출[로그] |
| primary action 누락 | `잠그고`에 `잠금` stem 미매칭 |
| 과도한 AMBIGUOUS | 안내/감사 기록 문장까지 차단 |

---

## 3. Compound Responsibility 문제

한 clause에 서로 다른 action·recipient·책임 유형이 있으면 독립 ACU로 분해한다.

예: `계정을 잠그고 관리자에게 알림` → 잠금 ACU + 알림 ACU

과분리 금지: `이름과 이메일을 저장한다` → 단일 ACU

---

## 4. ACU v2 스키마

`AtomicChangeUnit` 확장 (backward-compatible):

- `recipient`, `affected_entity`
- `facet_origins[]` (`ACU_DIRECT` / `CR_CONTEXT` / `DERIVED_PRIOR`)
- `responsibilities[]` (`AtomicResponsibility`)
- `split_parent_id`, `ambiguity_reason`, `supporting_context`
- provenance: `source_start/end`, `parent_sentence_id`, `parent_change_request_id`

---

## 5. Action / Responsibility 분리 규칙

분리 후보:

- 서로 다른 action
- 서로 다른 recipient/output
- 서로 다른 responsibility type
- notify + state change 복합
- clause/`고` 경계로 안전 분할 가능

유지(비분리):

- 동일 action + 병렬 object (`와/과/및`)
- `또는` / `중 하나` alternative constraint 묶음

안전하지 않으면 `NEEDS_REVIEW`.

---

## 6. Actor / Recipient / Affected Entity 분리

| 역할 | 의미 | 예 |
|------|------|-----|
| actor | 행위 주체 | `시스템이`, `implicit_system` |
| recipient | 알림/안내 수신자 | `관리자에게`, `사용자에게는` |
| affected_entity | 상태 변경 대상 | `계정`, `좌석` |
| object | 직접 적용 대상 | span 내 object hint |
| output | 산출물 | `감사 기록` (span 내만) |

`에게/한테/께` 표지는 actor로 넣지 않는다.

---

## 7. Implicit System Actor 정책

행위 주체 생략 + 기능/자동/상태변경/기록/알림 요구 → `actor=implicit_system`.

생략만으로 AMBIGUOUS 처리하지 않는다.

---

## 8. ACU Scope Isolation

- Direct facet는 **해당 ACU `source_span`에서만** 추출
- `로그인` 내부 `로그` 등 prefix 오탐 차단
- 타 ACU/whole-CR token을 ACU_DIRECT로 사용 금지
- whole-CR 보조 정보는 `supporting_context` (`CR_CONTEXT`)만

---

## 9. Facet Origin Tracking

```text
ACU_DIRECT     — span 직접 추출 (semantic_intent 기본)
CR_CONTEXT     — 전체 CR 보조 / discourse actor 상속
DERIVED_PRIOR  — B3/B4 prior (facet 자체를 바꾸지 않음)
```

---

## 10. AMBIGUOUS 정책 개정

AMBIGUOUS 금지 사유(단독):

- `하며/하고` 종결
- actor 생략
- 복합 명사 나열
- 앞 문장 문법 연결

EXTRACTED 허용: primary action + object/affected + responsibility intent + source span이 있으면.

AMBIGUOUS: 실제 복수 해석.  
NEEDS_REVIEW: 자동 분해가 위험할 때.

---

## 11. Semantic Intent 변경

`semantic_intent_from_acu`는 ACU_DIRECT(+ discourse actor)만 사용.

- primary action 누락 금지
- recipient/actor 혼동 금지
- unrelated output 금지
- whole CR 복사 금지

구조화 API: `semantic_intent_struct_from_acu`.

---

## 12. Before / After Fixture 비교

Account-lock synthetic (하드코드 분리 규칙 없음):

| | PR-6/v1 경향 | PR-7/v2 |
|--|-------------|---------|
| ACU 수 | ~4 (병합) | ≥4–5 (잠금/알림 분리) |
| 잠금 action | 누락 가능 | 존재 |
| 관리자 | actor 오인 | recipient |
| 안내/감사 | AMBIGUOUS | EXTRACTED |
| 산출 로그 유입 | 가능 | 차단 |

Trace: `acu_v1_vs_v2_shadow.json`

---

## 13. Multi-domain Tests

| Domain | CR | 기대 |
|--------|-----|------|
| Inventory | 발주 생성 + 관리자 알림 | 분리 + recipient |
| Reservation | 좌석 갱신 + 대기자 알림 | 분리 + recipient |
| Reporting | 보고서 생성 + 다운로드 | 분리 |
| Account/security | lock fixture | 역할/scope 개선 |

구현은 도메인 키워드 소유권 리스트 없이 일반 stem/격조사 규칙.

---

## 14. Shadow E2E Impact

경로:

```text
CR → improved ACU → B5a → B5b → provenance → owner proposal → shadow B5c → B6
```

Owner score threshold **미조정**. ACU 품질만 개선.

---

## 15. Actual Behavior Parity

불변:

- Actual B3 / B4 / B5
- `allow_mdsr_patch` / patched Req IDs
- DOCX bytes
- Frozen scenario/trial

---

## 16. Full pytest

```text
python -m pytest -q
→ 474 passed in 141.96s (0 failed, 0 skipped)
```

PR-6 기준 457; PR-7 ACU integrity 테스트 +17. 회귀 없음.
---

## 17. Freeze Integrity

미수정 / 재실행 없음:

- scenario-001, b3v2, b4v2, b5v2
- Trial 1 / Trial 2

---

## 18. Known Limitations

- ACU 분해는 여전히 rule-based
- staged path는 shadow only
- actual B3/B4는 whole-CR
- actual owner selection 미전환
- actual DOCX는 whole-CR legacy patch
- final prose generation 미재설계
- frozen unseen scenario에서 owner correctness 미검증
- semantic equivalence validation은 아직 staged-aware 아님

---

## 19. 다음 PR 권고 (PR-8)

후보:

- ACU_DIRECT 품질을 전제로 shadow owner ranking 재평가 (threshold 튜닝 없이)
- 또는 staged-aware semantic validation
- 계속 보류: actual owner switch, cross-ID actual, whole-CR append 제거, Scenario rerun

**최종 판정:** `READY_FOR_STAGED_B5_PR8`

---

## Trace Artifacts

| 파일 | 내용 |
|------|------|
| `atomic_change_units.json` | 기존 + v2 필드 |
| `atomic_change_units_v2.json` | ACU v2 상세 |
| `acu_scope_isolation.json` | direct/context/rejected |
| `acu_v1_vs_v2_shadow.json` | before/after 비교 |
