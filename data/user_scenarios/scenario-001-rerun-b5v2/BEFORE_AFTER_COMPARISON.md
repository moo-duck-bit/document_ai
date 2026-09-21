# Before / After — Scenario-001 Baseline → B3v2 → B4v2 → B5v2

## 4-way comparison

| Metric | Baseline | B3v2 | B4v2 | B5v2 |
|--------|----------|------|------|------|
| Overall | PARTIAL | PARTIAL | PARTIAL | **PARTIAL** |
| Retrieval | Top-k | identical | identical | **identical** |
| IMPACTED | 0 | 6 | 6 | **6** |
| UNCERTAIN | 7 | 1 | 1 | **1** |
| NOT_IMPACTED | 8 | 8 | 8 | **8** |
| B4 CONSISTENT | 0 | 0 | 4 | **4** |
| B4 CONFLICT | 0 | 0 | 0 | **0** |
| B4 NEEDS_REVIEW | — | 4 | 0 | **0** |
| B5 PATCH_EXISTING | — | — | (theme/legacy) | **1** (204) |
| B5 EXTEND_EXISTING | — | — | — | **2** (100, 110) |
| NEW_DESIGN | — | — | — | **0** |
| B5 SKIP | — | — | 3 (theme miss) | **1** (203) |
| B5 NEEDS_REVIEW | — | 4 | 0 | **0** |
| MDSR patched count | 0 | 0 | **4** (203/204/100/110) | **3** (204/100/110) |
| MDDR patched count | 0 | 0 | **1** (100 only) | **3** (204/100/110) |
| False propagation | n/a | n/a | **100 via 감사** | **100 via weak EXTEND** (감사 path gone) |

## Candidate-level B5

| Requirement | B3 | B4 | B5v1 (B4v2 rerun) | B5v2 | Design Target | Evidence | Final Action |
|-------------|----|----|-------------------|------|---------------|----------|--------------|
| Req.204 | IMPACTED | CONSISTENT | SKIP (theme miss) | **PATCH_EXISTING** | MDDR 204 | cr_mddr patient tokens; facets actor/action/object | MDSR+MDDR patch |
| Req.110 | IMPACTED | CONSISTENT | SKIP (theme miss) | **EXTEND_EXISTING** | MDDR 110 | cr_mddr `대시보드에서`; novel conditions | MDSR+MDDR patch |
| Req.203 | IMPACTED | CONSISTENT | SKIP + **MDSR still patched** | **SKIP** | MDDR 203 | cr_mddr=[]; boilerplate without CR | no MDSR/MDDR patch |
| Req.100 | IMPACTED | CONSISTENT | **PATCH via 감사** | **EXTEND_EXISTING** | MDDR 100 | cr_mddr=`[해당]` weak; not 감사 pair | MDSR+MDDR patch (**residual FP**) |

## MDSR safety gate (B4v2 vs B5v2)

| Req | B4v2 MDSR | B5v2 MDSR | Notes |
|-----|-----------|-----------|-------|
| 203 | patched | **not patched** | gate works |
| 204 | patched | patched | allow_mdsr_patch True |
| 100 | patched | patched | residual FP still opens gate |
| 110 | patched | patched | allow_mdsr_patch True |

## Stage change causes

1. Baseline→B3v2: IMPACTED unlocked; B4 theme-miss → no patches.
2. B3v2→B4v2: CONSISTENT×4; MDSR append×4; MDDR only 100 via audit theme.
3. B4v2→B5v2: Retrieval/B3/B4 stable. Audit-theme align removed. 203 SKIP+no MDSR. 204/110 useful prop. **100 still EXTEND** on weak content overlap.
