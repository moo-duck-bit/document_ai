# B5 Staged Architecture — PR-12 Activation Policy 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR13`  
**범위:** Requirement Patch Activation Policy (shadow only)  
**일자:** 2026-07-25

---

## 1. Objective

Requirement Patch를 **자동 적용할지** 판단하는 Activation Policy를 구현한다.

- DOCX **미수정**
- Legacy generation **유지**
- Requirement Patch / Semantic Draft / Patch Contract **미변경**

```text
Requirement Patch → Activation Policy → AUTO_APPLY | REVIEW | BLOCK
                                      → Legacy 비교 (관찰)
```

---

## 2. RequirementActivationDecision

모듈: `src/document_ai/impact/activation_policy.py`

| Field | 의미 |
|-------|------|
| `patch_id` / `requirement_id` | 대상 |
| `decision` | AUTO_APPLY / REVIEW / BLOCK |
| `reasons` | 결정 근거 |
| `validation_status` | patch validation |
| `scope_preserved` | scope 보존 여부 |
| `activation_eligible` | 적용 가능 여부 |
| `review_required` | 인간 검토 필요 |

---

## 3. Activation Rules

### AUTO_APPLY
- validation == VALID
- scope_preserved == true
- review_required == false
- duplicate 없음
- draft activation_eligible

### REVIEW
- VALID_WITH_WARNINGS
- REVIEW_REQUIRED op/status
- duplicate signal
- confidence 부족
- multiple candidates
- NO_ACTION
- scope_not_confirmed (비 INVALID)

### BLOCK
- INVALID
- scope violation
- semantic mismatch
- target 없음
- activation_eligible == false (INVALID 경로)

기본 fallback: **REVIEW** (silent AUTO_APPLY 금지)

---

## 4. Artifacts

| File | Content |
|------|---------|
| `requirement_activation_decisions.json` | decision list |
| `activation_summary.json` | counts + op/validation stats |
| `legacy_vs_activation.json` | vs legacy generation |

---

## 5. Policy Validation

- AUTO_APPLY ⊆ VALID
- BLOCK는 적용 불가 (`activation_eligible=false`)
- REVIEW는 `review_required=true`

---

## 6. Tests

`tests/test_b5_staged_pr12_activation_policy.py`

VALID→AUTO_APPLY, REVIEW_REQUIRED→REVIEW, INVALID→BLOCK, scope→BLOCK, duplicate→REVIEW, missing target→BLOCK

---

## 7. Compatibility

Legacy / DOCX / Patch / Draft / Contract / ACU **불변**  
AUTO_APPLY는 이번 PR에서 DOCX에 쓰지 않음

---

## 8. Full pytest

```text
python -m pytest -q
→ 537 passed in 137.30s (0 failed, 0 skipped)
```

PR-11 기준 529; PR-12 activation policy 테스트 +8. 회귀 없음.
---

## 9. Freeze

Scenario-001 / Trials 미재실행·미수정

---

## 10. Known Limitations

- Policy는 shadow only
- AUTO_APPLY ≠ DOCX write
- confidence/multiple-candidate는 선택 입력
- 실제 적용 오케스트레이션은 PR-13+

---

## 11. Next PR (PR-13)

후보: feature-flag로 AUTO_APPLY patches만 review artifact / dual-write preview. DOCX cutover는 별도 승인.

**Final judgment:** `READY_FOR_STAGED_B5_PR13`
