# WWW Short Paper — Frozen Number Snapshot

**Freeze id:** `www_short_paper_v1`  
**Venue (locked):** WWW short paper  
**Claim mode:** **B** (Change Impact primary + same-contract “new” secondary Field F1; fall back to **A** = safety-only if B is too crowded)  
**Holdout seed:** `document-tnr-small-a-holdout-v1`  
**Do not retune on holdout.** Dev may be used for debugging; holdout numbers below are sealed for slides/draft.

## Surviving claim (one line)

Multi-doc Change Impact → writable scope → patch/TRACE; safety measured by  
**μ = (false_patch, unsafe_write, original_broken, unapproved_write)** as one programmatic bench.  
No “first pre-write / first unintended-edit” claims.

## Paper tables (holdout × live) — primary

| mode | n | μ=0 rate | mean μ sum | R@3 | cell F1 | field F1 |
|---|---:|---:|---:|---:|---:|---:|
| live | 7 | **1.000** | 0.000 | 1.000 | 1.000 | 1.000 |
| demo_safe | 7 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |

Full (n=27) and dev (n=20): μ=0 rate = 1.000 for both modes; R@3 ≈ 0.991 / 0.988 (multi-Req `case_026`).  
Source: `reports/paper_safety_first.{md,json,csv}`

## Pilot → μ (RQ3 one-table)

| source | false_patch | unsafe_write | original_broken | unapproved_write | μ=0 |
|---|---:|---:|---:|---:|:---:|
| `pilot_run_01` | 0 | 0 | 0 | 0 | yes |

Key map: `reports/mu_pilot_key_alignment.json` · table: `pilot_mu_table.md`

## Sandbox ablation (practice / counterfactual only)

**Paper sentence (fixed):**  
> Ablation figures are a practice sandbox / counterfactual experiment (devices removed in dry-run), not live execution with safety off.

| variant | mean μ sum | primary μ hit |
|---|---:|---|
| `full` | 0 | — |
| `no_gate` | 2 | unapproved_write + unsafe_write |
| `no_copy_only` | 1 | original_broken |
| `no_closure` | 1 | false_patch |

`expected_hit_rate = 1.0` for all variants. Source: `reports/sandbox_ablation_mu.*` · figure: `figures/fig_ablation_bar.{png,pdf}`

## Secondary Field F1 (plan B, few structured cells)

Holdout × live mean Field F1 = **1.000** on structured cells (`DI_012_PARAM`, `REQ_007_DESC`).  
Not North Star full form-fill — enough for one secondary claim line.  
Source: `field_f1_holdout_live.*`

## Failure-mode live example

`case_025` must-not-touch bait: login (Req.1) mentioned; only Req.7/DI-12 written; μ=0; REQ_001 untouched.  
Source: `examples/failure_mode_live.*` · figure: `figures/fig11_walkthrough.{png,pdf}`

## Camera-ready figures

| file | use |
|---|---|
| `figures/fig_pipeline.{png,pdf}` | pipeline 1-pager |
| `figures/fig_ablation_bar.{png,pdf}` | ablation bars |
| `figures/fig11_walkthrough.{png,pdf}` | Fig.11-style walkthrough |

## Reproduce (do not overwrite freeze without new freeze id)

```bash
PYTHONPATH=src python3 -m document_ai.cli regulatory-bench-paper-tables \
  --out-dir data/eval/www_short_paper_freeze/reports
PYTHONPATH=src python3 -m document_ai.cli regulatory-bench-ablation-table \
  --out-dir data/eval/www_short_paper_freeze/reports
```
