# Ablation interpretation (sandbox / practice only)

**Fixed disclaimer for the paper:**  
Ablation is a **practice sandbox / counterfactual** experiment: safety devices are removed in dry-run only. It is **not** live execution with safety off on the original corpus.

## What each removal should hit

| variant | device removed | expected μ | mean μ sum (frozen) |
|---|---|---|---:|
| `full` | none | all zeros | 0 |
| `no_gate` | writable-scope gate | `unapproved_write` + `unsafe_write` | 2 |
| `no_copy_only` | copy-only / write-to-workspace | `original_broken` | 1 |
| `no_closure` | TRACE closure completeness | `false_patch` | 1 |

`expected_hit_rate = 1.0` across Small-A (n=27): each disabled-device run lands on its primary μ term(s).

## How to read RQ3

1. With all devices on (`full`), μ stays 0 — same contract as holdout/live.
2. Removing one device flips the matching μ term — devices are separable, not a single opaque “safe flag.”
3. Do **not** claim that production runs with safety disabled; cite sandbox only.

Numbers: `reports/sandbox_ablation_mu.md` · figure: `figures/fig_ablation_bar.png`.
