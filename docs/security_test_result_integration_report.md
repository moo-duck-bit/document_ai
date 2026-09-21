# Security Test Result Integration Report

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


Sprint: **XXCS External Test Result Integration**

## Goal

Document Harness accepts externally performed security test results in a standard JSON format, maps them safely onto existing security test items, updates `actual_result` / `evidence` / `satisfaction`, and regenerates/validates XXCS — without running servers, collecting live logs, or integrating Operation Harness.

## Data flow

```
external results JSON
        │
        ▼
import-security-results (schema + case_id + test ID validation)
        │
        ├─► cases/{case}/executions/{execution_id}.json   (archive)
        └─► cases/{case}/security_test_results.json       (overlay + history)
                │
                ▼
build_effective_security_payload()
  plan: security_tests.json  +  accepted overlay results
                │
                ▼
XXCS render → output_xxcs.docx
                │
                ▼
document-validate (plan metrics + informational execution metrics)
```

## Schema

File: `schemas/security_test_execution.schema.json`

Top-level: `case_id`, `execution_id`, `executed_at`, `executor`, `environment`, `results[]`, optional `synthetic`.

Per result: `security_test_id`, `status` (`PASS|FAIL|NOT_EXECUTED|NOT_APPLICABLE|REVIEW_REQUIRED`), `actual_result`, `evidence[]`, `executed_at`, `executor_note`.

Evidence item: `type` (`text|file|url|log|screenshot|command_output`), `path`, `description`, `sha256`, optional inline `content`.

## Merge policy

See `docs/security_test_result_merge_policy.md`.

Highlights:

- Plan (`security_tests.json`) is never overwritten by import.
- History is preserved per test; latest execution does not blindly replace prior accepted results.
- `NOT_EXECUTED` / `NOT_APPLICABLE` never clear an existing PASS/FAIL.
- `REVIEW_REQUIRED` is never auto-accepted.
- `PASS` without meaningful evidence → warning, not accepted.
- Review statuses: `imported` | `reviewer_verified` | `rejected` | `superseded`.

## Evidence handling

- Relative paths preferred (resolved against results file dir, case dir, `data/executions/{case_id}/`).
- Missing files → warning only.
- SHA-256 computed and stored for existing files.
- DOCX shows type + relative path + short hash — never full log bodies or absolute Windows paths (absolute paths previously corrupted XXCS table extract).

## XXCS render

| Plan fields | Execution fields |
|-------------|------------------|
| Test Method / Procedure / Expected Result | Actual Result / Satisfaction / Evidence |
| linked_req / linked_design | executed_at / executor / execution_id / review_status |

When no accepted overlay exists, placeholders remain `NOT_EXECUTED` / `NOT_COLLECTED`.

## Validation metrics (informational)

| Metric | Meaning |
|--------|---------|
| `execution_coverage` | Share of plan tests with accepted PASS/FAIL |
| `evidence_coverage` | Share with meaningful evidence |
| `executed_result_completeness` | Accepted results with non-empty actual_result |
| `pass_with_evidence_ratio` / `fail_with_evidence_ratio` | Evidence quality among PASS/FAIL |
| `unresolved_review_required_count` | Pending REVIEW_REQUIRED history rows |
| `stale_execution_count` | Older executed history vs accepted batch |
| `plan_test_completeness` / `execution_test_completeness` | Split plan vs execution field fill |

Missing executions do **not** fail validation. Readiness is reported separately via `execution_state`.

## Synthetic sample

Location: `data/executions/lab_ec_sw/security_results.synthetic.json`

| ID | Status | Notes |
|----|--------|-------|
| SI-01 | PASS | command_output evidence (synthetic) |
| IA-01 | FAIL | log evidence (synthetic) |
| UC-01 | NOT_EXECUTED | must not overwrite prior PASS/FAIL |
| DC-01 | REVIEW_REQUIRED | not auto-accepted |

All fixtures are marked `synthetic: true` and labeled **NOT A REAL SECURITY TEST RESULT**.

## Synthetic import results (lab_ec_sw)

| Metric | Value |
|--------|------:|
| MDSR validation | 100.0 |
| MDDR validation | 92.0 |
| XXCS validation | ~95.3 (vs plan-only gold; synthetic actuals diverge from NOT_EXECUTED gold text) |
| Integrated validation | ~95.7 PASS |
| Quality | 96.8 PASS |
| Harness benchmark | 93.2 |
| execution_coverage | 0.059 (2/34 accepted) |
| pass/fail_with_evidence_ratio | 1.0 |
| unresolved_review_required_count | 1 |

## Real vs synthetic

- Real executions: `synthetic: false` (or omitted), human/external evidence paths.
- Synthetic: `synthetic: true`, fixture text in evidence files, provenance `execution_truth: synthetic sample result`.
- Document Harness never auto-infers PASS from plan completeness.

## Boundary with Operation Harness

This sprint implements **import + merge + render + validate only**.

Out of scope:

- Running server commands
- Live log collection / incident analysis
- Coupling to Operation Harness runners

Future runner connection:

1. Operation Harness (or script) emits `security_test_execution` JSON.
2. Call `python -m document_ai.cli import-security-results --case … --results …`.
3. Reviewer verifies REVIEW_REQUIRED / imported rows.
4. `harness-generate` + `document-validate` refresh XXCS.

## CLI

```powershell
python -m document_ai.cli import-security-results `
  --case data/cases/lab_ec_sw `
  --results data/executions/lab_ec_sw/security_results.synthetic.json
```

## Remaining limits

- Only latest-accepted overlay drives XXCS; no UI yet to pick a specific historical execution per test.
- Reviewer verify/reject is data-model ready but no dedicated approve CLI yet.
- Gold XXCS for lab_ec_sw remains plan-oriented; importing real results will lower text similarity until gold is updated under human review.
- Absolute evidence paths must not be written into DOCX cells.

## Suggested next priority

1. **Human-approved XXCS** — review CLI to mark `reviewer_verified` / `rejected`, then freeze gold with approved executions.
2. **Automated security test runner** — emit the same schema from scripts (still Document Harness import only).
3. **Embedding retrieval** — improve few-shot for free_text, orthogonal to execution import.
