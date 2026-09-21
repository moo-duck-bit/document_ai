# Before / After — Scenario-001 Baseline vs B3v2 vs B4v2

## 3-way comparison

| Metric | Baseline | B3v2 Rerun | B4v2 Rerun |
|---|---:|---:|---:|
| Overall | PARTIAL | PARTIAL | **PARTIAL** |
| Retrieval candidates | Top-k stable | identical | **identical** |
| IMPACTED | 0 | 6 | **6** |
| UNCERTAIN | 7 | 1 | **1** |
| NOT_IMPACTED | 8 | 8 | **8** |
| B4 CONSISTENT | 0 | 0 | **4** |
| B4 CONFLICT | 0 | 0 | **0** |
| B4 NEEDS_REVIEW | 0 (no IMPACTED MDSR gated) | 4 | **0** |
| B5 PATCHED | 0 | 0 | **1** |
| B5 SKIPPED_WITH_REASON | 0 | 0 | **3** |
| MDSR patched IDs | [] | [] | 203, 204, 100, 110 |
| MDDR patched IDs | [] | [] | **100 only** |
| CR reflected in docs | No | No | **Partial** (MDSR CR-append; MDDR wrong owner) |
| Human review required | yes | yes | **yes** |

## Candidate-level B4

| Candidate | B3 | B4v1 | B4v2 | Evidence (B4v2) | Reason (short) |
|-----------|----|------|------|-----------------|----------------|
| Req.204 | IMPACTED | NEEDS_REVIEW (`role=other`) | CONSISTENT | compat: action, actor, object, responsibility, constraint; miss: condition_mapping | CR mutate / Req observe — extend compatible |
| Req.110 | IMPACTED | NEEDS_REVIEW | CONSISTENT | same facet pattern | Dashboard API observe — extend lean |
| Req.203 | IMPACTED | NEEDS_REVIEW | CONSISTENT | same | Registration manage — weaker fit but allowed |
| Req.100 | IMPACTED | NEEDS_REVIEW | CONSISTENT | same (over-broad) | Auth-code mutate — **FP not defended** |

## Stage change causes

1. **Baseline → B3v2**: B3 domain-independent IMPACTED unlocked candidates; B4v1 lockout themes → all NEEDS_REVIEW; no patches.
2. **B3v2 → B4v2**: Retrieval/B3 unchanged. B4 facet gate → 4× CONSISTENT. MDSR auto-append applied. B5 MDDR align still auth/audit keyword based → only Req.100 propagates.

## Answers

1. Retrieval changed? **No**
2. B3 changed? **No** (identical to B3v2)
3. B4 changed? **Yes** — NEEDS_REVIEW 4 → CONSISTENT 4
4. Theme-keyword-miss path? **Eliminated** for these candidates
5. Req.100 FP defended? **No** (CONSISTENT — B4 residual risk)
6. B5 new bottleneck? **Yes** — `_design_aligns` lockout/audit themes; wrong MDDR patched
7. Confidence-alone CONSISTENT? Facet lists present; confidence high but not sole gate — still over-permissive on object/responsibility for neighbors
