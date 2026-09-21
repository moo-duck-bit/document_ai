# Safety-first results (Small-A regulatory_bench)

Holdout seed: `document-tnr-small-a-holdout-v1`

Order: **μ=0 rate → μ terms → R@3 → cell F1 → field F1 (secondary)**.

## Split: full

| mode | n | μ=0 rate | mean μ sum | false_patch | unsafe_write | original_broken | unapproved_write | R@3 | cell F1 | field F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| demo_safe | 27 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.991 | 1.000 | 1.000 |
| live | 27 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.991 | 1.000 | 1.000 |

## Split: holdout

| mode | n | μ=0 rate | mean μ sum | false_patch | unsafe_write | original_broken | unapproved_write | R@3 | cell F1 | field F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| demo_safe | 7 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| live | 7 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |

## Split: dev

| mode | n | μ=0 rate | mean μ sum | false_patch | unsafe_write | original_broken | unapproved_write | R@3 | cell F1 | field F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| demo_safe | 20 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.988 | 1.000 | 1.000 |
| live | 20 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.988 | 1.000 | 1.000 |

