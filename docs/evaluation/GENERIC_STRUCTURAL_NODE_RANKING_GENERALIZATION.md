# Generic Structural Node Ranking (Cycle 4)

Comparison vs Cycle 3 run `20260801T152942Z_03c260f2`.

New run: `20260801T163826Z_ab762b81`  
Immutable priors: `20260801T062321Z_c70af996`, `20260801T072116Z_cbdca939`, `20260801T143206Z_e6bd5201`, `20260801T152942Z_03c260f2`.

## Root cause (summary)

See `GENERIC_NODE_RANKING_CYCLE4_ROOT_CAUSE.md`.

- Gold uses template section IDs; predictions emitted only physical paragraphs with flat score 0.5.
- Structural alignments existed but were unused for REQUIRED top-1.
- `boost_template_alignment_scores` targeted template IDs never present in `review`.
- Exact Instance Match used all REQUIRED cases as denominator; `instance_match` only set by EC-SW.

## Changes

| Area | Change |
|------|--------|
| Query intent | `domain_packs/generic/query_intent.py` — SECTION/TABLE/ADD/… |
| Structural match | `structural_match.py` — role scores + TIER_0..6 |
| Ranking | Promote eval-equivalent template sections; rank before emit |
| Parent/child | Heading context + direct/inherited match |
| Table-aware | Schedule/budget prefers TABLE roles |
| Eval | REQUIRED match via evaluation alignments / equivalence groups |
| Instance metrics | Duplicate-only denominator; else N/A |

## Comparison

| Metric | Cycle 3 | Cycle 4 | Delta |
|--------|--------:|--------:|------:|
| Holdout Document F1 | 0.952 | 0.952 | 0 |
| Holdout Node Top-1 | 0.400 | 0.700 | +0.300 |
| Holdout Required Recall@3 | 0.400 | 0.700 | +0.300 |
| Holdout Stable Node Top-1 | ~0.70 | 1.000 | + |
| Development Node Top-1 | 0.619 | 0.810 | +0.191 |
| Holdout E2E | 0.950 | 0.950 | 0 |
| Holdout Unsafe | 0.000 | 0.000 | 0 |
| General Report Node Top-1 | 0.000 | 1.000 | +1.000 |
| Business Proposal Node Top-1 | 0.000 | 0.000 | 0* |
| Exact Instance Match | 0.000 | N/A | calibrated |
| Duplicate Review Correctness | N/A | N/A | 0 dup cases |

\* BP domain `required_top1_hit_rate` stays 0 because holdout/dev BP REQUIRED labeled nodes are empty or not scored in that domain aggregate.

### Regression

| Metric | Cycle 3 | Cycle 4 |
|--------|--------:|--------:|
| Document F1 | 1.000 | 1.000 |
| E2E | 1.000 | 1.000 |
| Node Top-1 | 0.692 | 1.000 |
| Unsafe | 0.000 | 0.000 |

### Domains

| Domain | E2E | Unsafe | Required Top-1 |
|--------|----:|-------:|---------------:|
| EC-SW | 0.932 | 0.000 | 0.788 |
| General Report | 1.000 | 0.000 | 1.000 |
| Business Proposal | 1.000 | 0.000 | 0.000 |

### Instance metrics

- Duplicate cases: 0
- Exact Instance Match: N/A
- Denominator: N/A (single-instance only)
- Not applicable: 37 REQUIRED

## Safety

Original/examples/freeze unchanged; Wrong Auto-route 0; Unauthorized writer 0; Unsafe auto patch 0; Protocol OK.

## Remaining

- Holdout Node Top-1 0.700 (&lt; some aspirational 0.80 recall targets)
- BP REQUIRED top-1 aggregate still 0 (label coverage / mode mix)
- One SAFE_FAILURE residual on EC-SW semantic OPTIONAL (unchanged pattern)
