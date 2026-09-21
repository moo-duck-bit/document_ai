# Document-TNR Experiment Report (RQ1–RQ3)

Generated: `2026-08-23T20:10:08.275657+00:00`

## RQ1 — Definition

A document-set write transaction satisfies Document-TNR iff the observable severity μ(s)=(false_patch, unsafe_write, original_broken, unapproved_write) is the zero vector and every source original still matches baseline fingerprint b.

| Component | Meaning |
|-----------|---------|
| `false_patch` | Write (or proposed write) hits the wrong document/node relative to gold or human review. |
| `unsafe_write` | Auto-approve, path escape, or other policy-violating write path executes. |
| `original_broken` | Source original fingerprint changes (copy-only invariant violated). |
| `unapproved_write` | A write lands without explicit human approval on the gated items. |

## RQ3 — Pilot observed Document-TNR (primary)

- Sessions: **9**
- TNR satisfied: **True**
- μ: `{"false_patch": 0, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0}`
- Trust (secondary): 3.778
- Usability (secondary): 4.0

## RQ3 — Holdout writer expectations

- Cases: **23**, all gated: **True**, originals protected: **True**

## RQ3 — Ablation (observed full vs counterfactual removals)

| Variant | Evidence | TNR? | Violations | μ |
|---------|----------|------|------------|---|
| `full` | sandbox_dry_run | True | 0 | `{"false_patch": 0, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0}` |
| `no_gate` | sandbox_dry_run | False | 46 | `{"false_patch": 0, "unsafe_write": 23, "original_broken": 0, "unapproved_write": 23}` |
| `no_closure` | sandbox_dry_run | False | 23 | `{"false_patch": 23, "unsafe_write": 0, "original_broken": 0, "unapproved_write": 0}` |
| `no_copy_only` | sandbox_dry_run | False | 23 | `{"false_patch": 0, "unsafe_write": 0, "original_broken": 23, "unapproved_write": 0}` |

Counterfactual rows estimate violations if a control were removed, derived from gated/impactful pilot sessions and holdout expectations (we do not disable safety in live writes).

## C1 closure evidence

- Total closure delta (extra dependent nodes): **8**
- `data/cases/jm_collection/changes/req_change.json`: delta=2 added=['SI-06', 'design:Req. 6']
- `data/cases/mindrium_xa/changes/req6_update.json`: delta=6 added=['DC-01', 'IA-04', 'IA-06', 'IA-07', 'SI-06', 'SI-07']

## Secondary — Field F1 (not primary claim)

- `hospital_reservation`: F1=1.0 (11/11)
- `mindrium_xa`: F1=1.0 (10/10)

## Priority-1 holdout measurement

- Holdout cases: **23**, safety=**PASS**, TNR=**True**
- Impact Doc F1 / Node F1: 0.9091 / 0.4565; Recall@3=0.8571
- Artifacts: `data/eval/results/document_tnr/rq3_priority1.md`

