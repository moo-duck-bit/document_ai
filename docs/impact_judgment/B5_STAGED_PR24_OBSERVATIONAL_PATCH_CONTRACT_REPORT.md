# B5 Staged Architecture — PR-24 Observational Patch Contract / Writer Plan Bridge

**최종 판정:** `READY_FOR_CONTROLLED_B5_PR25`  
**범위:** Observational Patch Contract + Writer Plan Preview (dry-run only)  
**일자:** 2026-07-27

---

## 1. Objective

PR-23 `PrimaryPhysicalLocation`과 PR-22 `PatchIntent`를 결합하여  
Writer가 이해할 수 있는 **Patch Contract 초안**과 **Writer Plan Preview**를 만든다.

PR-24는 observational dry-run이다. 실제 Writer/DOCX/Markdown 수정은 금지한다.

---

## 2. Architecture / Pipeline

```text
PatchIntent
  → PatchTargetCandidate
  → PrimaryPhysicalLocation
  → Patch Contract Builder
  → Precondition Builder
  → Writer Plan
  → Dry-run Validation
  → Observational Execution Preview
```

패키지: `src/document_ai/patch_contract/`

| 모듈 | 역할 |
|------|------|
| `schema.py` | typed schemas |
| `contract_builder.py` | status / operation plan |
| `preconditions.py` | ordered preconditions |
| `fingerprint.py` | SHA-256 observational fingerprints |
| `writer_plan.py` | adapter 이름만 결정 |
| `capability_gate.py` | template vs writer vs gate |
| `preview.py` | WriterPlanPreview (no PREVIEW_READY) |
| `validation.py` | ID/consistency/safety invariants |
| `orchestrator.py` | fixtures + engine |

---

## 3. Schema (요약)

- `PatchContractInput`
- `PatchPrecondition`
- `PatchOperationPlan`
- `PatchContract`
- `WriterPlanPreview`

### Contract status

| Status | 의미 |
|--------|------|
| `CONTRACT_READY_FOR_REVIEW` | 검토용 초안 (실행 아님) |
| `CONTRACT_BLOCKED` | capability/UNRESOLVED/missing text 등 |
| `CONTRACT_REVIEW` | ambiguity / DELETE 등 |
| `CONTRACT_INVALID` | broken references / doc mismatch |

**금지:** `CONTRACT_EXECUTABLE`, `EXECUTED`, `APPLIED`

### Preview status

| Status | 의미 |
|--------|------|
| `PREVIEW_BLOCKED` | 기본 (READY_FOR_REVIEW 포함) |
| `PREVIEW_REVIEW` | contract REVIEW |
| `PREVIEW_INVALID` | contract INVALID |

**금지:** `PREVIEW_READY`

항상:

```text
contract_executable = false
activation_allowed = false
actual_patch_created = false
actual_document_changed = false
actual_docx_changed = false
actual_writer_called = false
```

---

## 4. Contract status policy

`CONTRACT_READY_FOR_REVIEW` 조건 (모두 충족):

- Intent `ELIGIBLE`
- Target `RESOLVED`
- Location `RESOLVED`
- `physical_candidate_id` 존재
- document / template_node 일치
- operation 유효 + proposed_text (필요 시)
- 위치 논리 일관
- 실제 writer 실행은 차단

`CONTRACT_READY_FOR_REVIEW` ≠ 실행 가능.

---

## 5. Preconditions

지원 타입: DOCUMENT_EXISTS, DOCUMENT_ID_MATCH, TARGET_RESOLVED, LOCATION_RESOLVED,  
SOURCE_FINGERPRINT_MATCH, BLOCK_EXISTS, ORIGINAL_TEXT_MATCH, OPERATION_ALLOWED,  
WRITER_CAPABILITY_SUPPORTED, HUMAN_APPROVAL_PRESENT, OBSERVATIONAL_GATE_DISABLED

`OBSERVATIONAL_GATE_DISABLED`는 실행 관점에서 항상 `UNSATISFIED`  
(게이트가 강제 OFF → activation 불가).

---

## 6. Fingerprint policy

- Algorithm: **SHA-256**
- Encoding: UTF-8
- Line endings: CRLF/CR → LF
- Whitespace 정규화 여부 metadata에 기록

원문 없는 fixture: `fingerprint_status = NOT_AVAILABLE` (임의 hash 생성 금지).  
Stale fixture: precondition `UNSATISFIED` → `CONTRACT_BLOCKED`.

---

## 7. Writer adapter planning

Adapter 이름만 결정 (호출 없음):

- `DOCX_PARAGRAPH_WRITER`
- `DOCX_TABLE_CELL_WRITER`
- `MARKDOWN_BLOCK_WRITER`
- `UNSUPPORTED_WRITER`

항상:

```text
observational_gate_forced_off = true
activation_allowed = false
```

---

## 8. Observational gate / External Feature Flag

Feature Flag OFF만으로 안전하다고 보지 않는다.

| 필드 | 값 |
|------|-----|
| `external_activation_flag` | env 관찰 (`DOCX_ACTIVATION_ENABLED`) |
| `observational_gate_forced_off` | true |
| `activation_allowed` | false |

`run_patch_contract_engine(env={"DOCX_ACTIVATION_ENABLED": "true"})` 전체 결과에서:

- 모든 `activation_allowed == false`
- 모든 `contract_executable == false`
- 모든 `actual_writer_called == false`
- 모든 `actual_document_changed == false`
- `PREVIEW_READY` / `CONTRACT_EXECUTABLE` 없음

---

## 9. Sample Results

| Case | Contract | Preview |
|------|----------|---------|
| Paragraph UPDATE | CONTRACT_READY_FOR_REVIEW | PREVIEW_BLOCKED |
| Table cell UPDATE | CONTRACT_READY_FOR_REVIEW | PREVIEW_BLOCKED |
| List UPDATE | CONTRACT_READY_FOR_REVIEW | PREVIEW_BLOCKED |
| ADD unsupported | CONTRACT_BLOCKED | PREVIEW_BLOCKED |
| REVIEW physical | CONTRACT_REVIEW | PREVIEW_REVIEW |
| UNRESOLVED physical | CONTRACT_BLOCKED | PREVIEW_BLOCKED |
| Invalid target ref | CONTRACT_INVALID | PREVIEW_INVALID |
| Missing proposed_text | CONTRACT_BLOCKED | PREVIEW_BLOCKED |
| DELETE w/o approval | CONTRACT_REVIEW | PREVIEW_REVIEW |
| LINK missing metadata | CONTRACT_BLOCKED | PREVIEW_BLOCKED |
| document_id mismatch | CONTRACT_INVALID | PREVIEW_INVALID |
| Stale fingerprint | CONTRACT_BLOCKED | PREVIEW_BLOCKED |
| External Flag ON | CONTRACT_READY_FOR_REVIEW | PREVIEW_BLOCKED (activation=false) |

---

## 10. Artifacts

`output/patch_contract/`:

- patch_contract_inputs.json
- patch_contracts.json
- patch_preconditions.json
- patch_operation_plans.json
- writer_plan_previews.json
- patch_contract_summary.json
- patch_contract_validation.json

공통 metadata: `stage`, `schema_version`, `observational_only`,  
`generated_from_pr22`, `generated_from_pr23`, `external_activation_flag`,  
`observational_gate_forced_off`, mutation flags = false.

---

## 11. Validation

- unique contract / precondition / plan / preview IDs  
- valid references, document/template/node/operation/location consistency  
- span_kind consistency; top1 physical (via PR-23)  
- safety: no PREVIEW_READY, no CONTRACT_EXECUTABLE, activation always false  
- summary counts; invariants computed from issues/objects  

---

## 12. PR-18~23 regression

- PR-18 Template Abstraction: 불변  
- PR-19 Generic Template Pack: 불변  
- PR-20 Document Structure: 불변  
- PR-21 Semantic Locator: 불변  
- PR-22 Patch Targeting: `activation_allowed_count=0`  
- PR-23 Physical Locator: full vs Top-K / span_kind / gate 유지  
- Freeze paths 유지  

---

## 13. Known limitations

- character_span은 대부분 `ESTIMATED_BLOCK_LOCAL` → 실행 위치 아님  
- ADD/DELETE/LINK writer path 미지원 (BLOCKED/REVIEW)  
- CONTRACT_READY_FOR_REVIEW는 human review 초안일 뿐  
- PR-25 전까지 write path 완전 차단  

---

## 14. PR-25 controlled activation prerequisites

1. `span_kind == SOURCE_ABSOLUTE` + valid fingerprint  
2. Human approval for DELETE / high-risk ops  
3. Explicit controlled activation gate (observational gate 해제 정책)  
4. Writer adapter capability matrix + dry-run → apply 분리  
5. Stale fingerprint 차단 유지  
6. Feature Flag AND controlled gate AND approval — Flag alone 금지  

---

## 15. Full pytest

PR-24 전용: **50 passed**.  
전체 suite: **912 passed**, 0 failed.

Safety counters:

- Patch / DOCX / Writer = **0**
- Feature Flag ON도 차단

**Verdict: `READY_FOR_CONTROLLED_B5_PR25`**
