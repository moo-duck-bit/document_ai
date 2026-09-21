# Trial 2 — Lockout Multi-Requirement (A1) — FROZEN

> status: **FROZEN / PASS**  
> trial_id: `trial-002-lockout-multireq`  
> overall_result: **PASS** (`Acceptance Criteria Met`)  
> based_on: Trial 1 `trial-001-mindrium-xa` (**FROZEN**, 읽기 전용)

## PASS 의미 (한정)

기존 문서에 대한 자연어 변경 요청에서 관련 요구사항 후보를 찾고,  
영향·의미 충돌을 분리 판단한 뒤, MDSR→MDDR 전파를 **이 lockout multi-req 시나리오에서** 검증함.

일반화·North Star E2E 달성으로 해석하지 말 것. 한계는 `FINAL_TRIAL_REPORT.md` 참고.

## 읽기 전용 진입점

| 문서 | 용도 |
|------|------|
| `FINAL_TRIAL_REPORT.md` | 최종 판정·증거·한계 |
| `FREEZE.md` | Freeze 규칙·산출물 트리 |
| `execution_report.json` | `overall_result`, evidence hashes |
| `ACCEPTANCE_CRITERIA.md` | 고정 AC |
| `validation/propagation/AC_STATUS.json` | AC 8/8 PASS |

**수정·재패치·재실행 금지.** 다음 Trial은 별도 설계 승인 후.
