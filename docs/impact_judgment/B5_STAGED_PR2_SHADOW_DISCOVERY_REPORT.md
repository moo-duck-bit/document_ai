# B5 Staged Architecture — PR-2 Shadow Discovery Report

**Verdict:** `READY_FOR_STAGED_B5_PR3`  
**Scope:** Cross-ID design candidate discovery in **SHADOW EVALUATION** only.  
**Date:** 2026-07-25

---

## 1. PR-2 Objective

Add an expanded Design Candidate Pool (same-ID + B3 IMPACTED MDDR + optional UNCERTAIN MDDR) and run B5b alignment for **observation**, while keeping the actual propagation / patch path identical to PR-1.

> **Shadow candidate comparison does not select a new owner.**

---

## 2. Previous PR-1 Behavior

| Path | Behavior |
|------|----------|
| B5a actual | `discover_design_candidates` → same-ID MDDR only |
| B5b / B5c | Align + decide on that single candidate |
| Traces | `design_candidates.json`, `responsibility_alignment.json`, `propagation_decisions.json`, `propagation_trace.json` |

PR-2 **does not** change that actual path.

---

## 3. Shadow Candidate Sources

| Source key | Meaning |
|------------|---------|
| `same_id` | Same Req ID MDDR (actual-path anchor) |
| `b3_impacted_mddr` | B3 judgment `IMPACTED` on document `MDDR` |
| `optional_b3_uncertain_mddr` | B3 `UNCERTAIN` MDDR **only if** retrieval evidence gate passes |

`sources` are **discovery provenance**, not ownership evidence.

API: `discover_design_candidates_shadow(...)`  
Actual API unchanged: `discover_design_candidates(...)` remains same-ID only.

---

## 4. B3 MDDR Handoff

`build_propagation_plan(..., b3_decisions=...)` already receives full B3 decision dicts from the runner.

Shadow discovery filters:

- `document == "MDDR"`
- `judgment == "IMPACTED"` → always eligible (if block indexed)
- `judgment == "UNCERTAIN"` → only if `retrieval_rank is not None` **and** (`confidence >= 0.25` **or** non-empty `matched_concepts`)

No Req-ID hard-codes (e.g. Req.17 enters only via B3 + index).

---

## 5. Dedup Policy

Key: `(design_id, document)`.

If the same MDDR appears from multiple sources, **one** candidate is kept and `sources` are merged (sorted by source priority).

Example: same-ID + B3 IMPACTED → `sources: ["same_id", "b3_impacted_mddr"]`.

---

## 6. Candidate Cap Policy

Constant: `SHADOW_CANDIDATE_CAP = 8` (contract band 5–8; **not** scenario-tuned).

Fill order:

1. **Always keep** all `same_id` candidates  
2. Fill remaining slots by min source priority, then `retrieval_rank`, then `design_id`  
   - Priority: `same_id` (0) < `b3_impacted_mddr` (1) < `optional_b3_uncertain_mddr` (2)

Rationale: preserve actual-path observability; prefer IMPACTED over optional UNCERTAIN; never use Req-ID or domain keywords for ranking.

---

## 7. Actual vs Shadow Separation

| Concern | Actual | Shadow |
|---------|--------|--------|
| Discovery | `discover_design_candidates` | `discover_design_candidates_shadow` |
| Alignment | B5b → feeds B5c | B5b via `evaluate_shadow_candidates` |
| Decision | B5c `decide_propagation` | **Not run** for cross-ID |
| `allow_mdsr_patch` | From actual outcome only | Never set from shadow |
| DOCX apply | `apply_b4_b5_patches(traces)` | Never consumes shadow |

Code comments and shadow `note` fields state explicitly that comparison does not select a new owner.

---

## 8. Shadow Trace Schema

Runner writes (in addition to PR-1 traces):

| File | Content |
|------|---------|
| `design_candidates_shadow.json` | Per-requirement shadow pool + `sources` |
| `responsibility_alignment_shadow.json` | Per-candidate B5b rows (`is_actual_candidate`, evidence, confidence) |
| `design_candidate_shadow_comparison.json` | Actual candidate vs shadow rows (`direct_evidence` / `generic_evidence` / `conflicts`) |

Actual traces (`design_candidates.json`, `propagation_trace.json`, …) remain same-ID / B5c based.

---

## 9. Synthetic Tests

`tests/test_b5_staged_pr2_shadow_discovery.py`

| ID | Coverage |
|----|----------|
| A | Actual same-ID discovery unchanged |
| B | B3 IMPACTED MDDR in shadow pool |
| C/D | Dedupe + sources merge |
| E | Cross-ID shadow alignment executed |
| F/G/H | Cross-ID cannot change decision / `allow_mdsr_patch` / eligible Req IDs |
| I | Cap |
| J | Legacy façade / plan parity |
| K | Weak same-ID + stronger cross-ID → actual unchanged; cross only in shadow |
| + | UNCERTAIN gate; shadow schema serialization |

---

## 10. Behavior Parity Evidence

- Actual candidate still from `discover_design_candidates` (same-ID).
- With vs without B3 IMPACTED MDDR: identical `propagation_decision` and `allow_mdsr_patch`.
- Existing PR-1 / B5v2 suites remain green.

---

## 11. Full pytest

```text
python -m pytest -q
→ 405 passed in 121.74s (0 failed, 0 skipped)
```

Baseline was 395; PR-2 adds `test_b5_staged_pr2_shadow_discovery.py` (+10). No regressions.

---

## 12. Freeze Integrity

**Not modified / not re-run:**

- `data/user_scenarios/scenario-001/`
- `data/user_scenarios/scenario-001-rerun-b3v2/`
- `data/user_scenarios/scenario-001-rerun-b4v2/`
- `data/user_scenarios/scenario-001-rerun-b5v2/`
- `data/trials/trial-001-mindrium-xa/`
- `data/trials/trial-002-lockout-multireq/`

---

## 13. Known Limitations

- cross-ID still **not** active in actual decision  
- B5b evidence semantics unchanged  
- evidence provenance / prior bleed unresolved  
- Atomic Change Unit not implemented  
- whole-CR append unchanged  
- B6 not implemented  
- Shadow does not promote better cross-ID owners (by design)

---

## 14. PR-3 Recommendation

Enable a **gated** path from shadow comparison → optional NEEDS_REVIEW bias or explicit owner promotion **only after**:

1. Shadow quality review on frozen Scenario-001 evidence (read-only analysis, or new non-overwriting run folder)  
2. Stronger B5b direct-vs-generic evidence rules (without Scenario hard-codes)  
3. Clear feature flag for actual cross-ID activation

Do **not** jump straight to patching cross-ID owners without those gates.

**Final judgment:** `READY_FOR_STAGED_B5_PR3`
