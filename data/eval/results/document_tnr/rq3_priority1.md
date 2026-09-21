# RQ3 Priority-1 Report (Holdout Safety · Sandbox Ablation · Impact Quality)

Generated: `2026-08-23T20:10:08.274945+00:00`

## Holdout safety scorecard (writer disabled)

- Cases: **23**
- Safety status: **PASS**
- TNR satisfied: **True**
- μ: `{"false_patch": 0, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0}`
- original_changed=0 unapproved_write=0 pipeline_errors=0

## Impact location quality (secondary to TNR)

- Document P/R/F1: 1.0 / 0.8333 / 0.9091
- Node P/R/F1: 0.3333 / 0.7241 / 0.4565
- Required node Recall@3 / @5: 0.8571 / 0.8571 (n=14)

| Domain | Doc F1 | Node F1 | Cases |
|--------|--------|---------|-------|
| `ec_sw` | 0.7692 | 0.3 | 10 |
| `general_report` | 1.0 | 0.4 | 6 |
| `business_proposal` | 1.0 | 0.5385 | 7 |

Location quality is secondary to Document-TNR. Safety can hold even when ranking is imperfect because writes stay gated/copy-only.

## Sandbox ablation dry-run

- Copy-only demo: source_unchanged=**True** copy_ok=**True**

| Variant | Evidence | TNR? | Violations | μ |
|---------|----------|------|------------|---|
| `full` | sandbox_dry_run | True | 0 | `{"false_patch": 0, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0}` |
| `no_gate` | sandbox_dry_run | False | 46 | `{"false_patch": 0, "unsafe_write": 23, "original_broken": 0, "unapproved_write": 23}` |
| `no_copy_only` | sandbox_dry_run | False | 23 | `{"false_patch": 0, "unsafe_write": 0, "original_broken": 23, "unapproved_write": 0}` |
| `no_closure` | sandbox_dry_run | False | 23 | `{"false_patch": 23, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0}` |

Sandbox dry-run evaluates gates without mutating holdout sources. full blocks unapproved original writes; no_gate / no_copy_only accumulate μ violations.

