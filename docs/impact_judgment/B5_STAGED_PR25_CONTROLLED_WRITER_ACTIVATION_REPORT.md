# B5 Staged Architecture — PR-25 Controlled Writer Activation

**최종 판정:** `DOCUMENT_AI_V1_COMPLETE`  
**범위:** Controlled Writer (Approval → Adapter → Executor → Diff → Rollback → Validation)  
**일자:** 2026-07-27

---

## 1. Objective

PR-24 Patch Contract를 입력으로, **원본을 절대 수정하지 않고** 복사본에서만  
Controlled Writer를 실행한다.

필수 조건:

- Approval 필수
- 원본 수정 금지 (copy only)
- Rollback 가능
- Diff 생성
- Validation 통과
- Dual flag: `DOCX_ACTIVATION_ENABLED` **AND** `CONTROLLED_WRITER_ENABLED`
- `span_kind == SOURCE_ABSOLUTE` + fingerprint match

Flag 단독으로는 activation 불가.

---

## 2. Pipeline

```text
Patch Contract
  → Approval Check
  → Writer Adapter
  → Patch Executor (on COPY)
  → Validation
  → Diff
  → Rollback Point
  → Result
```

패키지: `src/document_ai/controlled_writer/`

---

## 3. Approval

`ApprovalDecision`:

- `approval_id`, `patch_contract_id`
- `decision`: APPROVED | REJECTED | AUTO_APPROVED | MANUAL_REQUIRED
- `approved_by`, `approved_at`, `reason`

DELETE는 **APPROVED**만 허용 (AUTO_APPROVED 불가).

---

## 4. Writer Adapters

| Adapter | Ops |
|---------|-----|
| DOCX_PARAGRAPH_WRITER | UPDATE / REPLACE |
| DOCX_TABLE_CELL_WRITER | UPDATE / REPLACE |
| MARKDOWN_BLOCK_WRITER | UPDATE / REPLACE / ADD / DELETE / LINK |
| UNSUPPORTED_WRITER | 차단 |

---

## 5. Mutation Rule

```text
original.*  →  never modified
original_copy_*  →  only copy mutated
```

`ensure_copy` → writer → (failure 시) rollback snapshot restore.

---

## 6. Sample Results

| Case | Result |
|------|--------|
| Paragraph UPDATE | APPLIED (copy) |
| Table UPDATE | APPLIED |
| List UPDATE | APPLIED |
| ADD | APPLIED |
| DELETE + APPROVED | APPLIED |
| LINK | APPLIED |
| Approval REJECT | REJECTED |
| Forced failure | ROLLED_BACK |
| Feature flags OFF | BLOCKED |
| DOCX paragraph / table | APPLIED |
| Stale fingerprint | BLOCKED |
| Unsupported writer | BLOCKED |

`original_changed_count = 0`

---

## 7. Artifacts

`output/writer/`:

- approval.json
- writer_plan.json
- writer_result.json
- diff.json
- rollback.json
- validation.json
- summary.json

---

## 8. Validation

- Original fingerprint unchanged
- Patch success / failure counts
- Diff consistency
- Rollback snapshot exists for APPLIED

---

## 9. PR-18~24 Regression

불변. PR-24는 여전히 `activation_allowed=false` / `contract_executable=false`  
(observational). PR-25는 **별도 dual-flag controlled path**.

Freeze paths 유지.

---

## 10. Full pytest

PR-25 전용: **52 passed**.  
전체 suite: **964 passed**, 0 failed.

완료 조건:

- 원본 변경 0건
- 복사본 수정 성공
- Rollback 성공
- Diff 생성
- Validation 성공
- pytest 전체 통과

**Verdict: `DOCUMENT_AI_V1_COMPLETE`**
