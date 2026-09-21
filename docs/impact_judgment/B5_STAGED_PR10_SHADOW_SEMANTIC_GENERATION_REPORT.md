# B5 Staged Architecture — PR-10 Shadow Semantic Generation 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR11`  
**범위:** Patch Contract → Shadow Semantic Draft (비교·검증만)  
**일자:** 2026-07-25

---

## 1. PR-10 Objective

Patch Contract만으로 ACU-scoped semantic draft를 **결정적으로** 생성할 수 있음을 증명한다.

- Legacy whole-CR generation **유지**
- DOCX **미변경**
- Owner / propagation / Patch Contract semantics **미변경**
- LLM/API **미도입**

---

## 2. Architecture

### Actual (unchanged)

```text
CR → ACU → Owner → Plan → Contract(shadow) → Legacy Whole-CR Generation → DOCX
```

### Shadow (new)

```text
Patch Contract
 → Semantic Draft Generator (RULE/TEMPLATE)
 → Semantic Draft Validation
 → Legacy vs Semantic Comparison
```

---

## 3. Generator Input Boundary

**허용:** 단일 PatchContract, structured semantic_intent, DocumentTarget, source_span, provenance, optional owner_target_text

**금지:** full CR, unrelated ACU, whole B3/B4, unrelated owners, frozen expected output

`cr_text` / `full_cr` / `change_request_text` kwargs → `INVALID` + `full_cr_input_forbidden`

---

## 4. SemanticDraft Schema

모듈: `src/document_ai/impact/semantic_draft.py`

`draft_id`, `contract_id`, `atomic_change_id`, `target`, `operation`, `draft_text`,  
`generation_mode`, `used_inputs`, `omitted_inputs`, `source_span`, `provenance`,  
`validation_status`, `validation_issues`, `review_required`, `concept_coverage`,  
`activation_eligible`

`generation_mode`: `RULE_BASED_SHADOW` | `TEMPLATE_BASED_SHADOW` | `REVIEW_REQUIRED` | `NO_ACTION`

---

## 5. Operation-specific Generation

| Op | Behavior |
|----|----------|
| ADD / UPDATE / REPLACE | requirement-style core statement |
| CONSTRAIN | constraint/condition clause |
| LINK | traceability instruction |
| DELETE | deletion metadata (no replacement prose) |
| NO_ACTION | empty |
| REVIEW_REQUIRED | empty + review |

Contract `validation_status != OK` → no automatic prose.

---

## 6. Requirement-language Policy

한국어 의무형: `시스템은 …해야 한다.` / `…인 경우 …해야 한다.`

금지: CR 서술 복사, 구현 세부 창작, `정책을 강화한다` 같은 모호 meta (계약에 없을 때)

---

## 7. Actor / Recipient Handling

- `implicit_system` → `시스템` (토큰명 노출 금지)
- recipient는 `…에게`만; `관리자가 알림을 보낸다` 금지

---

## 8. Constraint / Alternative Handling

`또는` / `중 하나` → OR 문장 (`A 또는 B에 따라 …될 수 있어야 한다`)  
AND로 flatten하지 않음

---

## 9. Scope Integrity Validation

계약 facet + source_span concepts vs draft tokens  
타 ACU only concepts → `cross_acu_leakage`  
문법·의무어는 allowlist

---

## 10. Full-CR Leakage Detection

- 생성기가 CR을 받지 않음
- draft == whole CR 비교 추적
- legacy vs shadow: `whole_cr_used_by_legacy` / `whole_cr_used_by_shadow`

---

## 11. Target-context Use

`owner_target_text`는 용어 overlap 기록만 (`target_context_terms`)  
기존 요구사항 전문 복붙 성공 처리 금지

---

## 12. Account-lock Fixture Result

Synthetic account-lock CR (non-frozen):

- ACU별 분리 draft
- 관리자/사용자 = recipient
- 알림 draft에 감사 개념 미포함
- whole-CR draft 없음
- 계약 수 hard-code 없음

---

## 13. Multi-domain Tests

Inventory / Reservation / Reporting / Retention — 도메인 키워드 소유권 리스트 없이 ACU→contract→draft

---

## 14. Legacy vs Semantic Comparison

Traces:

- `semantic_drafts_shadow.json`
- `semantic_draft_validation.json`
- `legacy_vs_semantic_draft.json`
- `semantic_generation_summary.json`

`actual_generation_changed=false`, `docx_changed=false`

---

## 15. Actual Behavior Parity

B3/B4/owner/propagation/generation/DOCX/allow_mdsr_patch/thresholds/Patch Contract schema 불변

---

## 16. Full pytest

```text
python -m pytest -q
→ 517 passed in 142.70s (0 failed, 0 skipped)
```

PR-9 기준 493; PR-10 shadow semantic generation 테스트 +24. 회귀 없음.
---

## 17. Freeze Integrity

scenario-001 / b3v2 / b4v2 / b5v2 / Trial 1–2 미재실행·미수정

---

## 18. Known Limitations

- rule/template only (no LLM)
- shadow-only drafts
- regulated prose 미승인
- DOCX는 legacy
- legacy validation은 contract-unaware
- whole-CR generation 활성
- frozen scenario 미재실행
- cross-ID actual discovery 보류
- semantic equivalence 제한적

---

## 19. Activation Criteria for PR-11

후보 게이트 (아직 미활성):

- `activation_eligible=True` drafts만 dual-write / preview
- INVALID/REVIEW는 legacy fallback
- DOCX cutover는 별도 승인 + freeze 재검증

---

## 20. Next PR Recommendation

**PR-11:** feature-flagged preview — eligible shadow drafts를 review artifact로 노출하되 DOCX는 legacy 유지. 또는 contract-aware validation 도입.

**Final judgment:** `READY_FOR_STAGED_B5_PR11`
