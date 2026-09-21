# B5 Root Cause Analysis

**Status:** Analysis only — no B5/B4/B3 code changes, no rerun.  
**Frozen evidence (do not modify):**

| Artifact | Result | Policy |
|----------|--------|--------|
| `data/user_scenarios/scenario-001/` | PARTIAL | freeze |
| `data/user_scenarios/scenario-001-rerun-b3v2/` | PARTIAL | freeze |
| `data/user_scenarios/scenario-001-rerun-b4v2/` | PARTIAL | freeze |
| Trial 1 / Trial 2 | intact | freeze |

Primary evidence: `scenario-001-rerun-b4v2/output/trace/propagation_trace.json`  
Primary code: `src/document_ai/impact/propagation.py` (`_design_aligns`, `build_propagation_plan`, `apply_b4_b5_patches`)

---

## 1. Objective

Explain why B4v2 Scenario-001 produced:

- MDSR CR-append on Req.203 / 204 / 100 / 110
- MDDR **PATCHED = 1** and **only Req.100**
- Req.203 / 204 / 110 MDDR = `SKIPPED_WITH_REASON` (“design responsibility not evidenced”)

Separate:

1. Design retrieval vs alignment vs false propagation vs missing design  
2. B4 FP (Req.100 CONSISTENT) vs B5 wrong MDDR patch  
3. Domain-specific `_design_aligns` heuristics (Trial-2 lockout family)

Propose domain-independent B5v2 design — **implement later, not now**.

---

## 2. Current B5 Role

**Documented intent** (`propagation.py` docstring):

> Same Req ID alone is insufficient for propagation — design responsibility must align.

**Intended product role (target):**

| Stage | Question |
|-------|----------|
| B3 | Which requirements are impacted by the CR? |
| B4 | Can that requirement be consistently modify/extend-ed? |
| **B5** | Which design artifact should receive the change, and in what patch scope? |

**Effective role today:**

1. For each B4 MDSR decision with same-ID MDDR block: run `_design_aligns(mdsr, mddr, cr_text)`.
2. If B4 CONSISTENT + aligned → mark MDDR `PATCHED` (CR-append design text).
3. Independently, if B4 CONSISTENT + `allow_auto_patch` → **always** MDSR description CR-append (**no** `_design_aligns` gate).

So B5 today is a **same-ID + lockout/audit/UX theme co-occurrence gate**, plus unconditional MDSR append on B4 CONSISTENT — not a full responsibility-alignment / target-selection stage.

---

## 3. Current B5 Decision Logic

### 3.1 Inputs actually used

| Input | Used by MDDR align? | Used by MDSR patch? |
|-------|---------------------|---------------------|
| B4 `status` / `allow_auto_patch` | Yes (gate) | Yes |
| Same Req ID MDDR block from index | Yes (only candidate) | N/A |
| MDSR title+body text | Yes (`_design_aligns`) | Fields for base description |
| MDDR title+body text | Yes | Patch target body |
| CR text | Passed to `_design_aligns` but **unused inside function** | Yes (append sentence) |
| B3 `matched_concepts` / facets / spans | **No** | **No** |
| B4 `compatible_facets` / `conflicting_facets` / evidence | **No** (only status + `proposed_resolution_direction` string in evidence list) | **No** |
| Cross-ID MDDR IMPACTED from B3 (e.g. MDDR Req.17, Req.204) | **No** — never selected | **No** |

### 3.2 `_design_aligns` (core)

```text
require mdsr.req_id == mddr.req_id
else False

theme pairs (any src in MDSR text AND any dst in MDDR text):
  (감사,) → (감사, audit)
  (안내, 에러, 오류) → (안내, 에러, 오류, 메시지)
  (과다, 차단, 임계, 잠금, 제한) → (잠금, 임계, 제한, 차단, 실패)

else if "로그인" in MDSR and "로그인" in MDDR → True
else False ("Same ID present but design responsibility link not evidenced")
```

`cr_text` parameter is **dead** — alignment ignores CR semantics entirely.

### 3.3 `build_propagation_plan` outcomes

| Condition | Outcome |
|-----------|---------|
| No MDDR block | NEEDS_REVIEW |
| B4 CONFLICT | SKIPPED_WITH_REASON |
| B4 NEEDS_REVIEW / !allow_auto_patch | NEEDS_REVIEW |
| B4 CONSISTENT + !aligned | SKIPPED_WITH_REASON ← Scenario-001 203/204/110 |
| B4 CONSISTENT + aligned + design delta | PATCHED ← Scenario-001 Req.100 |
| aligned but no delta | SKIPPED_WITH_REASON |

### 3.4 `apply_b4_b5_patches` split

- **MDSR:** `proposed_mdsr_description` for every CONSISTENT+allow — **bypasses alignment**.
- **MDDR:** only traces with `outcome==PATCHED`.

This split explains “MDSR patched 4 / MDDR patched 1”.

---

## 4. Scenario-001 B4v2 Failure Path

Pipeline state entering B5:

- Retrieval stable; B3 IMPACTED includes MDSR 203/204/100/110 and MDDR 17/204 (among others).
- B4v2: all four MDSR → CONSISTENT + allow_auto_patch.

B5 path:

```text
for each CONSISTENT MDSR:
  pair only MDDR with same Req ID
  aligned = _design_aligns(MDSR, MDDR, CR)   # CR ignored
  if aligned: MDDR PATCHED (CR append)
  else: MDDR SKIP ("design responsibility not evidenced")
  always: MDSR CR-append if B4 allow_auto_patch
```

Result recorded in frozen `propagation_trace.json`:

| Req | MDDR outcome | Align flag | Align evidence |
|-----|--------------|------------|----------------|
| 203 | SKIP | false | Same ID; no theme pair |
| 204 | SKIP | false | Same ID; no theme pair |
| 100 | **PATCHED** | true | `src=('감사',)` dst hits in MDDR |
| 110 | SKIP | false | Same ID; no theme pair |

---

## 5. Candidate-level Analysis

| Requirement | B3 | B4 | B5 result | Design candidate | Direct code condition | Reason |
|-------------|----|----|-----------|------------------|----------------------|--------|
| Req.204 | IMPACTED (MDSR); MDDR 204 also IMPACTED | CONSISTENT | MDDR SKIP; MDSR patched | MDDR Req.204 (same ID) — **exists**, patient progress/report UI | CONSISTENT ∧ `not _design_aligns` | No audit/UX/lockout/login co-occurrence between MDSR↔MDDR; clinical design present but invisible to theme gate |
| Req.110 | IMPACTED MDSR | CONSISTENT | MDDR SKIP; MDSR patched | MDDR Req.110 — **exists**, dashboard data API | same | MDSR criteria may mention 감사, but MDDR 110 body lacks matching dst theme → align false; CR-relevant API design still present |
| Req.203 | IMPACTED MDSR | CONSISTENT | MDDR SKIP; MDSR patched | MDDR Req.203 — **exists**, registration `/patients/create` | same | Design exists but ownership for *inactive-patient highlight* is weak; skip avoids MDDR pollution here (accident of theme miss, not responsibility reasoning) |
| Req.100 | IMPACTED MDSR | CONSISTENT (B4 FP) | **MDDR PATCHED**; MDSR patched | MDDR Req.100 — auth-code / patient_code | CONSISTENT ∧ `_design_aligns` True via **감사** | Incidental audit sentence in MDSR+MDDR triggers lockout-era audit pair; CR inactive-patient meaning wrongly appended |

---

## 6. Why Req.100 Was Patched

**A. Why only Req.100 PATCHED?**  
Only Req.100 satisfied `_design_aligns == True` among the four CONSISTENT MDSR IDs.

**B. Why linked?**  
MDSR Req.100 body/criteria contain `감사` (code lookup/use history must be audited).  
MDDR Req.100 also contains `감사 기록`.  
First theme pair fires: `src=('감사',)` → dst hits — **independent of CR**.

**C. Did `감사` outrank true design responsibility?**  
**Yes.** True CR responsibility ≈ classify inactive patients from task records + dashboard highlight.  
Req.100 design responsibility ≈ one-time registration/auth code lifecycle.  
Thematic/security boilerplate (`감사`) outranked behavioral ownership.

**D/E.** See §§7–8 for 203/204/110 and classification.

---

## 7. Why Req.203 / 204 / 110 Were Skipped

Direct condition (all three):

```text
decision.status == CONSISTENT
and allow_auto_patch
and not aligned
→ SKIPPED_WITH_REASON
  "MDSR CONSISTENT but MDDR design responsibility not evidenced"
```

`align_reason`: `"Same ID present but design responsibility link not evidenced"`.

Not because MDDR blocks are missing — traces show real `before_snippet` design text for each.

Not because CR was analyzed and rejected — **CR is unused** in `_design_aligns`.

Skipped because none of the Trial-2 theme pairs (감사/안내·에러/잠금·임계/로그인) co-occur in a way the gate accepts for those MDSR↔MDDR pairs (for 110: MDSR may have 감사 but MDDR 110 does not → pair fails).

---

## 8. Retrieval vs Alignment vs Missing-Design Classification

| Case | Definition | Scenario-001 mapping |
|------|------------|----------------------|
| **A** Design Retrieval | Related MDDR not available as B5 candidate | B5 never retrieves: **only same-ID**. B3 IMPACTED MDDR Req.17 / 204 are **ignored** as alternate owners → latent **A** for cross-ID selection |
| **B** Design Alignment | Related same-ID MDDR exists; align rejects | **Req.204**, **Req.110** (and partially 203): designs exist with clinically related content; theme gate rejects |
| **C** False Propagation | Wrong MDDR selected/patched via theme | **Req.100** PATCHED |
| **D** Missing / NEW DESIGN | No adequate design owner in corpus | Possible for *inactive-patient highlight* as a first-class UI/state design if 204/110 judged insufficient after true alignment — not proven missing; **203**’s registration design is wrong owner (would be C if patched). Prefer NEW_DESIGN/NEEDS_REVIEW over forcing 100 |

**Per requirement:**

| Req | Primary class | Notes |
|-----|---------------|-------|
| 204 | **B** (+ latent **A** if better non-ID design preferred) | Same-ID MDDR related; align fail |
| 110 | **B** | Dashboard API design present; align fail |
| 203 | **B** (skip) / potential **D** for true CR UI | Registration design exists but weak CR fit |
| 100 | **C** | Wrong owner patched via 감사 |

---

## 9. Domain-specific Logic

Confirmed lockout / auth / security-shaped B5 logic:

| Location | Heuristic |
|----------|-----------|
| `_design_aligns` pair 1 | 감사 / audit |
| pair 2 | 안내 / 에러 / 오류 / 메시지 (UX) |
| pair 3 | 과다 / 차단 / 임계 / 잠금 / 제한 / 실패 (policy/lockout) |
| fallback | both sides contain `로그인` |
| Tests | `test_b4_b5_consistency_propagation.py` — Trial-2 lockout CR; Req.6 skip, 103/105 patch path |

This is **Trial-2 lockout multi-req shaped**, not domain-independent responsibility alignment.

Also:

- Same-ID hard link (traceability assumption) without facet evidence.
- CR theme not used (ironically neither domain-independent CR facets nor lockout CR terms drive align — only MDSR↔MDDR keyword bags).
- MDSR patch path has **zero** design-responsibility check.

**Out of scope / must not do in implementation:** Req.204/110/203/100 hard-codes; inactive/dashboard/3-day special cases.

---

## 10. B3/B4 Evidence Handoff

| Evidence | Reaches B5? |
|----------|-------------|
| B3 matched_concepts | No |
| B3 behavioral_overlap | No |
| B3 cr_spans / candidate_spans | No |
| B3 change_type | No |
| B4 compatible_facets | No |
| B4 conflicting_facets | No |
| B4 missing_information | No |
| B4 reason / structured evidence | Only free-text `proposed_resolution_direction` sometimes copied into MDDR PATCHED evidence list |
| B4 status / allow_auto_patch | **Yes** |

**Conclusion:** B5 re-decides with its own keyword/theme matcher. Upstream evidence pipeline stops at B4 for consistency; B5 does not consume it for ownership.

---

## 11. B3/B4/B5 Responsibility Separation

| Stage | Should do | Currently does | Overlap / gap |
|-------|-----------|----------------|---------------|
| B3 | Impact candidacy | Evidence IMPACTED | OK |
| B4 | Consistency of modify/extend on Req | Facet gate (B4v2); still over-allows Req.100 | Problem 1 (separate) |
| B5 | Design ownership + propagation scope + patch target | Same-ID + audit/UX/lockout theme co-occurrence; MDSR append uncapped by align | **Gap:** no facet handoff; **bleed:** theme ownership; **split:** MDSR vs MDDR gates differ |

B5 should defend against upstream FP for **design** propagation (Problem 2) even when B4 CONSISTENT — thematic similarity ≠ design ownership.

---

## 12. Root Cause

**Primary root cause**

B5 MDDR propagation uses `_design_aligns`: same-Req-ID plus **Trial-2 security/UX/lockout keyword co-occurrence**. It does **not** evaluate CR↔design responsibility using B3/B4 facets. Therefore:

- Clinically relevant designs (204/110) → false SKIP (theme miss).  
- Auth-code design with incidental `감사` (100) → false PATCH (theme hit).  
- CR text is irrelevant to align.

**Contributing causes**

1. No cross-ID design candidate selection (B3 MDDR IMPACTED unused).  
2. MDSR auto-patch ignores alignment → CR pollution on all CONSISTENT IDs including FP.  
3. Patch strategy = whole-CR append (not field/responsibility-scoped).  
4. No NEW_DESIGN / NEEDS_REVIEW when no safe owner.  
5. Upstream B4 FP (Req.100 CONSISTENT) enlarges blast radius — but B5 still should not have aligned on 감사 alone.

**Not the root cause**

- Missing MDDR blocks for 203/204/110 (they exist).  
- Retrieval Top-k drift.  
- B3 instability.

---

## 13. Domain-independent B5 Design Proposal

### 13.1 Questions B5 must answer

1. Which design block(s) own this consistent requirement change?  
2. Is that ownership evidenced (not merely same ID / shared boilerplate)?  
3. Patch existing, extend, propose new design, skip, or review?

### 13.2 Judgment dimensions (no auth lexicon as core)

- Actor / action / object compatibility (reuse B3/B4 facet priors)  
- Responsibility / component / interface / data-flow alignment  
- Direct traceability (same ID as **prior**, not sufficient condition)  
- Behavioral alignment with CR (use CR spans — currently unused)  
- Contradiction / wrong-owner risk (thematic neighbor defense)

Distinguish explicitly:

| Signal | Enough for PATCH_EXISTING? |
|--------|----------------------------|
| Thematic similarity | **No** |
| Keyword/theme bag overlap (감사, 로그인, …) | **No** (legacy only) |
| Responsibility alignment evidence | **Required** |
| Direct traceability (ID) | Necessary-but-not-sufficient or soft prior |
| Behavioral alignment with CR | Required or strong prior |

### 13.3 Proposed output schema

```json
{
  "requirement": "Req. …",
  "design_candidate": "Req. … (MDDR) | null",
  "propagation_decision": "PATCH_EXISTING | EXTEND_EXISTING | NEW_DESIGN_CANDIDATE | SKIP | NEEDS_REVIEW",
  "evidence": {
    "requirement_spans": [],
    "design_spans": [],
    "matched_responsibilities": [],
    "matched_facets": [],
    "conflicts": [],
    "missing_information": []
  },
  "reason": "...",
  "confidence": 0.0
}
```

Rules:

- Confidence never sole PATCH trigger.  
- Same ID alone never PATCH.  
- Boilerplate-only overlap (e.g. shared 감사 clause without CR-aligned object/action) → SKIP or NEEDS_REVIEW.  
- Consume B3/B4 evidence as priors; re-validate design-side spans.

### 13.4 MDSR vs MDDR

Recommend **shared ownership gate** (or stricter): do not MDSR-append when design ownership is SKIP/conflict/FP-neighbor — or mark MDSR patch NEEDS_REVIEW when MDDR cannot align. (Design choice for B5v2 scope — document in implementation plan.)

---

## 14. NEW_DESIGN / NEEDS_REVIEW Proposal Design

When no design candidate has responsibility alignment:

- Emit `NEW_DESIGN_CANDIDATE` or `NEEDS_REVIEW` proposal (structured; **no** auto-insert into DOCX).  
- Include: source CR provenance, related MDSR id, rejected same-ID candidates + reasons, human decision required.  
- Parallel to B3 zero-IMPACTED NEW_REQUIREMENT safety — do not invent Req IDs silently.

Scenario-001 lean: if 204/110 fail true alignment after B5v2, prefer proposal over patching 100.

---

## 15. Synthetic Test Matrix (design only — no tests this step)

| Case | Intent | Expected |
|------|--------|----------|
| **A** | Req↔Design responsibility clearly matches | PATCH_EXISTING |
| **B** | Related design; scope extension | EXTEND_EXISTING |
| **C** | Theme similar; responsibility differs (Req.100-class) | SKIP or NEEDS_REVIEW |
| **D** | No adequate design block | NEW_DESIGN_CANDIDATE |
| **E** | Insufficient information | NEEDS_REVIEW |
| **F** | Traceability ID match but behavioral conflict | SKIP / NEEDS_REVIEW |
| **G** | Non-auth domain (inventory/reservation/reporting) | Align without lockout lexicon |

**Regression:** Trial-2 Req.6 must not silent-propagate; 103/105 may still PATCH via **general** audit/policy responsibility evidence — not via hard-coded theme bags as sole core.

---

## 16. Risks

| Risk | Detail |
|------|--------|
| Over-eager PATCH after removing theme bags | Patch wrong clinical neighbor; mitigate with responsibility+CR facets |
| Breaking Trial-2 | Need equivalent evidence rules for audit/policy extension |
| Same-ID fetish | Missing better cross-ID design; need candidate search policy |
| Ignoring MDSR/MDDR gate split | MDSR still polluted if only MDDR align fixed |
| Confidence misuse | Ban score-only PATCH |
| Scope creep | Do not retune B4/B3 in same change; separate Problem 1 follow-up |
| Scenario hard-codes | Forbidden |

---

## 17. Recommended Implementation Scope

**In scope for future B5v2:**

1. Replace `_design_aligns` theme bags with facet/responsibility alignment using CR + MDSR + MDDR (+ B3/B4 priors).  
2. Structured propagation decision + evidence in traces.  
3. False-propagation defense (Case C).  
4. NEW_DESIGN_CANDIDATE / NEEDS_REVIEW when no safe owner.  
5. Revisit MDSR patch gating vs MDDR ownership.  
6. Synthetic tests A–G + Trial-2 regression.  
7. Validate only in **new** scenario dir (never overwrite B4v2 freeze).

**Out of scope:**

- B4 / B3 code changes (Problem 1 tracked separately)  
- Dense embedding / XXCS / form-fill  
- Req-ID or Scenario-001 keyword special cases  
- Editing frozen scenario/trial artifacts  

### Problem split (explicit)

| ID | Problem | Owner of fix (later) |
|----|---------|----------------------|
| **Problem 1** | B4 marks Req.100 CONSISTENT | B4 follow-up (not this step) |
| **Problem 2** | B5 patches Req.100 MDDR via 감사 theme | **B5v2** (this analysis) |

B5 **should** defend design propagation against upstream FP: even if B4 CONSISTENT, PATCH requires design-responsibility evidence tied to CR — not boilerplate theme overlap.

---

## Verdict checklist

| READY criterion | Met? |
|-----------------|------|
| Req.100 wrong-patch path explained | Yes — 감사 pair |
| 203/204/110 skip path explained | Yes — theme miss / !aligned |
| Retrieval vs Alignment vs Missing separated | Yes — §8 |
| Domain-specific dependency confirmed | Yes — §9 |
| B3/B4/B5 separation clear | Yes — §11 |
| Domain-independent design exists | Yes — §§13–15 |
| Implementable without scenario hard-codes | Yes |

**Final judgment: READY_TO_IMPLEMENT_B5V2**
