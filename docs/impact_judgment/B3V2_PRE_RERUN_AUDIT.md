# B3v2 Pre-Rerun Implementation Audit

> Audit only — **no code changes**, **no Scenario-001 rerun**.  
> Date: 2026-07-23  
> Auditor target: B3 evidence-based judgment + zero-IMPACTED NEW_REQUIREMENT fallback

## 1. Audit Scope

| Artifact | Role |
|----------|------|
| `docs/impact_judgment/B3_ROOT_CAUSE_ANALYSIS.md` | Prior root-cause (v1) |
| `src/document_ai/impact/impact_judgment.py` | B3v2 judgment |
| `src/document_ai/impact/new_requirement_proposal.py` | Zero-IMPACTED fallback |
| `src/document_ai/scenario/runner.py` | Wiring (proposal write-only) |
| `tests/test_b3_evidence_based.py` | Cases A–E |
| `tests/test_hybrid_and_b3.py` | Lockout / false-ID / access demotion regression |
| Full `pytest` | Suite health |
| Scenario-001 / Trial 1 / Trial 2 freezes | Integrity |

Out of scope this audit: B4/B5 redesign, dense embedding, Scenario-001 execution.

## 2. Generalization Findings

### A. Scenario-specific overfitting — **PASS (no hard-codes found)**

| Check | Result |
|-------|--------|
| `Req. 204` hard-code in B3/proposal/runner | **Absent** |
| `Req. 110` hard-code | **Absent** |
| Dedicated `비활성` production rule | **Absent** (only appears in **test** false-friend fixture) |
| Dashboard-specific special case | **Absent** as a branch; `대시보드` is only an OUTPUT facet marker |
| `3일`-specific rule | **Absent** |
| Scenario-001 gold injection | **Absent** |

### B. Remaining domain / lexicon structure — **non-blocking findings**

| Mechanism | Assessment |
|-----------|------------|
| **matched_concepts** | Unigram/bigram intersection after stopwords — **domain-agnostic**, OK |
| **relevance** | Jaccard + retrieval lex/sem blend — **domain-agnostic**, OK |
| **behavioral_overlap** | Closed marker lists for actor/action/output/condition/object — **generic software/req language**, but lexicon is finite and **Korean product-doc skewed** (e.g. `의료진`, `환자`, `대시보드`) |
| **access-control title demotion** | Title contains `권한` / `접근 통제` / `API 접근` → demote IMPACTED if CR does not target access — **structural**, not Scenario-001-specific; still **security-domain flavored** residual |

**Verdict on overfitting to Scenario-001 answers:** No evidence of answer injection.  
**Verdict on residual bias:** Mild healthcare/UI marker bias and access-control demotion remain; not treated as fatal Scenario-001 overfit, but listed as residual risk.

## 3. Remaining Domain-specific Logic

1. **Facet marker lists** (`ACTOR_MARKERS` includes `의료진`/`환자`; `OUTPUT_MARKERS` includes `대시보드`) — help clinical CRs but are not exclusive gates.
2. **Access-control primary demotion** — security-title heuristic retained to protect lockout CR vs Req.101-style FP.
3. **B4 `consistency_gate.py`** still lockout-themed (out of B3v2 scope; unchanged as required) — will matter after IMPACTED resumes on non-auth CRs.

No lockout-only IMPACTED gates remain in B3v2 (`strong_lock` / `LOCK_TERMS` removed).

## 4. Impact Judgment Decision Flow

```
inputs: cr_text, block, lexical_score, semantic_score

tokens / bigrams → matched_concepts
relevance = 0.45*J_uni + 0.25*J_bi + 0.20*sem_norm + 0.10*lex_norm
facets = shared actor/action/output/condition/object markers
false_friend = weak single-token overlap without shared actor/object
change_type = f(relevance, facets, novel CR tokens, false_friend)
confidence = f(relevance, facet_n)   # informational only

IF false_friend AND relevance < 0.15:
    → NOT_IMPACTED / NOT_RELATED
ELIF change_type ∈ {MODIFY_EXISTING, EXTEND_EXISTING}
     AND facet_n ≥ 2 AND relevance ≥ 0.10
     AND (lex≥0.06 OR sem≥0.05 OR J_uni≥0.08):
    → IMPACTED
ELIF change_type == NEW_REQUIREMENT_CANDIDATE AND facet_n≥1 AND relevance≥0.07:
    → UNCERTAIN (change_type kept NEW_REQUIREMENT_CANDIDATE)
ELIF change_type == EXTEND_EXISTING AND relevance≥0.07:
    → UNCERTAIN   # extension without enough facets for auto IMPACTED
ELIF change_type == NOT_RELATED OR relevance < 0.045:
    → NOT_IMPACTED / NOT_RELATED
ELSE:
    → UNCERTAIN

IF IMPACTED AND access_primary_title AND CR not access-targeted:
    → demote to NOT_IMPACTED / NOT_RELATED
```

### Key safety properties

| Property | Status |
|----------|--------|
| **confidence alone never selects IMPACTED** | **PASS** — confidence is computed after/alongside gates; never in `if confidence…` |
| Semantic/lexical evidence required for IMPACTED | **PASS** — needs change_type + facet_n + relevance (+ score/jaccard floor) |
| Behavioral overlap role | **PASS** — `facet_n` required (≥2) for IMPACTED; also feeds change_type via `has_core` |
| MODIFY vs EXTEND | novel CR tokens present → EXTEND; few novel + high relevance → MODIFY |
| NEW_REQUIREMENT_CANDIDATE vs UNCERTAIN | NEW_REQ change_type + facets → judgment UNCERTAIN; weak residual → UNCERTAIN change_type |

## 5. Zero-IMPACTED Safety

| Case | Intended | Actual code | Status |
|------|----------|-------------|--------|
| **1** No related candidates | Do **not** emit NEW_REQUIREMENT | `ranked==[]` → no emit (**OK**). But if retrieval returns **any** hits that are all `NOT_RELATED`, `should_emit` is still **True** because `return bool(uncertainish or top)` and `top` is non-empty | **FAIL / BLOCKING** |
| **2** Related but weak evidence | UNCERTAIN / review | B3 can yield UNCERTAIN; fallback may also emit proposal | OK-ish |
| **3** Related but out of scope | NEW_REQUIREMENT_CANDIDATE | Supported via change_type + fallback | OK |
| **4** Clear in-scope modify | IMPACTED MODIFY/EXTEND | Supported when facets≥2 + relevance | OK (unit Case A) |

**Probe (runtime):**  
`all NOT_RELATED + nonempty ranked` → `should_emit_zero_impacted_fallback == True` and proposal **is emitted**.

This violates the audit rule: *NEW_REQUIREMENT must not fire merely because IMPACTED==0*.

### Proposed fix (do **not** implement in this audit step)

```python
def should_emit_zero_impacted_fallback(...):
    if any(IMPACTED): return False
    if not ranked: return False
    relatedish = [
        d for d in decisions
        if d.judgment == "UNCERTAIN"
        or d.change_type in {"EXTEND_EXISTING", "NEW_REQUIREMENT_CANDIDATE", "MODIFY_EXISTING", "UNCERTAIN"}
    ]
    # Require at least one non-NOT_RELATED signal among top-N — never `or top` alone
    return bool(relatedish)
```

Optionally also require `len(cr_text) > N` (already indirectly via runner use).

## 6. NEW_REQUIREMENT Safety

| Check | Status |
|-------|--------|
| No auto-assigned permanent Req ID | **PASS** — title from CR text; notes forbid permanent number |
| No DOCX insertion of new Req | **PASS** — proposal files only; `apply_b4_b5_patches` unaware of proposal |
| Human decision required listed | **PASS** |
| Source CR provenance | **PASS** (`source_cr`, intent) |
| Related candidates retained | **PASS** |
| MDSR/MDDR impact as hints only | **PASS** |
| Proposal not treated as approved req downstream | **PASS** — B4 still keys only on B3 `IMPACTED`; proposal not in consistency/propagation inputs |

Residual: over-emission (Section 5) can create **noisy** proposals, not silent approved patches.

## 7. Regression Results (expectation table)

| Scenario type | Pre-B3v2 (theme lockout) | B3v2 expected | Covered by tests |
|---------------|--------------------------|---------------|------------------|
| Lockout policy block | IMPACTED | IMPACTED MODIFY/EXTEND | `test_lockout_still_impacted_*`, `test_b3_lock_block_impacted` |
| Audit-primary login events | IMPACTED / scope | IMPACTED or UNCERTAIN with evidence | `test_b3_audit_primary_impacted` (allows both) |
| Access-control + incidental auth (Req.101-style) | NOT_IMPACTED | NOT_IMPACTED via demotion | `test_b3_generic_audit_not_impacted` |
| UX/supporting (password/session) | often theme-miss | IMPACTED if facets align | Case A |
| Lexical false friend (`비활성` app vs patient) | NOT / weak | NOT_RELATED | Case D |
| Unrelated / vague CR | NOT / UNCERTAIN | NOT or UNCERTAIN | Case E |
| ID alone | not IMPACTED | not IMPACTED | `test_id_alone_*` |

No observed test regressions in targeted suites; full suite green (below).

## 8. Full Pytest Result

```
363 passed in 158.54s
failed: 0
skipped: 0
flaky: not observed (single clean run)
```

Scenario-001 **was not executed**.

## 9. Freeze Integrity

| Freeze | Result |
|--------|--------|
| `data/user_scenarios/scenario-001/` via `FREEZE.json` canonical hashes | **ok** (`overall_result=PARTIAL`) |
| Trial 2 `execution_report.json` canonical hashes | **ok** (`PASS`) |
| Trial 1 | `trial_1_freeze: true`, `overall_result: FAILED` — report present; no hash drift check of same schema (different report shape); **not modified this session** |

## 10. Risks Before Rerun

1. **BLOCKING:** NEW_REQUIREMENT over-trigger when Top-k is all `NOT_RELATED`.
2. Facet lexicons may under-serve non-Korean / non-clinical domains (false UNCERTAIN).
3. Access-control demotion may over-suppress legitimate access-policy CRs that omit title keywords.
4. After IMPACTED resumes on clinical CRs, **unchanged B4** may still be lockout-shaped → separate post-rerun risk (not B3v2 commit blocker for judgment module alone, but affects end-to-end Scenario-001-rerun expectations).
5. Threshold sensitivity (`relevance`/`facet_n`) not calibrated on frozen Scenario-001 (by design).

## 11. Final Decision

### BLOCKED_BEFORE_COMMIT_B3V2

**Reason:** Zero-IMPACTED fallback is **not yet safe** under Case 1 / “IMPACTED==0 ⇒ unconditional proposal when ranked≠∅”.  
Full pytest PASS and freeze integrity are OK; Scenario-specific hard-codes are absent — but READY conditions require safe NEW_REQUIREMENT fallback.

### Unblock checklist (next implementation step — not done now)

1. Change `should_emit_zero_impacted_fallback` to require **relatedish** decisions (not bare `or top`).
2. Add unit test: all `NOT_IMPACTED/NOT_RELATED` + nonempty ranked → **no** proposal.
3. Re-run targeted + full pytest.
4. Re-audit → then consider `READY_TO_COMMIT_B3V2`.
5. Only after commit approval: Scenario-001 rerun in a **new directory** (never overwrite freeze).

---

## 12. Blocking Finding Resolution (post-audit fix)

**Original Finding:**
- all NOT_RELATED candidates could trigger fallback via `return bool(uncertainish or top)`

**Resolution:**
- removed unconditional top-ranked fallback (`or top`)
- related evidence is now required: among Top-N decisions, at least one must be non-`NOT_RELATED` and evidence-related (`EXTEND_EXISTING` / `NEW_REQUIREMENT_CANDIDATE` / `MODIFY_EXISTING`, or `UNCERTAIN` with matched_concepts/behavioral_overlap and minimum relevance, or concepts+facets+relevance)

**Regression Test:**
- `test_zero_impacted_fallback_does_not_emit_when_all_candidates_not_related`
- positive path retained: `test_case_c_new_requirement_candidate_and_fallback`

**Result:**
- PASS — full suite `364 passed` (local); Case1 probe: all-NOT_RELATED + ranked → no emit

**Updated decision (after fix):** see section 13.

## 13. Post-fix Decision

After resolving the single blocking finding (no Scenario-001 rerun; freezes untouched):

**READY_TO_COMMIT_AND_RERUN_SCENARIO_001**

Conditions met:
- all-NOT_RELATED fallback bug fixed
- positive NEW_REQUIREMENT fallback retained
- full pytest PASS (`364 passed`, 0 failed, 0 skipped)
- no scenario-specific hard-code introduced
- Scenario-001 / Trial 2 freeze hashes intact; Trial 1 freeze flag unchanged

Scenario-001 execution still requires separate approval and a **new directory** (never overwrite freeze).

**CODE_MODIFIED_FOR_BLOCKING_FIX_ONLY = YES** (fallback + tests + audit appendix)  
**SCENARIO_001_RERUN = NO**
