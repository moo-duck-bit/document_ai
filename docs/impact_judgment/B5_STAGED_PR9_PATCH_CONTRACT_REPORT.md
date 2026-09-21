# B5 Staged Architecture — PR-9 Patch Contract 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR10`  
**범위:** B6 Patch Planning ↔ 미래 Semantic Generation 사이의 **Patch Contract** 안정화  
**일자:** 2026-07-25

---

## 1. PR-9 Objective

Semantic generation을 **활성화하지 않는다**.

대신 Patch Planning(B6)과 향후 generation 사이의 **의도(intent) 계약**을 고정한다.

```text
CR → ACU v2 → Owner Selection → Patch Planning → Patch Contract (NEW)
                                              → Legacy Whole-CR Generation (unchanged)
```

---

## 2. Contract Schema

모듈: `src/document_ai/impact/patch_contract.py`

### PatchContract

| Field | 의미 |
|-------|------|
| `contract_id` | `PC-{ACU-id}` |
| `atomic_change_id` | 1 ACU ↔ 1 primary contract |
| `owner_requirement_id` / `owner_design_id` | Owner 선택 결과 |
| `semantic_intent` | 구조화 intent (prose 없음) |
| `responsibility_type` | ACU 책임 유형 |
| `patch_operation` | 정규화된 연산 |
| `target` | `DocumentTarget` dict |
| `target_section` / `target_field` | 명시적 위치 |
| `source_span` | ACU span |
| `rationale` | 계획 근거 |
| `confidence` | 신뢰도 |
| `provenance` | ACU/owner evidence |
| `review_required` | 검증 실패 시 true |

**생성 prose 필드 없음.**

### DocumentTarget

`document` · `requirement_id` · `field` · `section` · `anchor`

Generation이 target을 추론하지 않도록 명시.

### SemanticIntentContract

```json
{
  "responsibility_type": "notification",
  "actor": "implicit_system",
  "recipient": "administrator",
  "action": "notify",
  "object": [],
  "condition": null,
  "constraint": [],
  "output": [],
  "affected_entity": []
}
```

---

## 3. Patch Operations (closed set)

`ADD` · `UPDATE` · `DELETE` · `CONSTRAIN` · `REPLACE` · `LINK` · `NO_ACTION` · `REVIEW_REQUIRED`

정규화 예: `EXTEND`/`MODIFY` → `UPDATE`, `NO_CHANGE` → `NO_ACTION`, `REVIEW` → `REVIEW_REQUIRED`

---

## 4. Architecture

```text
ACU + B6 PatchPlanItem + PropagationTrace
        ↓
build_patch_contract() / build_patch_contracts()
        ↓
validate_patch_contract()
        ↓
patch_contracts.json (shadow)
```

Actual DOCX path는 계속 `proposed_*` whole-CR append.

---

## 5. Validation

필수: operation · target · semantic intent · owner(해당 시) · provenance · source_span

누락 → `REVIEW_REQUIRED` (legacy generation은 차단하지 않음)

---

## 6. Traces

| File | Content |
|------|---------|
| `patch_contracts.json` | contract list + schema note |
| `patch_contract_validation.json` | OK / REVIEW counts |
| `patch_contract_diff.json` | legacy targets vs contracts |

---

## 7. Compatibility

| 항목 | 상태 |
|------|------|
| Legacy whole-CR generation | 유지 |
| DOCX mutation via contract | 없음 |
| Owner selection / B3/B4 | 미변경 |
| B6 shadow plans | 입력으로만 사용 |
| Patch Contract | **shadow-only** |

---

## 8. Tests

`tests/test_b5_staged_pr9_patch_contract.py`

- operation / target normalization
- semantic intent integrity
- single / multiple ACU
- review required / no owner
- plan+trace fallback
- validation + diff
- no prose in payload

---

## 9. Full pytest / Freeze

```text
python -m pytest -q
→ 493 passed in 130.41s (0 failed, 0 skipped)
```

PR-8 기준 482; PR-9 patch contract 테스트 +11. 회귀 없음.

Freeze: Scenario-001 / Trials 미재실행·미수정.
---

## 10. Known Limitations

- Contract는 shadow only
- Generation은 여전히 whole-CR
- Contract → prose renderer 미구현
- Actual path가 contract를 소비하지 않음
- Cross-ID target 미확장

---

## 11. PR-10 Recommendation

Feature-flagged **Semantic Generation**:

- `validation_status=OK` contract만 ACU `semantic_intent` + `source_span`으로 prose 초안
- `REVIEW_REQUIRED` / 실패 시 legacy whole-CR fallback
- Scenario hard-code 금지

**Final judgment:** `READY_FOR_STAGED_B5_PR10`
