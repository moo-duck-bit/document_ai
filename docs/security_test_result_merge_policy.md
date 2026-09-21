# Security Test Result Merge Policy

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


Document Harness separates **plan data** (`security_tests.json`) from **execution overlay**
(`security_test_results.json`). External results are archived under `executions/{execution_id}.json`.

## Data layers

| Layer | File | Mutable by import |
|-------|------|-------------------|
| Plan | `security_tests.json` | No |
| Overlay | `security_test_results.json` | Yes |
| Archive | `executions/exec-*.json` | Append-only |

## Import validation

1. Payload must match `schemas/security_test_execution.schema.json` (lightweight validator).
2. `case_id` must match `input.json` / case directory.
3. Each `security_test_id` must resolve to a plan test (`SI-01` → `SI-01-T01` allowed).
4. Duplicate `security_test_id` within one execution file is rejected.
5. Duplicate `execution_id` import is rejected.

## Per-test history

- Each plan test keeps `history[]` of all imported results.
- `accepted` holds the currently effective result for XXCS render.
- History is never deleted when a newer execution arrives.

## Acceptance rules (`accepted`)

| Incoming status | Effect on `accepted` |
|-----------------|----------------------|
| `PASS` | Accepted only if meaningful evidence exists |
| `FAIL` | Accepted if timestamp ≥ current accepted |
| `NOT_EXECUTED` | **Never** overwrites existing `PASS`/`FAIL` |
| `NOT_APPLICABLE` | **Never** overwrites existing `PASS`/`FAIL` |
| `REVIEW_REQUIRED` | Stored in history only; **never** auto-accepted |

Additional rules:

- `PASS` without evidence → import warning; not auto-accepted.
- `reviewer_verified` accepted result is superseded only by another `reviewer_verified` result with a newer `executed_at`.
- Latest execution batch sets `accepted_execution_id` metadata when `--accept` is used (default); per-test `accepted` still follows rules above.

## Review statuses

| Status | Meaning |
|--------|---------|
| `imported` | Default after CLI import |
| `reviewer_verified` | Human approved for XXCS |
| `rejected` | Discarded for acceptance |
| `superseded` | Replaced by newer verified result |

`REVIEW_REQUIRED` imports remain `imported` until a reviewer explicitly verifies.

## Evidence

- Relative paths resolved against execution file directory, case dir, and `data/executions/{case_id}/`.
- Missing files → warning; does not fail import.
- SHA-256 computed and stored for existing files.
- DOCX shows evidence summary (type, path/URL, short hash) — not full log bodies.

## XXCS render

| Field group | Source |
|-------------|--------|
| Test Method / Procedure / Expected Result | Plan (`security_tests.json`) |
| Actual Result / Satisfaction / Evidence / Executed at / Executor | Accepted overlay |

When no accepted execution exists, plan placeholders (`NOT_EXECUTED`, `NOT_COLLECTED`) remain.

## Validation

Execution metrics (`execution_coverage`, `evidence_coverage`, etc.) are **informational**.
Missing executions do **not** fail document validation; they appear as readiness signals.
