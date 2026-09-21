# B5 Staged Architecture — PR-16 DOCX Activation Writer 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR17`  
**범위:** Feature-Flag DOCX Activation Writer (PASS-only, copy-out)  
**일자:** 2026-07-26

---

## 1. Objective

Preview Validation Gate에서 `PASS` + `eligible_for_docx_activation=true`인 항목만  
**별도 DOCX 복사본**에 제한 반영할 수 있는 Writer를 추가한다.

- Feature Flag 기본 **OFF**
- 원본 DOCX **in-place 수정 금지**
- REVIEW/BLOCK **절대 미적용**
- Gate 판정 **재해석 금지**

```text
Preview Validation Gate
  → DOCX Activation Plan
  → (flag ON일 때만) activated copy write
  → DOCX Activation Validation
```

---

## 2. Architecture

모듈: `src/document_ai/impact/docx_activation_writer.py`

| API | 역할 |
|-----|------|
| `build_docx_activation_plan` | 적용/skip 계획 |
| `validate_docx_activation_plan` | plan invariants |
| `apply_docx_activation_plan` | 복사본 write |
| `validate_activated_docx` | 출력 검증 |
| `build_docx_activation_summary` | 집계 |
| `compare_activated_docx_vs_preview` | preview 대조 |
| `run_docx_activation_writer` | 오케스트레이션 |

Runner는 Gate 직후 plan/results artifacts를 항상 기록하고,  
환경변수/flag 기본값으로 write는 수행하지 않는다.

---

## 3. Feature Flag

| Env | Default |
|-----|---------|
| `DOCX_ACTIVATION_ENABLED` | `false` |
| `DOCX_ACTIVATION_POLICY` | `strict_global` |

OFF: plan만 생성, `write_attempted=0`, output DOCX 0, source hash 불변.

---

## 4. Execution Policies

| Policy | 동작 |
|--------|------|
| `strict_global` (기본) | `global_status=PASS`일 때만 write |
| `eligible_only` | global BLOCK이어도 개별 PASS만 plan/write |

현재 Scenario형 global BLOCK → 기본 설정에서 write 0건.

---

## 5. PASS-only Eligibility

필수:

- `final_status=PASS`
- `eligible_for_docx_activation=true`
- `activation_decision=AUTO_APPLY`
- `preview_applied=true`
- patch/language VALID
- docx/generation unchanged flags false

REVIEW/BLOCK/unknown/누락 → skip (fail-closed).

---

## 6. Activation Plan

Plan과 write 분리. Plan-only 시 `actual_docx_changed=false`.

---

## 7. Locator Strategy

우선: `requirement_id + field` (Req 표 `설명` 셀 등) → exact `before_text` → normalized exact.

- match=1 → 적용 가능
- 0 또는 >1 → skip (`TARGET_NOT_FOUND` / `TARGET_AMBIGUOUS`)
- fuzzy / 임의 선택 **금지**

---

## 8. Supported Operations

허용: `UPDATE`, `CONSTRAIN`, `REPLACE`  
비활성: `ADD`, `DELETE`, `LINK` → `UNSUPPORTED_DOCX_OPERATION`

---

## 9. Atomic Write

원본 hash 기록 → 임시 복사 → patch → reopen → atomic rename → output hash.  
실패 시 원본 유지, 불완전 출력 제거.

출력명: `<stem>__activated_pr16.docx` (충돌 시 `_001`…).

---

## 10. Formatting Preservation

단일 run 내부 exact replace만 허용. multi-run span → `FORMAT_PRESERVATION_UNSAFE` skip.  
`cell.text=` 전체 재할당 지양.

---

## 11. Validation Invariants

source hash 불변, PASS만 write, REVIEW/BLOCK 미적용, flag OFF 시 output 0, preview 일치, unrelated 보존 등.

---

## 12. Current Scenario Default Result

flag=false, policy=strict_global, global BLOCK:

- write 0 / output 0 / source 불변 / plan+trace 유지

---

## 13. Explicit eligible_only Test

flag=true + eligible_only + global BLOCK → PASS 항목만 plan/write, BLOCK skip.

---

## 14. Negative Tests

illegal BLOCK write, source hash drift, unsupported op, locator 0/>1, multi-run unsafe, overwrite 거부.

---

## 15. Artifacts

| File |
|------|
| `output/trace/docx_activation_plan.json` |
| `output/trace/docx_activation_results.json` |
| `output/trace/docx_activation_summary.json` |
| `output/trace/docx_activation_vs_preview.json` |
| `output/trace/docx_activation_validation.json` |

활성 출력(있을 때만): `output/activated/*__activated_pr16.docx`

---

## 16. Full pytest

```text
python -m pytest -q
→ 633 passed in 214.07s (0 failed, 0 skipped)
```

PR-15 기준 609; PR-16 DOCX activation writer 테스트 +24. 회귀 없음.
---

## 17. Compatibility

Gate/Preview/Policy/Realizer/Patch 의미 미변경. Legacy generation 경로 미교체.  
Scenario-001 freeze 유지.

---

## 18. Source DOCX Non-Mutation

원본 SHA-256 불변을 validation으로 강제. 출력은 `activated/`만.

---

## 19. Freeze

Scenario-001 / Trials 미재실행·미수정.

---

## 20. Known Limitations

- ADD/DELETE/LINK 미지원
- multi-run 텍스트 미지원 (skip)
- MDSR 표 필드 중심 locator (MDDR paragraph는 후속 확장)
- flag OFF가 기본 — 실제 규제 문서에 자동 반영하지 않음

---

## 21. Next PR Recommendation (PR-17)

- MDDR paragraph locator 강화
- dual-write review UI
- flag gated cutover checklist
- ADD 구조 변경은 별도 승인 PR

**Final judgment:** `READY_FOR_STAGED_B5_PR17`
