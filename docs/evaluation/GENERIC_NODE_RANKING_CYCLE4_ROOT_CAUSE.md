# Generic Node Ranking Cycle 4 — Root Cause

Baseline: Cycle 3 run `20260801T152942Z_03c260f2`.

## Holdout / Development GR REQUIRED misses

| Case | Gold (template section) | Pred top-1 | Pattern |
|------|-------------------------|------------|---------|
| `v2_hol_gr_concl` | `general_report_v1.conclusion` | `paragraph_0006` | aligned paragraph exists; flat score 0.5 |
| `v2_hol_gr_en` | `general_report_v1.results` | `paragraph_0002` | same |
| `v2_hol_gr_dup` | `general_report_v1.results` | `paragraph_0000` | tie-break by node_id |
| `v2_dev_gr_method` | `general_report_v1.methodology` | `paragraph_*` | same |
| `v2_dev_gr_results` | `general_report_v1.results` | `paragraph_*` | same |
| `v2_dev_gr_dup` / `mixed` | methodology/results | `paragraph_*` | same |

Holdout Node Top-1 = 0.400: 10 REQUIRED; GR misses dominate.

## Answers

1. Gold is template section; prediction emits physical paragraph/heading — **yes**.
2. Heading sometimes competes with paragraph at equal score — **yes**.
3. Section container vs editable block not distinguished in ranking — **yes**.
4. SECTION_ADD / UPDATE intent not extracted — **yes**.
5. Schedule: heading+table both ~0.7; table may not enter equivalence group — **partial**.
6. methodology/conclusion concepts exist as tokens but not as first-class ranking concepts — **weak**.
7. Structural equivalence used in AMBIGUOUS eval groups only; **not** REQUIRED matching — **yes**.
8. `boost_template_alignment_scores` targets template ids never in `review` — **dead boost**.
9. Multiple paragraphs share identical 0.5 score — local specificity unused.
10. Virtual targets not ranked into top for UPDATE (good); not promoted for ADD ranking either.

## Instance metric = 0

`exact_instance_match_rate` counts `metadata.instance_match` on REQUIRED top-1.  
Only EC-SW ranking sets that flag; GR never does. Denominator includes all REQUIRED (37), not duplicate-instance cases → aggregate always ~0.

## Fix direction

- Generic query intent + structural roles + rank tiers.
- Promote evaluation-equivalent template section candidates into ranked review.
- Match REQUIRED via structural equivalence / alignments (evaluation only).
- Calibrate instance metrics: duplicate-only denominator; else N/A.
- Do not touch EC-SW `rank_mdtm_candidates`.
