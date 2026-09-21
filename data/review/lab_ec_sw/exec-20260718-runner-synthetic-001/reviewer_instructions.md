# Security Execution Review Instructions — lab_ec_sw

Execution: `exec-20260718-runner-synthetic-001`
Synthetic: **True**

## Reviewer checklist

1. Confirm each security_test_id maps to the plan (`security_tests.json`).
2. Confirm actual_result matches attached evidence.
3. Confirm PASS/FAIL judgments are justified (do not invent results).
4. Verify evidence paths and SHA-256 hashes in `evidence_manifest.json`.
5. Ensure sensitive data is not copied into XXCS DOCX.
6. Decide `selected_for_report` per test (final XXCS only).
7. Acknowledge synthetic vs real execution.

## Rules

- Do **not** auto-approve imported results.
- Synthetic executions cannot become human-approved execution gold.
- Prefer `test_fixture_verified` + `selected_for_report=false` for synthetic demos.
- Original execution JSON under `executions/` must not be edited.
