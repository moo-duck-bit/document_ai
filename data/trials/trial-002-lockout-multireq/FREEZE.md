# Trial 2 FREEZE

- trial_id: `trial-002-lockout-multireq`
- overall_result: **PASS**
- reason: **Acceptance Criteria Met**
- trial_2_freeze: `true`

## Rule

Do **not** modify, re-run, or “improve” frozen evidence under this trial directory  
(except adding non-mutating documentation that points here).

Machine-readable freeze: `execution_report.json`  
Human report: `FINAL_TRIAL_REPORT.md`

## Frozen artifact trees

- `input/`
- `expected/` (evaluation-only; never injected into model ranking)
- `reference/`
- `retrieval/lexical_baseline/`
- `retrieval/hybrid/`
- `validation/impact_judgment/`
- `validation/semantic_consistency/`
- `validation/propagation/`
- `generated/patched_mdsr/`
- `generated/patched_mddr/`
- `ACCEPTANCE_CRITERIA.md`
- `FINAL_TRIAL_REPORT.md`
- `execution_report.json`

## PASS meaning (scoped)

NL CR on existing Mindrium XA MDSR/MDDR: find related requirement candidates without Exact-ID,  
separate impact vs semantic-conflict judgment, and perform explicit MDSR→MDDR propagation  
— verified for **this lockout multi-req scenario only**.
