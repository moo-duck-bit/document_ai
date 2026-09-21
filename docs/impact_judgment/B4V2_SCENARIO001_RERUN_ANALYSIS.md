# B4v2 Scenario-001 Rerun Analysis

## 1. Objective

Validate whether B4v2 (facet-based domain-independent consistency) removes the Scenario-001 consistency bottleneck observed after B3v2, **without** forcing PASS or editing frozen evidence.

## 2. Execution Conditions

| Item | Value |
|------|-------|
| Rerun dir | `data/user_scenarios/scenario-001-rerun-b4v2/` |
| Baseline | `scenario-001` PARTIAL frozen |
| Prior rerun | `scenario-001-rerun-b3v2` PARTIAL frozen |
| Inputs | Same CR + MDSR + MDDR hashes |
| Changed component | **B4 only** |
| B3 / B5 code | unchanged |
| Expected impact | unused |
| Frozen outputs as gold | **no** |
| Commit SHA | `bb528ce27d3ccff53b876b8faf50107874c24eda` |

## 3. Freeze Integrity

Pre/post checks: scenario-001, scenario-001-rerun-b3v2, Trial 1, Trial 2 — **not modified** by this rerun (outputs written only under `scenario-001-rerun-b4v2/`).

## 4. Retrieval Stability

Top-k order/ids/scores: **identical** to baseline and B3v2 rerun (`retrieval_identical_to_b3v2_rerun=true`).

## 5. B3 Stability

Impact map identical to B3v2 rerun:

- IMPACTED 6 / NOT_IMPACTED 8 / UNCERTAIN 1  
- Same IDs including MDSR 203, 204, 100, 110  

No B3 drift; change variable is B4 as intended.

## 6. B4 Candidate-level Results

| Candidate | B3 | B4v1 | B4v2 | Evidence | Reason |
|-----------|----|------|------|----------|--------|
| Req.204 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | compatible: actor, action, object, responsibility, constraint; missing: condition_mapping; families CR=mutate / Req=observe | Natural extend of patient activity monitoring |
| Req.110 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | same pattern; Req=observe | API supplying performance records — extend lean |
| Req.203 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | same; Req=mutate | Registration/list — borderline over-include |
| Req.100 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | same; Req=mutate | Auth-code lifecycle — **should be CONFLICT**; FP defense failed |

All decisions carry structured `evidence` + `b3_prior` in `output/trace/consistency_decisions.json`. No “theme keyword miss” reasons.

## 7. B4v1 vs B4v2

| Aspect | B4v1 (in B3v2 rerun) | B4v2 |
|--------|----------------------|------|
| Decision core | POLICY/UX/AUDIT role×theme | Facet compatibility |
| Non-lockout CR | Always NEEDS_REVIEW | Can CONSISTENT |
| Req.204/110 | Blocked | CONSISTENT (intended improvement) |
| Req.100 FP | Deferred (NEEDS_REVIEW) | **Not blocked** (CONSISTENT) — regression vs ideal defense |
| Trace | role=other note | compatible/conflicting/missing facets |

**B4v2 success vs criteria:** theme-miss fixed ✅; evidence traces ✅; related can CONSISTENT ✅; FP defense ❌ for Req.100; not all IMPACTED need CONSISTENT (mixed would be OK) — here over-uniform CONSISTENT.

## 8. B5 Downstream Effects (observe only)

B5 code **not** modified.

| MDSR | B4 | B5 MDDR outcome | Align reason |
|------|----|-----------------|--------------|
| 203 | CONSISTENT | SKIPPED_WITH_REASON | Same ID but design responsibility not evidenced |
| 204 | CONSISTENT | SKIPPED_WITH_REASON | same |
| 110 | CONSISTENT | SKIPPED_WITH_REASON | same |
| 100 | CONSISTENT | **PATCHED** | Shared theme `('감사',)` — lockout/audit-era align |

Findings:

- CONSISTENT candidates **are** passed to B5.
- PATCHED count rose 0→1, but on the **wrong** owner (Req.100).
- Stronger clinical candidates skipped because `_design_aligns` still uses 감사/안내/잠금/로그인 theme pairs.
- MDSR patches apply whenever B4 `allow_auto_patch` (separate from MDDR align) → 4 MDSR CR-appends including FP.

**Next bottleneck:** B5 domain-independent design-responsibility alignment (+ optional B4 FP tightening — analyze only).

## 9. Document Output Analysis

| Check | Result |
|-------|--------|
| CR meaning reflected | **Partial** — literal CR sentence appended under “변경 요청 반영” on MDSR 203/204/100/110 |
| Structure/format preserved | Appears preserved (description append only) |
| Unintended diff | Req.100 MDSR/MDDR received inactive-patient CR under auth-code requirement — **semantic pollution** |
| Unrelated Req changes | Req.100 is the primary unwanted change |
| MDDR propagation | Only Req.100; 204/110/203 design not updated |

Do not treat PATCHED=1 as success — the patched design is the thematic neighbor.

## 10. 3-way Comparison

See `BEFORE_AFTER_COMPARISON.md` table. Headline: B3 unlocked candidates; B4v2 unlocked CONSISTENT; B5 still mis-propagates.

## 11. New Bottleneck

**Primary:** B5 `_design_aligns` (auth/audit/lockout theme pairs) — skips true owners, promotes Req.100 via 감사 keyword.

**Secondary:** B4 over-permissive CONSISTENT on mutate↔mutate neighbors (Req.100) — FP defense incomplete.

**Tertiary:** Patch strategy = whole-CR append (not field-targeted semantics).

## 12. Overall Evaluation

| Component | Grade |
|-----------|-------|
| Retrieval | PASS |
| B3 | STABLE / PARTIAL (prior) |
| B4 | IMPROVED / PARTIAL |
| B5 | BOTTLENECK |
| Documents | PARTIAL / RISKY |
| **Overall** | **PARTIAL** |

## 13. Recommendation

1. **Next development:** B5 domain-independent design-responsibility alignment (root-cause analysis first, same discipline as B3/B4).
2. Optional follow-up (after B5 RCA): B4 FP tightening on object-family mismatch — **no Scenario Req-ID hard-codes**.
3. Future validation only in a **new** dir (e.g. `scenario-001-rerun-b5v2/`); keep this PARTIAL evidence frozen.

**Do not** retune B4/B3 keywords or special-case Req.204/110/100 in this step.

---

## Verdict

**SCENARIO_001_B4V2_PARTIAL**
