# B5 Staged Architecture — PR-1 Implementation Report

**Verdict:** `READY_FOR_STAGED_B5_PR2`  
**Scope:** Structural refactor only — B5v2 behavior parity preserved.  
**Date:** 2026-07-25

---

## 1. PR-1 Objective

Separate B5 into staged interfaces **without** changing semantic behavior:

| Stage | Role |
|-------|------|
| **B5a** | Design candidate discovery |
| **B5b** | Responsibility alignment / evidence |
| **B5c** | Propagation decision (PATCH/EXTEND/SKIP/NEW/REVIEW) |

Keep `assess_design_propagation` and `build_propagation_plan` as legacy façades. Add staged traces for future PR-2 wiring. **No** cross-ID, ACU, B6, threshold, or scenario rerun.

---

## 2. Previous Structure

Pre-PR-1, discovery + alignment + decision were fused:

- `build_propagation_plan` did same-ID lookup inline (`by_key.get((req_id, "MDDR"))`).
- `assess_design_propagation` both scored evidence **and** returned the propagation enum.
- Runner wrote only `propagation_trace.json`.

---

## 3. B5a Interface

**API:** `discover_design_candidates(requirement_id, blocks_by_key) -> list[DesignCandidate]`

**`DesignCandidate` fields:** `requirement_id`, `design_id`, `document`, `sources`, `retrieval_rank`, `retrieval_evidence` (+ internal `block`).

**PR-1 behavior:** same-ID MDDR only; `sources=["same_id"]`. Empty list if missing. **No** PATCH/EXTEND/SKIP.

> same-ID-only is for **parity**, not an ownership claim in the architecture contract.

---

## 4. B5b Interface

**API:** `align_design_candidate(cr_text, mdsr, mddr, *, decision, b3_prior) -> AlignmentResult`

Reuses B5v2 facet / Jaccard / actor / action evidence computation **unchanged**.  
`alignment="EVIDENCE_COMPUTED"`; decision deferred to B5c. Internal `_signals` carry live `PropagationEvidence` for B5c parity.

---

## 5. B5c Interface

**API:** `decide_propagation(*, requirement_id, design_id, alignment, decision) -> PropagationDecisionResult`

Maps alignment evidence → `PATCH_EXISTING` / `EXTEND_EXISTING` / `NEW_DESIGN_CANDIDATE` / `SKIP` / `NEEDS_REVIEW` with **identical** B5v2 thresholds and reason strings.

---

## 6. Legacy Façade Compatibility

| API | Behavior |
|-----|----------|
| `assess_design_propagation(...)` | Calls B5b → B5c; returns `(decision, PropagationEvidence, confidence, reason)` |
| `build_propagation_plan(..., return_stages=False)` | Default: still `list[PropagationTrace]` |
| `build_propagation_plan(..., return_stages=True)` | `(traces, staged)` for runner |

Orchestration path: **B5a → B5b → B5c** then existing outcome / `allow_mdsr_patch` / snippet logic.

Existing call sites (tests, runner) remain valid without API removal.

---

## 7. Trace Schema

Runner still writes `output/trace/propagation_trace.json`.

**New (PR-1):**

| File | Stage | Minimum fields |
|------|-------|----------------|
| `design_candidates.json` | B5a | `requirement_id`, candidates with `design_id` + `sources=["same_id"]`, `candidate_count` |
| `responsibility_alignment.json` | B5b | alignment, matched_facets, evidence, reason, confidence |
| `propagation_decisions.json` | B5c | propagation_decision, reason, confidence, evidence |

Cross-ID / B3 IMPACTED MDDR **not** connected yet.

---

## 8. Behavior Parity Evidence

Synthetic fixtures (no scenario freeze rerun):

- B5a selects the same same-ID MDDR as previous inline lookup.
- B5b + B5c ↔ `assess_design_propagation` decision / confidence / reason / evidence dict equality.
- `build_propagation_plan` propagation_decision matches façade for PATCH and SKIP cases.
- Existing `tests/test_b5v2_propagation.py` (A–G + plan) still pass.

---

## 9. Test Results

**PR-1 suite:** `tests/test_b5_staged_pr1_parity.py`  
**B5v2 suite:** `tests/test_b5v2_propagation.py`  
Together: **22 passed** (pre-full-suite check).

Full regression:

```text
python -m pytest -q
→ 395 passed in 155.00s (0 failed, 0 skipped)
```

Baseline was 382; PR-1 adds staged parity tests (`test_b5_staged_pr1_parity.py`). No regressions.

Covered:

- A. B5a same-ID discovery  
- B. B5b alignment parity  
- C. B5c PATCH / EXTEND|PATCH / SKIP / NEEDS_REVIEW / NEW_DESIGN  
- D. Legacy assess façade parity  
- E. build_propagation_plan decision parity  
- F. Staged trace serialization + default return type  

---

## 10. Freeze Integrity

**Not modified / not re-run:**

- `data/user_scenarios/scenario-001/`
- `data/user_scenarios/scenario-001-rerun-b3v2/`
- `data/user_scenarios/scenario-001-rerun-b4v2/`
- `data/user_scenarios/scenario-001-rerun-b5v2/`
- Trial 1 / Trial 2 freezes

---

## 11. Known Limitations

Intentionally **out of PR-1** (unchanged defects):

- same-ID-only discovery intentionally preserved  
- cross-ID not active yet  
- B3 IMPACTED MDDR pool (e.g. Req.17) not connected  
- prior bleed (B3/B4 → B5) not fixed yet  
- whole-CR append not fixed yet  
- EXTEND weak-token residual (Req.100) not fixed yet  
- Atomic Change Unit not implemented  
- B6 Patch Planning not implemented  
- No threshold / keyword / Req-ID hard-code changes  

---

## 12. PR-2 Readiness

PR-1 unlocks PR-2 **dataflow** changes against stable interfaces:

1. Expand B5a candidate sources (cross-ID / B3 IMPACTED MDDR) without rewriting decision code.
2. Keep B5b/B5c contracts; tighten alignment / EXTEND semantics under parity tests.
3. Introduce ACU + B6 on top of staged traces.

**Final judgment:** `READY_FOR_STAGED_B5_PR2`
