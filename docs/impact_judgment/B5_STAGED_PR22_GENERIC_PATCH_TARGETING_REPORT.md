# B5 Staged Architecture — PR-22 Generic Patch Targeting Report

**최종 판정:** `READY_FOR_STAGED_B5_PR23`  
**범위:** Generic Patch Targeting / Observational Patch Intent Bridge  
**일자:** 2026-07-27

---

## 1. Objective

PR-21 Semantic Match Result를 실제 문서 수정 없이  
**Patch Intent → Logical Target → Activation Preview**로 변환한다.

---

## 2. Architecture

```text
Semantic Match Result
  → Eligibility
  → Patch Intent (ELIGIBLE / REVIEW_REQUIRED / BLOCKED / INVALID)
  → Patch Target Candidate (RESOLVED / REVIEW / UNRESOLVED / INVALID)
  → Activation Preview (항상 observational; Feature Flag OFF → BLOCKED)
  → Validation
```

패키지: `src/document_ai/patch_targeting/`

---

## 3. Input / Output Schema

- `PatchTargetingInput` — change + semantic match context + requested_operation  
- `PatchIntent` — `actual_patch_created=false`  
- `PatchTargetCandidate` — logical node only (no physical locator)  
- `ActivationPreview` — `actual_writer_called=false`, `actual_document_changed=false`

---

## 4. Eligibility Policy

| Semantic | Default Intent |
|----------|----------------|
| MATCHED | ELIGIBLE (추가 조건 통과 시) |
| REVIEW | REVIEW_REQUIRED |
| UNMAPPED | BLOCKED |
| INVALID | INVALID |

추가 차단/검토: ambiguity, low margin, missing proposed_text, DELETE, LINK metadata, template/writer capability.

---

## 5. Template / Writer Capability Separation

예시 (ADD):

- `template_allowed=true`
- `writer_supported=false`
- `activation_allowed=false`
- Intent=ELIGIBLE, Preview=PREVIEW_BLOCKED

Template 허용 ≠ Writer 실행.

### Observational Gate vs External Feature Flag

PR-22 `capability_gate`는 외부 `DOCX_ACTIVATION_ENABLED`보다 **우선**한다.

- `external_activation_flag` = `is_docx_activation_enabled(...)` 결과 (관찰용)
- `observational_gate_forced_off` = **항상 true**
- `activation_allowed` = **항상 false**

외부 Flag가 true여도:

- Preview ≠ `PREVIEW_READY`
- `actual_writer_called=false`
- `actual_document_changed=false`
- reason: `ACTIVATION_DISABLED`, `OBSERVATIONAL_GATE_FORCED_OFF`

---

## 5b. Semantic Match Reference Validation

`validate_patch_targeting(..., known_semantic_match_ids=...)`  

- `None` (기본): 샘플 fixture 독립 실행 호환 — reference 검사 생략  
- `set` 제공 시: `PatchIntent.semantic_match_id` 미존재 → `unknown_semantic_match_id:<id>`  
- invariant `semantic_match_reference_valid`는 issues 기반으로 계산

---

## 6. Sample Results

| Case | Intent | Target | Preview |
|------|--------|--------|---------|
| MATCHED UPDATE | ELIGIBLE | RESOLVED | PREVIEW_BLOCKED (ACTIVATION_DISABLED) |
| MATCHED ADD | ELIGIBLE | RESOLVED | PREVIEW_BLOCKED (WRITER_NOT_SUPPORTED) |
| REVIEW match | REVIEW_REQUIRED | REVIEW | PREVIEW_REVIEW |
| UNMAPPED | BLOCKED | UNRESOLVED | PREVIEW_BLOCKED |
| INVALID | INVALID | INVALID | PREVIEW_INVALID |
| Ambiguous DELETE | REVIEW_REQUIRED | REVIEW | PREVIEW_REVIEW |
| Missing proposed_text | BLOCKED | UNRESOLVED | PREVIEW_BLOCKED |
| LINK writer unsupported | ELIGIBLE | RESOLVED | PREVIEW_BLOCKED |
| Generic req_id=None | ELIGIBLE | RESOLVED | PREVIEW_BLOCKED |

---

## 7. Artifacts

`output/patch_targeting/`:

- patch_targeting_inputs.json  
- patch_intents.json  
- patch_target_candidates.json  
- activation_previews.json  
- patch_targeting_summary.json  
- patch_targeting_validation.json  

PR-18~21 artifact 불변.

---

## 8. Validation

`validation.status` vs `global_patch_targeting_status` 분리.  
샘플 INVALID fixture → global=INVALID, validation=VALID 가능.

---

## 9. Non-Mutation

PR-18/19/20/21, Change Review, DOCX Writer, Legacy, Freeze 유지.  
Feature Flag OFF. actual_patch/docx/writer = 0.

---

## 10. Known Limitations

- Physical paragraph/table locator 없음  
- Patch Contract / Writer bridge 없음  
- Human Approval 없음  
- Requirement Patch Engine과 미통합 (의도)

---

## 11. Next PR Recommendation

**PR-23:** Physical locator (DOCX/Markdown structure → span) observational bridge,  
또는 Patch Intent → shadow Patch Contract adapter (write still OFF).

---

## 12. Full pytest

**821 passed**, 0 failed (PR-22 safety hardening 포함).

실제 Patch / DOCX / Writer = **0**.

**Verdict: `READY_FOR_STAGED_B5_PR23`**
