# Security Execution Review Policy

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## Purpose

Human reviewers approve or reject imported security test executions before results
appear in a final XXCS report or human-approved execution gold.

Original execution archives under `executions/` are **immutable**.
Review decisions are stored separately under `execution_reviews/`.

## Review statuses

| Status | Meaning |
|--------|---------|
| `imported` | Default after execution import |
| `review_pending` | Awaiting human decision |
| `reviewer_verified` | Human approved for real final report / execution gold |
| `test_fixture_verified` | Synthetic/demo fixture acknowledged (not real gold) |
| `rejected` | Not usable for final report |
| `superseded` | Replaced by a newer verified result |

## Selection priority (final XXCS)

1. Explicit `selected_for_report=true`
2. `reviewer_verified`
3. `synthetic=false`
4. Latest `reviewed_at`
5. Latest `executed_at`

If two candidates remain tied, keep `REVIEW_REQUIRED` / ambiguous and do not auto-pick.

## Synthetic blocking

- `synthetic=true` cannot be `overall_status=reviewer_verified`
- Per-test `reviewer_verified` is blocked for synthetic rows
- Gold promotion to `data/gold/xxcs/execution/` is blocked for synthetic
- Synthetic counts are excluded from real execution coverage metrics
- Demo selection requires `--allow-synthetic-demo` and `test_fixture_verified`
- XXCS render labels synthetic rows as **Synthetic / Demonstration Result**

## Partial approval

An execution may be partially approved:

- Some tests `reviewer_verified` + `selected_for_report=true`
- Others `rejected` or `review_pending`

Rejected tests are never selected. Pending tests stay on plan placeholders.

## Retest / regression

- History is append-only
- FAIL → later PASS: both remain in history; select the verified PASS when approved
- PASS → later FAIL: select the latest verified FAIL when approved
- Import-time `NOT_EXECUTED` never clears prior PASS/FAIL

## Plan gold vs execution gold

| Gold type | Location | Used for |
|-----------|----------|----------|
| plan | `data/gold/xxcs/plan/` (+ existing independent plan gold) | Plan validation (`plan_score`) |
| execution | `data/gold/xxcs/execution/` | Human-approved real execution only |

Do not mix them in one comparison bucket. Thresholds are not relaxed to hide
execution actuals vs plan-only gold; `score_plan_xxcs` excludes execution text
similarity from plan scoring when executions are present.

## Final report readiness

Ready when:

- Every selected result is `reviewer_verified` (or fixture-only under demo flag)
- No synthetic selected (unless demo flag)
- No unresolved `REVIEW_REQUIRED`
- PASS/FAIL selections have evidence
- Evidence hashes validate when claimed verified

Plan-only cases (no selection) remain valid for plan validation.
