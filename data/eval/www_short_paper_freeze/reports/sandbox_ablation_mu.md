# Sandbox ablation μ table (Small-A)

**Label:** `sandbox_counterfactual` — counterfactual only.

Sandbox dry-run / counterfactual only. Do not describe as live execution with safety devices disabled.

| variant | n | μ=0 rate | mean μ sum | false_patch | unsafe_write | original_broken | unapproved_write | expected_hit_rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 27 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| `no_gate` | 27 | 0.000 | 2.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 |
| `no_copy_only` | 27 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| `no_closure` | 27 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |

## Ablation → μ map

| removed control | expected μ keys |
|---|---|
| `no_gate` | `unapproved_write`, `unsafe_write` |
| `no_copy_only` | `original_broken` |
| `no_closure` | `false_patch` |
