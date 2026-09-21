# User Scenario Runner — Limitations

Harness status: **READY_FOR_USER_SCENARIO_TEST** (smoke-tested).

## Auto-patch conditions

- B3 = IMPACTED (MDSR)
- B4 = CONSISTENT and `allow_auto_patch`
- MDDR: design-responsibility aligned → PATCHED else SKIPPED_WITH_REASON / NEEDS_REVIEW

## Forced non-patch / review

| Condition | Outcome |
|-----------|---------|
| B4 CONFLICT | Patch blocked; REVIEW_REQUIRED |
| B4 NEEDS_REVIEW | No auto-patch |
| B3 UNCERTAIN | Listed in REVIEW_REQUIRED |
| No IMPACTED + substantive CR | `NEW_REQUIREMENT_CANDIDATE` flag |
| Outside auth/lock/audit/UX themes | Often empty IMPACTED set → review / new-req flag |

## Not supported in this harness

- Dense embedding retrieval
- XXCS propagation
- New requirement auto-authoring into DOCX
- Form-fill blank-template generation
- Admin-mode product features
- Using `expected_impact` as input
