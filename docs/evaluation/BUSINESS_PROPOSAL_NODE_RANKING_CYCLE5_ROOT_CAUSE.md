# Business Proposal Node Ranking Cycle 5 — Root Cause

Baseline: Cycle 4 run `20260801T163826Z_ab762b81`.

## Primary finding

**Business Proposal has zero `REQUIRED` node-evaluation cases.**

| Split | Impactable BP cases | Mode | Gold nodes |
|-------|--------------------:|------|------------|
| holdout | sched / budget / risk | OPTIONAL | empty |
| development | schedule / budget / risk / org / effect / dup / en | OPTIONAL | empty |

Domain metric:

```
required_top1_hit_rate = hits / count(mode==REQUIRED)
```

With denominator 0 → `_safe_div` → **0.0**. This is a **label-mode / denominator artifact**, not evidence that ranking always fails.

## Runtime predictions (already present)

| Case | Top-1 | Template in top-k |
|------|-------|-------------------|
| hol sched | `heading_0001` | `business_proposal_v1.schedule` @2 |
| hol budget | `heading_0004` | `business_proposal_v1.budget` @2 |
| hol risk | `heading_0006` | `business_proposal_v1.risks` @3 |
| dev risk | `business_proposal_v1.risks` | — |
| dev effect | `business_proposal_v1.expected_outcomes` | — |

So candidate generation + alignment partially work; template IDs often rank #2, not always #1.

## Answers

1. Gold nodes for REQUIRED: **N/A** (no REQUIRED).
2. If promoted, gold should be template IDs `business_proposal_v1.*` (like GR).
3. Predictions lean heading first; aligned template often second.
4. Template sections are promoted into review via generic path.
5. Not mis-routed to `general_report` template — uses `build_business_proposal_template()`.
6. Budget table exists in fixtures but **schedule/table retrieval is GR-only** → BP tables under-scored.
7. Proposal concepts (위험관리, 기대효과, 수행조직) partially covered by generic synonyms; weaker than GR.
8. Alignments exist; evaluation match works for OPTIONAL but OPTIONAL is excluded from Required Top-1.
9. Adapter emits BP nodes; domain metric ignores OPTIONAL.
10. REQUIRED grounding is **not currently label-enabled** for BP.

## Fix direction (no Gold mutation)

- Proposal-specific concepts / intent / table analysis / ranking so template+table beat weak headings.
- Enable BP table retrieval (schedule/budget/org).
- Label audit + `proposed_label_changes.json` (do not apply).
- Report `intent_grounding_top1` from CR→template mapping (no gold read).
- Keep Required Top-1 honest (0 or N/A until labels promoted in a future ticket).
