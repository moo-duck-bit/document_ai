# B5 Staged Architecture — PR-3 Evidence Provenance Report

**Verdict:** `READY_FOR_STAGED_B5_PR4`  
**Scope:** Evidence provenance / lineage to reduce prior-bleed *observability* issues.  
**Date:** 2026-07-25

---

## 1. PR-3 Objective

Introduce a shared evidence provenance schema so that the same CR source projected through B3 → B4 → B5 is tracked as **one lineage**, not multiple independent corroborations in traces.

Actual path decisions and patches remain **PR-2 parity**. Cross-ID stays **shadow-only**.

---

## 2. Prior Bleed Problem

The same CR concept (e.g. actor/object token) can reappear as:

1. B3 `behavioral_overlap` / `matched_concepts`  
2. B4 `compatible_facets`  
3. B5 direct facet + `b3_prior_*`  

Without lineage, summaries look like many independent reasons. PR-3 records `derived_from` + shared `independent_group` so duplicate counting is visible and avoidable in provenance summaries.

---

## 3. Evidence Schema

Module: `src/document_ai/impact/evidence_provenance.py`

```text
EvidenceItem:
  evidence_id, concept, facet, source_type, source_span,
  document, candidate_id, derived_from[], independent_group,
  evidence_class, notes[]
```

`source_type`: `CR_DIRECT` | `REQUIREMENT_DIRECT` | `DESIGN_DIRECT` | `RETRIEVAL_DERIVED` | `B3_DERIVED` | `B4_DERIVED` | `TRACEABILITY`

`evidence_class`: `DIRECT` | `SUPPORTING` | `GENERIC` | `CONFLICTING` | `DERIVED`

---

## 4. Evidence Lineage Rules

- `independent_group` = hash of normalized **source span** (same span → same group).
- B3/B4/B5 projections of the same concept/facet set `derived_from` to the root CR evidence id and **reuse** that group.
- `b3_prior_*` matched facets are tagged `DERIVED` with note `prior_projection_not_independent_direct`.
- Traceability (`same_req_id`) uses group `traceability:*` and note `traceability_not_ownership`.

---

## 5. Generic vs Direct vs Derived

GENERIC uses **domain-independent** heuristics (no Scenario keyword blacklist):

- membership in existing shared `WEAK_TOKENS` (boilerplate set already in B5)
- high local document frequency across CR/MDSR/MDDR + short form
- high-DF actor-marker-only tokens

DIRECT = CR↔design discriminative content without weak/DF collapse.  
DERIVED = B3/B4/B5 prior projections.  
SUPPORTING = weaker but non-generic links (incl. divergent surface spans).

---

## 6. B3/B4/B5 Handoff

| Stage | New evidence | Reused (derived) |
|-------|--------------|------------------|
| B3 | CR concept seeds if missing | `matched_concepts`, `behavioral_overlap` → `B3_DERIVED` |
| B4 | facet root if missing | `compatible_facets` → `B4_DERIVED`; conflicts → `CONFLICTING` |
| B5 | CR/DESIGN direct hits | `b3_prior_*` → `B3_DERIVED` same group |

Built as a **sidecar** in `align_design_candidate` after the unchanged confidence formula.

---

## 7. Duplicate-Count Prevention

`summarize_evidence_items`:

- `direct_independent_count` = unique groups with class DIRECT  
- `derived_prior_count` counts DERIVED / B3_DERIVED / B4_DERIVED items  
- Derived items **do not** add new direct independent groups  

**Confidence formula for B5c is unchanged** (actual parity). Provenance summaries are for traces / shadow / future safety.

---

## 8. Shadow Comparison Improvements

`design_candidate_shadow_comparison` rows now include:

- `direct_independent_count`
- `supporting_independent_count`
- `generic_count`
- `derived_prior_count`
- `conflicting_count`
- `unique_independent_groups`
- `evidence_lineage_summary`

Winner selection still forbidden.

New artifact: `output/trace/evidence_provenance.json`

---

## 9. Tests

`tests/test_b5_staged_pr3_evidence_provenance.py` — A–J + prior-bleed + false-friend.

---

## 10. Actual Path Parity

- Same `discover_design_candidates` (same-ID)  
- Same B5b confidence / B5c thresholds  
- Same `allow_mdsr_patch` / outcomes  
- Provenance attached under `structured_evidence.provenance` only  

Existing PR-1/PR-2/B5v2 suites remain green.

---

## 11. Full pytest

```text
python -m pytest -q
→ 417 passed in ~2m (0 failed, 0 skipped)
```

Baseline was 405; PR-3 adds provenance tests. No regressions.

---

## 12. Freeze Integrity

Unmodified / not re-run:

- scenario-001, b3v2, b4v2, b5v2  
- trial-001-mindrium-xa, trial-002-lockout-multireq  

---

## 13. Known Limitations

- cross-ID still shadow only  
- actual owner selection not changed  
- full semantic false-friend resolution not complete (span divergence notes only)  
- Atomic Change Unit not implemented  
- whole-CR append unchanged  
- B6 not implemented  
- confidence formula not yet provenance-gated (by design this PR)

---

## 14. PR-4 Recommendation

Use provenance summaries to **gate** EXTEND/PATCH (e.g. reject generic-only / prior-only opens) **behind a feature flag**, with synthetic golden parity first — still without Scenario Req hard-codes or cross-ID activation until gated.

**Final judgment:** `READY_FOR_STAGED_B5_PR4`
