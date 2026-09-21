# B5 Staged Architecture — PR-13 Activation Preview 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR14`  
**범위:** Activation Preview Builder (shadow only)  
**일자:** 2026-07-26

---

## 1. Objective

Activation Policy에서 `AUTO_APPLY`로 결정된 Requirement Patch만 선별하여,  
실제 DOCX/Legacy 적용 **직전** 상태를 보여주는 Preview Artifact를 생성한다.

- DOCX **미수정**
- Legacy generation **유지**
- Requirement Patch / Activation Policy **미변경**
- Preview는 **shadow artifact만** 생성

```text
Requirement Patch → Activation Policy → Preview Builder
   ├─ AUTO_APPLY → Preview 반영
   ├─ REVIEW     → 원문 유지 + review_queue
   └─ BLOCK      → 원문 유지 + blocked_queue
→ Preview Validation → Legacy 비교 (관찰)
```

---

## 2. Architecture

모듈: `src/document_ai/impact/activation_preview.py`

| 컴포넌트 | 역할 |
|----------|------|
| `build_activation_preview_entries` | patch_id로 Patch↔Decision 결합, Entry 생성 |
| `build_aggregated_requirement_previews` | 동일 req/doc/field AUTO_APPLY 순차 병합 |
| `validate_activation_preview` | Preview invariants |
| `build_preview_summary` | 집계 통계 |
| `compare_preview_vs_legacy` | Legacy generation 대비 관찰 |
| `build_activation_preview` | 오케스트레이션 (payload 반환) |

Runner (`scenario/runner.py`)는 PR-12 activation traces 직후 shadow JSON 4종을 기록한다.  
DOCX writer / legacy generation 경로는 호출하지 않는다.

---

## 3. ActivationPreviewEntry Schema

| Field | 의미 |
|-------|------|
| `preview_id` / `patch_id` / `draft_id` / `atomic_change_id` | 식별 |
| `requirement_id` / `document` / `field` / `operation` | 대상 |
| `activation_decision` | AUTO_APPLY / REVIEW / BLOCK |
| `original_requirement` | 원문 |
| `proposed_requirement` | Requirement Patch의 `patched_requirement` |
| `preview_requirement` | AUTO_APPLY면 proposed, 아니면 original |
| `applied_in_preview` | AUTO_APPLY만 `true` |
| `reasons` | 결정·적용 근거 |
| `validation_status` / `scope_preserved` / `review_required` | 메타 |
| `changed_spans` / `unchanged_spans` | span 추적 |

---

## 4. AggregatedRequirementPreview

동일 `requirement_id` / `document` / `field`에 여러 AUTO_APPLY patch가 있을 때:

1. `atomic_change_id` → `patch_id` 순으로 정렬
2. `apply_requirement_patch`로 **순차 병합** (단순 overwrite 금지)
3. 원문 base 불일치·merge INVALID/REVIEW_REQUIRED → `conflict_detected=true`
4. conflict 시 `final_preview_requirement` = 원문, silent resolve 금지

| Field | 의미 |
|-------|------|
| `applied_patch_ids` / `skipped_patch_ids` | 적용·스킵 |
| `final_preview_requirement` | 병합 결과 (또는 원문) |
| `decision_trace` | 단계별 기록 |
| `conflict_detected` / `conflict_reasons` | 충돌 |

---

## 5. AUTO_APPLY / REVIEW / BLOCK 처리

| Decision | `preview_requirement` | `applied_in_preview` | Queue |
|----------|----------------------|----------------------|-------|
| AUTO_APPLY | proposed | true | — |
| REVIEW | original | false | `review_queue` |
| BLOCK | original | false | `blocked_queue` |
| missing decision | original | false | REVIEW + `missing_activation_decision` |
| orphan decision (patch 없음) | — | — | `blocked_queue` (mismatch) |

---

## 6. Multi-patch 병합 방식

- 단순 마지막 patch overwrite **금지**
- 각 patch의 `semantic_draft`로 `SemanticDraft` 재구성 후 `apply_requirement_patch(current_base, draft)` 순차 적용
- ADD 계열은 누적 draft 텍스트가 최종 preview에 포함됨

---

## 7. Conflict 처리 원칙

- `inconsistent_original_bases` → 즉시 conflict, 원문 유지
- merge 중 INVALID / unsafe REVIEW_REQUIRED → conflict, 원문 유지
- `conflict_detected=true` → validation `REVIEW_REQUIRED`
- 자동 해결·부분 silent apply **금지**

---

## 8. Preview Validation

Invariants:

1. AUTO_APPLY만 `applied_in_preview=true`
2. REVIEW/BLOCK은 원문 유지
3. BLOCK은 Preview 미반영
4. missing decision 자동 반영 금지
5. conflict 시 원문 유지
6. `actual_docx_unchanged` / `actual_generation_unchanged` = true

상태: `VALID` | `VALID_WITH_WARNINGS` | `REVIEW_REQUIRED` | `INVALID`

---

## 9. Artifacts

| File | Content |
|------|---------|
| `output/trace/activation_preview.json` | entries + aggregated + queues |
| `output/trace/preview_validation.json` | counts + invariants |
| `output/trace/preview_summary.json` | AUTO_APPLY/applied/review/block/doc·field 통계 |
| `output/trace/preview_vs_legacy.json` | legacy texts vs preview (관찰) |

공통: `actual_docx_changed=false`, `actual_generation_changed=false`

---

## 10. Tests

`tests/test_b5_staged_pr13_activation_preview.py`

1. AUTO_APPLY → Preview 반영  
2. REVIEW → 원문  
3. BLOCK → 원문  
4. missing decision → 미적용  
5. patch_id mismatch → 차단  
6. AUTO_APPLY 외 `applied_in_preview=true` 금지  
7. multi-patch 결정적 순서  
8. multi-patch 병합 성공  
9. multi-patch conflict → REVIEW_REQUIRED  
10–11. review/blocked queue  
12–13. DOCX/Legacy flags 불변  
14. validation invariant  

---

## 11. Full pytest 결과

```text
python -m pytest -q
→ 549 passed in 166.20s (0 failed, 0 skipped)
```

PR-12 기준 537; PR-13 activation preview 테스트 +12. 회귀 없음.

---

## 12. Compatibility

변경 금지 유지:

- `requirement_patch.py` 의미
- `activation_policy.py` 결정 규칙
- Semantic Draft / Patch Contract / Owner / ACU
- Legacy generation / DOCX writer
- Scenario-001 frozen outputs

허용된 최소 변경: `runner.py`에 shadow preview artifact 쓰기만 연결.

---

## 13. Freeze

Scenario-001 / Trials **미재실행·미수정**. Freeze 유지.

---

## 14. Known Limitations

- Preview는 shadow only — DOCX에 쓰지 않음
- AUTO_APPLY ≠ 실제 출력 반영
- multi-patch 병합은 rule-based `apply_requirement_patch`에 의존
- REPLACE/DELETE 계열의 복잡한 교차 충돌은 보수적으로 conflict 처리
- dual-write / feature-flag cutover는 후속 PR

---

## 15. Next PR 제안 (PR-14)

후보:

- Preview Validation을 runner gate로 승격 (shadow fail-loud)
- feature-flag dual-write: AUTO_APPLY preview vs legacy side-by-side review UI
- DOCX cutover는 별도 승인 후에만

**Final judgment:** `READY_FOR_STAGED_B5_PR14`
