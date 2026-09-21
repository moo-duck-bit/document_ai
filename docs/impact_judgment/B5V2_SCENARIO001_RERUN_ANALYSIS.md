# B5v2 Scenario-001 Rerun Analysis

## 1. Objective

Validate B5v2 (responsibility/facet design propagation + MDSR safety gate) on the same unseen inactive-patient CR without forcing PASS or editing frozen evidence.

## 2. Execution Conditions

| Item | Value |
|------|-------|
| Dir | `data/user_scenarios/scenario-001-rerun-b5v2/` |
| Commit | `52c3af5a4ae045ec0efb79243975d1cda238e3dc` |
| Versions | B3v2 + B4v2 + **B5v2** |
| Changed component | **B5v2 only** |
| Inputs | Same CR/MDSR/MDDR hashes as baseline |
| Frozen outputs as gold | **no** |

## 3. Freeze Integrity

Baseline, B3v2, B4v2, Trial 1, Trial 2 — not modified (outputs only under this new dir).

## 4. Retrieval / B3 / B4 Stability

| Check | Result |
|-------|--------|
| Retrieval Top-k vs B4v2 | **identical** |
| B3 judgments | **identical** (6 / 8 / 1) |
| B4 statuses | **identical** (4 CONSISTENT) |

No upstream regression from B5 change.

## 5. B5 Candidate-level Results

See `BEFORE_AFTER_COMPARISON.md` table.

### Req.100 false propagation

**B4v2 mechanism (eliminated):**  
`_design_aligns` theme pair `src=('감사',)` → MDDR PATCH despite CR not about audit.

**B5v2 mechanism (observed):**  
`propagation_decision=EXTEND_EXISTING`  
- `cr_mddr_content=['해당']` (weak)  
- `obj_jaccard_cr_mddr≈0.016`  
- `mdsr_mddr` still large (auth-code corpus)  
- facets include actor/action/object via B3 priors + weak token  
- reason cites scope extension / novel CR terms — **not** 감사 theme  

**Conclusion:** Audit-theme false path **removed**. Residual wrong-owner EXTEND **remains**.

### Req.203 / 204 / 110

| Req | B5v2 | Assessment |
|-----|------|------------|
| 203 | SKIP; allow_mdsr=False | Correct — registration ownership ≠ inactive classify; MDSR gate OK |
| 204 | PATCH_EXISTING | Plausible patient monitoring/view design owner |
| 110 | EXTEND_EXISTING | Plausible dashboard API / records owner |

## 6. MDSR Safety Gate

B4 CONSISTENT alone no longer patches all four:

- 203 blocked ✓  
- 204/110 allowed with design eligibility  
- 100 allowed because EXTEND still fired ✗ (residual)

## 7. MDDR Propagation

| Decision | Count | IDs |
|----------|------:|-----|
| PATCH_EXISTING | 1 | 204 |
| EXTEND_EXISTING | 2 | 100, 110 |
| NEW_DESIGN | 0 | — |
| SKIP | 1 | 203 |
| NEEDS_REVIEW | 0 | — |

DOCX changes: CR-append style on MDSR 204/100/110 and MDDR 204/100/110. No auto-inserted new design IDs.

## 8. NEW_DESIGN / NEEDS_REVIEW

None emitted for these four. Cross-ID better owners (e.g. B3 IMPACTED MDDR Req.17) still unused (same-ID only).

## 9. Document-level Semantic QA

| Check | Result |
|-------|--------|
| Wrong Req CR text | **Yes — Req.100** still receives inactive-patient CR under auth-code ownership |
| Req.203 pollution | **Cleared** vs B4v2 |
| Useful CR on 204/110 | Present (append) |
| Uncontrolled replication | 3 reqs (down from 4 MDSR); still multi-append |
| Structure/format | Appears preserved (append-only) |
| Title/purpose contradiction | Soft — CR appended under mismatched 100 purpose |

## 10. 4-way Comparison

See `BEFORE_AFTER_COMPARISON.md`.

## 11. New Bottleneck

1. **Over-permissive EXTEND_EXISTING** on weak CR↔design content tokens (`해당`, B3 prior bleed) → residual Req.100-class FP.  
2. Same-ID-only design candidate selection (no cross-ID owner search).  
3. Whole-CR append still coarse semantically.  
4. Upstream B4 still CONSISTENT on Req.100 (unchanged this step).

## 12. Overall Evaluation

| Component | Grade |
|-----------|-------|
| Retrieval / B3 / B4 | STABLE PASS |
| B5 audit-theme safety | PASS (path removed) |
| B5 useful propagation (204/110) | IMPROVED |
| B5 residual FP (100) | FAIL residual |
| MDSR gate | PARTIAL |
| Documents | PARTIAL / RISKY |
| **Overall** | **PARTIAL** |

## 13. Recommendation

Next (analysis-first, no immediate retune in this step): tighten EXTEND gates so weak single-token / prior-only overlap cannot open PATCH; optionally separate B4 FP follow-up. Validate only in a **new** dir afterward.

**Do not** hard-code Req.100/204/110 or Scenario keywords now.

---

## Verdict

**SCENARIO_001_B5V2_PARTIAL**
