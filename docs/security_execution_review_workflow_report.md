# Security Execution Review Workflow Report

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


Sprint: **XXCS Execution Review, Approval and Report Selection Workflow**

## Review state model

| Status | Use |
|--------|-----|
| `imported` | After execution import |
| `review_pending` | Awaiting human review |
| `reviewer_verified` | Real execution approved for final XXCS / execution gold |
| `test_fixture_verified` | Synthetic fixture acknowledged (not real gold) |
| `rejected` | Not selectable for final report |
| `superseded` | Replaced by newer verified result |

Review fields (per history row / review record): `review_status`, `reviewer`, `reviewed_at`, `review_note`, `verification_scope`, `selected_for_report`, optional supersession ids.

Original `executions/*.json` files are never mutated. Reviews live in `execution_reviews/{execution_id}.review.json`.

## Flow

```
import-security-results
        │
prepare-security-review  →  data/review/{case}/{exec}/ package
        │
human fills execution_review.json
        │
import-security-review   →  execution_reviews/ + selected_security_results.json
        │
security-review-summary  →  readiness + metrics
        │
harness-generate         →  XXCS uses selected / reviewer_verified real results only
```

## Synthetic blocking

- Cannot set `overall_status=reviewer_verified` or per-test `reviewer_verified`
- Cannot promote to `data/gold/xxcs/execution/`
- Excluded from `real_execution_coverage` / reviewer-verified coverage
- Fixture path: `test_fixture_verified` + `selected_for_report=false`
- Demo selection requires `--allow-synthetic-demo`

lab_ec_sw synthetic sample was processed as fixture-only; **not** selected for final report.

## Result selection

Priority: selected_for_report → reviewer_verified → non-synthetic → latest reviewed_at → latest executed_at.

Ambiguous ties remain unselected.

Policy: `docs/security_execution_review_policy.md`

## Plan gold vs execution gold

```
data/gold/xxcs/
  plan/          # plan-based gold
  execution/     # human-approved real execution gold only
```

Validation:

- `plan_score` / XXCS document score uses `score_plan_xxcs` (drops text-similarity penalty when executions exist; uses plan completeness)
- `execution_import_score` is informational
- Thresholds were not relaxed

## Final report readiness (lab_ec_sw after fixture review)

- mode: `plan_only`
- ready: true
- selected_count: 0
- reviewer_verified_execution_coverage: 0.0
- synthetic_result_count: 4
- real_execution_count: 0

## CLI

```powershell
python -m document_ai.cli prepare-security-review --case data/cases/lab_ec_sw --execution-id exec-20260717-synthetic-001
python -m document_ai.cli import-security-review --case data/cases/lab_ec_sw --review data/review/lab_ec_sw/exec-20260717-synthetic-001/execution_review.json
python -m document_ai.cli security-review-summary --case data/cases/lab_ec_sw
```

Schema: `schemas/security_test_execution_review.schema.json`

## Lab reviewer procedure (real execution)

1. Import real results (`synthetic=false`).
2. `prepare-security-review` and fill reviewer name/role.
3. Confirm evidence hashes, PASS/FAIL justification, sensitivity.
4. Set `reviewer_verified` + `selected_for_report=true` only for approved tests.
5. `import-security-review` then `security-review-summary` until readiness true.
6. Regenerate XXCS; optionally promote execution gold (blocked for synthetic).

## Future automated runner interface

Runner emits `security_test_execution` JSON → existing import → this review workflow unchanged. No Operation Harness coupling in this sprint.
