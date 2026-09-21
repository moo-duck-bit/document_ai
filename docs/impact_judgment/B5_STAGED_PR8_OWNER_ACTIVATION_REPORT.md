# B5 Staged Architecture — PR-8 Owner Activation 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR9`  
**범위:** ACU v2 기반 **owner selection만** actual path에 활성화  
**일자:** 2026-07-25

---

## 1. PR-8 Objective

Improved ACU v2 pipeline로 **Design Discovery → Responsibility Alignment → Propagation Decision** 입력만 교체한다.

의도적으로 **활성화하지 않음**:

- document patching 로직 교체
- DOCX generation 재설계
- patch application 교체
- validation rewriting
- B3/B4 reasoning 변경

---

## 2. Architecture

### Before

```text
legacy actual:
CR → B3 → B4 → Design Discovery → Alignment → Propagation
     (alignment/decision query = whole CR)

shadow:
CR → ACU v2 → Discovery → Alignment → Propagation  (analysis only)
```

### After (PR-8 actual)

```text
CR
 ↓
ACU v2
 ↓
Design Discovery          (same-ID; per ACU × requirement)
 ↓
Responsibility Alignment  (query = ACU.source_span)
 ↓
Propagation Decision      (per ACU; aggregate → req-level trace)
 ↓
(existing generation / apply — whole-CR append helpers unchanged)
```

B3/B4는 계속 whole-CR.

---

## 3. Activated Code Path

| 모듈 | 역할 |
|------|------|
| `owner_activation.py` | `select_owners_via_acu`, summary/diff/mapping builders |
| `propagation.build_propagation_plan` | `owner_selection_mode`: `legacy` (default) / `auto` / `acu` |
| `scenario/runner.py` | `owner_selection_mode="auto"` + `acus=acu_units` |

Runner 활성화 시:

1. legacy plan을 한 번 계산 (diff + shadow observation 유지)
2. usable EXTRACTED ACU가 있으면 ACU path로 **actual traces** 교체
3. 없으면 legacy fallback

Alignment/Decision에 넣는 텍스트는 **`acu.source_span`** 이다 (whole CR 아님).

---

## 4. Compatibility

| 항목 | 동작 |
|------|------|
| Library default | `owner_selection_mode="legacy"` — 기존 테스트/호출 호환 |
| Scenario runner | `auto` — ACU 있으면 활성화 |
| Empty / no EXTRACTED ACU | legacy fallback |
| Apply / `proposed_*` | whole-CR append **유지** |
| Trace shape | requirement-level `PropagationTrace` 유지 (apply 호환) |
| Shadow observation | legacy plan의 shadow traces 유지 |

---

## 5. Execution Summary Schema

```json
{
  "acu_count": 5,
  "owners_found": 4,
  "needs_review": 1,
  "legacy_targets": 3,
  "acu_targets": 4,
  "effective_mode": "acu",
  "generation_unchanged": true,
  "b3_b4_unchanged": true
}
```

---

## 6. Traces

| File | Content |
|------|---------|
| `owner_activation_summary.json` | mode, counts, targets |
| `owner_activation_diff.json` | legacy vs acu owner decisions |
| `acu_owner_mapping.json` | ACU × requirement evaluations |

---

## 7. Aggregation Rule

- 각 ACU가 독립적으로 same-ID discovery → align(span) → decide
- Requirement별로 가장 강한 ACU decision을 aggregate  
  (`PATCH_EXISTING` > `EXTEND_EXISTING` > `NEW_DESIGN` > `NEEDS_REVIEW` > `SKIP`)
- AMBIGUOUS/NEEDS_REVIEW ACU는 owner를 단독 grant하지 않음
- Aggregate 후 patch 허용 시 `proposed_mddr_design_description(mddr, cr_text)`로 snippet 생성 (generation unchanged)

---

## 8. Risk Assessment

| Risk | Mitigation |
|------|------------|
| ACU span이 너무 짧아 false SKIP | EXTRACTED만 사용; fallback; diff trace로 비교 |
| Multi-ACU → 동일 Req 중복 | req-level aggregate; apply는 기존과 동일 1회 patch |
| 테스트 대량 실패 | library default=`legacy`; runner만 `auto` |
| Frozen scenario 오염 | rerun 금지; 이번 PR에서 scenario 미실행 |
| Generation이 ACU intent를 무시 | **known** — PR-9+ 대상 |

---

## 9. Remaining Work Before Generation Activation

1. Patch planning을 ACU `semantic_intent` 기반으로 전환
2. `proposed_*` whole-CR append 제거 → ACU-scoped prose
3. Validation을 staged/ACU-aware로 재작성
4. Cross-ID actual discovery (현재 same-ID 유지)
5. Frozen unseen scenario에서 owner+generation 통합 검증 (별도 승인)

---

## 10. Synthetic Tests

`tests/test_b5_staged_pr8_owner_activation.py`

- legacy fallback (empty ACU)
- single ACU
- multiple ACUs
- empty ACU + explicit acu mode → fallback
- diff/summary artifacts
- AMBIGUOUS does not grant owner
- library default = legacy

---

## 11. Full pytest / Freeze

```text
python -m pytest -q
→ 482 passed in 126.79s (0 failed, 0 skipped)
```

PR-7 기준 474; PR-8 owner activation 테스트 +8. 회귀 없음.

Freeze: scenario-001 / b3v2 / b4v2 / b5v2 / Trial 1–2 미수정·미재실행.
---

## 12. Known Limitations

- Owner selection만 ACU화; **generation은 여전히 whole-CR**
- Actual discovery는 same-ID
- B3/B4는 whole-CR
- Cross-ID actual owner 미활성
- Scenario-001 frozen 재검증 없음

---

## 13. Next PR Recommendation (PR-9)

**Generation activation (feature-flagged):** CLEAR/aggregated owner에 대해 ACU `semantic_intent` + `source_span`으로 patch text 생성. whole-CR append는 fallback. Scenario hard-code 금지.

**Final judgment:** `READY_FOR_STAGED_B5_PR9`
