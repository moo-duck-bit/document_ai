# B5 Staged Architecture — PR-23 Generic Physical Locator Report

**최종 판정:** `READY_FOR_STAGED_B5_PR24` (hardened for PR-24)  
**범위:** Generic Physical Locator (observational) + PR-24 선행 안전성 보완  
**일자:** 2026-07-27

---

## 1. Objective

PR-22 Logical Patch Target을 PR-20 Document Structure에 연결하여  
Physical Location Candidate를 생성·순위화한다.

실제 DOCX/Markdown 수정, Writer 호출, Patch 실행은 하지 않는다.

---

## 2. Architecture / Pipeline

```text
PatchTargetCandidate
  → Document Structure Model
  → Physical Candidate Builder
  → Location Ranking (full_ranked_candidates)
  → Primary Physical Location
  → Artifact Top-K (per target)
  → Validation (on full set)
```

패키지: `src/document_ai/physical_locator/`

---

## 3. Full vs Artifact Top-K

| 필드 | 의미 |
|------|------|
| `full_ranked_candidates` / `full_candidates` | 메모리 내 ranking·validation·통계용 **전체** 후보 |
| `artifact_candidates` / `candidates` | artifact 크기 제한용 **Top-K (기본 8)** |
| `full_candidate_count` | 전체 후보 수 |
| `artifact_candidate_count` | artifact에 저장된 Top-K 합계 |
| `artifact_top_k_limit` | 8 |

Artifact metadata:

```text
candidate_scope = "TOP_K_PER_TARGET"
top_k_limit = 8
full_candidate_count = ...
artifact_candidate_count = ...
```

파일:

- `physical_location_candidates.json` (Top-K + metadata)
- `physical_location_candidates_topk.json` (명시적 Top-K)

Primary candidate는 반드시 artifact Top-K 안에 존재한다.  
Validation은 **full_ranked_candidates** 기준으로 수행한다.

---

## 4. character_span / span_kind

`character_span`은 OOXML 또는 원문 absolute offset이 **아니다**.

| span_kind | 의미 |
|-----------|------|
| `ESTIMATED_BLOCK_LOCAL` | Markdown/Object fixture 기본 (블록 로컬 추정) |
| `SOURCE_ABSOLUTE` | 원문 absolute offset 보장 시에만 |
| `OOXML_LOCAL` | OOXML 로컬 span |
| `NONE` | span 없음/미보장 |

TABLE_CELL의 `(0, len(cell))`은 **block-local** (`ESTIMATED_BLOCK_LOCAL`)이다.  
문서 전체 absolute span으로 해석하지 않는다.

PR-24 Patch Contract는 다음이 모두 충족되지 않으면 character_span을 실행 가능 위치로 간주하지 않는다:

- `span_kind == SOURCE_ABSOLUTE`
- locator confidence sufficient
- source fingerprint valid

---

## 5. Ranking & Threshold

점수 요소: heading / parent / section / field / block_type / document_order  

| Status | Threshold |
|--------|-----------|
| RESOLVED | ≥ 0.85 (+ margin or clear preferred type) |
| REVIEW | ≥ 0.60 또는 ambiguous top |
| UNRESOLVED | < 0.60 또는 후보 없음 |
| INVALID | broken document/target reference |

---

## 6. Observational Gate (Feature Flag만으로 안전하지 않음)

Feature Flag OFF 자체가 **유일한** 안전장치가 아니다.

검증 필드:

| 필드 | PR-23 값 |
|------|----------|
| `external_activation_flag` | env 관찰값 (ON 가능) |
| `observational_gate_forced_off` | **항상 true** |
| `activation_allowed` | **항상 false** |

외부 Flag가 true여도:

- `actual_writer_called = false`
- `actual_docx_changed = false`
- `actual_patch_created = false`

Validation invariant는 상수 True가 아니라 **issues / 객체 상태**로 계산한다  
(`observational_only`, `pr18_to_pr22_non_mutation`, `activation_blocked_despite_external_flag`).

---

## 7. Sample Results

| Case | Status |
|------|--------|
| MATCHED Paragraph (data_sources) | RESOLVED |
| MATCHED Table | RESOLVED |
| MATCHED List | RESOLVED |
| Duplicate heading/paragraph | REVIEW |
| Empty document | UNRESOLVED |
| Missing document / invalid target | INVALID |

---

## 8. Artifacts

`output/physical_locator/`:

- physical_locator_inputs.json  
- physical_location_candidates.json (Top-K + scope metadata)  
- physical_location_candidates_topk.json  
- primary_physical_locations.json  
- physical_locator_summary.json  
- physical_locator_validation.json  

---

## 9. Known Limitations

- Logical structure index만 (OOXML absolute offset 없음)  
- `span_kind`는 대부분 `ESTIMATED_BLOCK_LOCAL` / `NONE`  
- Writer 실행은 PR-25 controlled activation까지 차단  

---

## 10. Next

**PR-24:** Physical Location → Observational Patch Contract / Writer Plan bridge  
(여전히 write OFF). → 완료 후 `READY_FOR_CONTROLLED_B5_PR25`

---

## 11. Full pytest (hardening 후)

PR-23 전용: **41 passed**.  
전체 suite (PR-24 포함): **912 passed**, 0 failed.

actual_patch_created / actual_docx_changed / actual_writer_called = **0**.  
External Feature Flag ON에서도 observational gate가 우선한다.

**Verdict: `READY_FOR_STAGED_B5_PR24` (hardened)**
