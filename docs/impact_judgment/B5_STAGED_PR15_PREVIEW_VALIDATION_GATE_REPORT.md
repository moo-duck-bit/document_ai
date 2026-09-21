# B5 Staged Architecture — PR-15 Preview Validation Gate 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR16`  
**범위:** Preview Validation Gate (shadow / observational)  
**일자:** 2026-07-26

---

## 1. Objective

분산된 validation(Requirement Patch / Language Realizer / Activation / Preview)을  
통합하여 **향후 DOCX 반영 여부**를 결정할 중앙 품질 Gate를 추가한다.

- DOCX **미수정**
- 선행 단계 artifact **비파괴** (observational)
- `eligible_for_docx_activation`은 PASS에서만 true (실제 write 없음)

```text
… → Activation Preview → Preview Validation Gate
```

---

## 2. Architecture

모듈: `src/document_ai/impact/preview_validation_gate.py`

| API | 역할 |
|-----|------|
| `evaluate_preview_gate_item` | patch 단위 PASS/REVIEW/BLOCK |
| `build_preview_gate_results` | deterministic 목록 생성 |
| `validate_preview_gate_results` | gate invariants / negative 탐지 |
| `build_preview_gate_summary` | global 집계 |
| `compare_gate_vs_activation` | side-by-side |
| `run_preview_validation_gate` | 오케스트레이션 |

Runner는 Preview artifact 기록 직후 Gate를 호출하고,  
기존 Preview/Activation/Language/Patch 결과를 mutate하지 않는다.

---

## 3. Gate Inputs

1. Requirement Patch validation  
2. Language Realizer validation (`rejected`, `semantic_changed`, `meaning_preserved`)  
3. Activation Decision  
4. Activation Preview entry / validation / aggregated conflict  
5. DOCX / Legacy 불변 플래그  
6. artifact 누락 · trace id 불일치

---

## 4. PASS / REVIEW / BLOCK Rules

**PASS** (전부 충족): Patch VALID, Language VALID, semantic_changed=false, meaning_preserved=true, rejected=false, AUTO_APPLY, preview applied, preview VALID, conflict/missing/duplicate 없음, docx/legacy unchanged.

**REVIEW**: Language REVIEW/rejected/warning, Activation REVIEW, missing decision(미적용), conflict+원문보존, duplicate anomaly, patch REVIEW/WARNINGS 등.

**BLOCK**: Activation BLOCK, Patch/Preview INVALID, 비정상 apply(BLOCK/REVIEW/missing이 적용됨), AUTO_APPLY 미적용, conflict 원문 미보존, semantic_changed, meaning 미보존, docx/legacy changed, unknown state, artifact 누락, trace id mismatch.

판정 불가 → **BLOCK** (fail-closed).

---

## 5. Precedence

`BLOCK > REVIEW > PASS`

예: AUTO_APPLY + Language REVIEW_REQUIRED → REVIEW  
AUTO_APPLY + semantic_changed → BLOCK  
REVIEW + actual_docx_changed → BLOCK

---

## 6. Reason Codes

`PASS_ALL_VALID`, `PATCH_INVALID`, `LANGUAGE_REVIEW_REQUIRED`, `LANGUAGE_REJECTED`, `SEMANTIC_CHANGED`, `MEANING_NOT_PRESERVED`, `ACTIVATION_REVIEW`, `ACTIVATION_BLOCK`, `PREVIEW_NOT_APPLIED`, `NON_AUTO_APPLY_WAS_APPLIED`, `BLOCK_WAS_APPLIED`, `MISSING_DECISION_APPLIED`, `PREVIEW_INVALID`, `PREVIEW_CONFLICT`, `CONFLICT_DID_NOT_PRESERVE_ORIGINAL`, `DUPLICATE_ANOMALY`, `TRACE_ID_MISMATCH`, `ACTUAL_DOCX_CHANGED`, `ACTUAL_GENERATION_CHANGED`, `UNKNOWN_STATE`, `MISSING_ARTIFACT`, …

---

## 7. Gate Schema

`PreviewGateResult`: ids, per-stage statuses, conflict/missing/duplicate flags, `final_status`, `reason_codes`/`reason_messages`, `eligible_for_docx_activation` (PASS only).

---

## 8. Global Invariants

`pass_only_when_all_valid`, precedence, only PASS eligible, blocked/review/missing not applied, conflict handling, semantic/meaning never PASS, docx/legacy unchanged, deterministic, trace consistency.

---

## 9. Current Scenario Result

Gate 자체는 숫자를 하드코딩하지 않는다.  
시나리오형 입력(AUTO_APPLY N + BLOCK 1)에 대해:

- `pass_count == AUTO_APPLY 수`
- `block_count == BLOCK 수`
- global_status = BLOCK (BLOCK 존재 시)

단위 테스트 `test_24_scenario_like_eleven_pass_one_block`: **11 PASS / 1 BLOCK**.

---

## 10. Negative Test Result

강제 이상 상태(UNKNOWN, BLOCK applied, REVIEW+eligible, semantic PASS, meaning PASS, docx changed, id mismatch)를 `validate_preview_gate_results` / evaluate 경로에서 탐지. 통과.

---

## 11. Determinism

동일 입력 → 동일 결과·동일 정렬 (`atomic_change_id`, `patch_id`, `document`, `requirement_id`, `field`).

---

## 12. Artifacts

| File | Content |
|------|---------|
| `output/trace/preview_gate_results.json` | per-patch results + invariants |
| `output/trace/preview_gate_summary.json` | PASS/REVIEW/BLOCK + reason 집계 |
| `output/trace/preview_gate_vs_activation.json` | activation vs gate side-by-side |

`actual_docx_changed=false`, `actual_generation_changed=false`.

---

## 13. Full pytest

```text
python -m pytest -q
→ 609 passed in 209.86s (0 failed, 0 skipped)
```

PR-14.1 기준 577; PR-15 gate 테스트 +32. 회귀 없음.
---

## 14. Compatibility

변경 금지 유지: ACU, B3–B5, Patch Contract, Semantic Draft, Requirement Patch 의미, Language Realizer 규칙, Activation Policy/Preview 규칙, DOCX, Legacy, Scenario-001 freeze.

허용: Gate 모듈 + runner orchestration + tests + report.

---

## 15. Freeze

Scenario-001 / Trials **미재실행·미수정**. Freeze 유지.

---

## 16. Known Limitations

- Gate는 observational — DOCX write 없음
- PASS eligible ≠ 실제 반영
- Preview validation status가 전역 INVALID이면 모든 항목 BLOCK 가능
- 실제 시나리오 수치는 runner 재실행 artifact 기준으로 확인 (frozen 미재실행)

---

## 17. Next PR Recommendation (PR-16)

- feature-flag dual-write / human review UI for PASS-only
- Gate global_status를 runner fail-loud 옵션으로 승격
- DOCX cutover는 별도 승인 후에만

**Final judgment:** `READY_FOR_STAGED_B5_PR16`
