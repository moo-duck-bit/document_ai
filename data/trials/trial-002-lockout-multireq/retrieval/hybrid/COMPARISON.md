# Hybrid Retrieval Comparison

- created_at: `2026-07-22T21:51:30Z`
- lexical_baseline: preserved under `retrieval/lexical_baseline/`
- expected_impact_used_in_retrieval: `false`
- semantic channel: TF-IDF cosine (project embedding backend; no neural model dep)

## Focus ranks by document (document-aware)

| Req | Doc | lexical | semantic | hybrid |
|-----|-----|--------:|---------:|-------:|
| Req. 105 | MDSR | 13 | 8 | 8 |
| Req. 105 | MDDR | 1 | 1 | 1 |
| Req. 103 | MDSR | 2 | 3 | 2 |
| Req. 103 | MDDR | 4 | 2 | 3 |
| Req. 6 | MDSR | 3 | 5 | 5 |
| Req. 6 | MDDR | None | 9 | 13 |

## Top-5 FP vs expected impacted

### lexical
- rank 5: Req. 101 (MDSR)

### semantic
- rank 4: Req. 101 (MDSR)

### hybrid
- rank 4: Req. 101 (MDSR)

