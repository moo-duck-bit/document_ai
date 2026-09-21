# B5 Staged Architecture — PR-11 Requirement Patch 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR12`  
**범위:** Shadow Requirement-level Patch Application  
**일자:** 2026-07-25

---

## 1. Objective

Semantic Draft를 **구조화된 Requirement 텍스트**에 결정적으로 적용한다.

- DOCX / Word / serialization **없음**
- Legacy generation / DOCX **불변**
- Semantic generation **미활성** (shadow draft만 소비)

```text
Patch Contract → Semantic Draft → Requirement Patch (shadow)
  → Patched Requirement → Validation → Legacy Comparison
```

---

## 2. RequirementPatch Schema

모듈: `src/document_ai/impact/requirement_patch.py`

| Field | 의미 |
|-------|------|
| `original_requirement` | 원문 필드 텍스트 |
| `semantic_draft` | 적용 draft |
| `patched_requirement` | 패치 결과 |
| `changed_spans` / `unchanged_spans` | 변경·보존 구간 |
| `operation` | 정규화 연산 |
| `validation_*` / `scope_preserved` | 검증 |

---

## 3. Operation Behavior

| Op | 동작 |
|----|------|
| UPDATE | 책임 overlap 절만 교체; 없으면 append |
| ADD | 누락 책임만 append; 중복 skip |
| CONSTRAIN | 매칭 절에 조건 주입 또는 제약 문장 append |
| DELETE | intent overlap 절만 제거 |
| LINK | prose 유지, link metadata만 |
| REPLACE | 대상 필드 전체 → draft |
| NO_ACTION / REVIEW_REQUIRED | 원문 유지 |

---

## 4. Scope Preservation

- 비대상 절·식별자·번호 유지 (필드 텍스트 단위)
- 전체 requirement 재생성 금지
- `unchanged_spans`로 검증

---

## 5. Validation

- target 보존
- semantic intent 반영
- unrelated text 보존
- duplicate responsibility 방지
- unrelated insertion 경고
- operation 충족

---

## 6. Shadow Traces

| File | Content |
|------|---------|
| `requirement_patches_shadow.json` | patch list |
| `requirement_patch_validation.json` | OK / warning / invalid |
| `legacy_vs_requirement_patch.json` | vs whole-CR legacy |

---

## 7. Tests

`tests/test_b5_staged_pr11_requirement_patch.py`

UPDATE / ADD / CONSTRAIN / DELETE / LINK / REPLACE / scope / duplicate / multi-patch / NO_ACTION·REVIEW

---

## 8. Compatibility

Legacy generation·DOCX·owner·ACU·Patch Contract·semantic generator **미변경**

---

## 9. Full pytest

```text
python -m pytest -q
→ 529 passed in 171.80s (0 failed, 0 skipped)
```

PR-10 기준 517; PR-11 requirement patch 테스트 +12. 회귀 없음.
---

## 10. Freeze

Scenario-001 / Trials 미재실행·미수정

---

## 11. Known Limitations

- 필드 문자열 단위 (DOCX 레이아웃 미반영)
- 절 분할은 rule-based
- shadow only
- DOCX cutover 없음

---

## 12. Next PR (PR-12)

후보: eligible requirement patches를 review artifact로 dual-write하거나, DOCX field patch preview (flagged). 실제 DOCX 교체는 별도 승인.

**Final judgment:** `READY_FOR_STAGED_B5_PR12`
