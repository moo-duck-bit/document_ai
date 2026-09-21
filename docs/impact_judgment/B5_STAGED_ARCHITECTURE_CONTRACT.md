# B5 Staged Architecture — Implementation Contract

**Status:** Architecture contract only — **no code changes, no rerun, freezes untouched.**  
**Prior judgment:** `ARCHITECTURE_CHANGE_REQUIRED_BEFORE_B5V3`  
**Evidence base:** Scenario-001 B5v2 rerun PARTIAL + `propagation.py` / `runner.py` as of B5v2.

This document **locks** the staged architecture that must be implemented before (and as) B5v3. Incremental threshold/keyword hotfixes are **out of contract**.

---

## 1. Problem Statement

B5v2 improved away lockout/`감사` theme ownership, but residual PARTIAL shows **structural** defects:

1. **Candidate discovery is same-ID exclusive** — `build_propagation_plan` pairs each CONSISTENT MDSR `Req.X` only with MDDR `Req.X`.
2. **B3 IMPACTED MDDR (e.g. Req.17) never enters the B5 pool** — cross-ID designs cannot be aligned.
3. **Discovery + alignment + decision are fused** inside `assess_design_propagation` / `build_propagation_plan`.
4. **EXTEND_EXISTING opens on weak CR↔design touch + strong same-ID MDSR↔MDDR echo** (Req.100 residual FP).
5. **Prior bleed** — B3/B4 facets reappear as B5 `b3_prior_*` / compatible lists; evidence amplification.
6. **Whole-CR append** — `proposed_*_description` dumps the entire CR into every allowed owner → multi-responsibility contamination.

These cannot be fixed by thresholds alone; they require a **staged contract**.

---

## 2. Evidence from B5v2

| Observation | Implication |
|-------------|-------------|
| Req.100 EXTEND with `cr_mddr=['해당']`, `action_cr_mddr=['기록']`, high `obj_j_mdsr_mddr` | Same-ID echo + weak/generic/false-friend signals open EXTEND |
| Req.203 SKIP + MDSR gate blocked | Discriminative absence can work when `cr_mddr=[]` and no action |
| Req.204 PATCH / Req.110 EXTEND useful | Discriminative action–responsibility binding exists when discovery hits the right owner |
| MDDR Req.17 IMPACTED in B3, unused in B5 | Discovery gap, not alignment rejection |
| MDSR 203/204/100/110 previously all appended under B4v2; B5v2 still appends whole CR on 204/100/110 | Text generation coupled to ownership without ACU scoping |

---

## 3. Current Code Responsibilities

Legend: **A** Candidate Discovery · **B** Alignment · **C** Propagation Decision · **D** Patch Planning · **E** Text Generation · **F** DOCX Application · **G** Trace/Report orchestration

| Function / entry | File | A | B | C | D | E | F | G | Notes |
|------------------|------|---|---|---|---|---|---|---|-------|
| `assess_design_propagation` | `propagation.py` | ◐ | ● | ● | | | | | **Mixed:** assumes single `mddr` already chosen; scores align + returns PATCH/EXTEND/SKIP/NEW/REVIEW |
| `build_propagation_plan` | `propagation.py` | ● | ◐ | ● | ◐ | ◐ | | ◐ | **Mixed:** same-ID discovery; calls assess; precomputes design text snippets; builds `PropagationTrace` |
| `apply_b4_b5_patches` | `propagation.py` | | | | ● | ◐ | ● | | MDSR gate via `allow_mdsr_patch`; calls text helpers; writes DOCX |
| `proposed_mdsr_description` | `propagation.py` | | | | | ● | | | Whole-CR append if B4 CONSISTENT |
| `proposed_mddr_design_description` | `propagation.py` | | | | | ● | | | Whole-CR append |
| `_cr_append_sentence` | `propagation.py` | | | | | ● | | | Opaque full-CR snippet |
| `_extract_b3_prior` / `_extract_b4_prior` | `propagation.py` | | ◐ | | | | | | Feeds priors into assess (bleed surface) |
| `legacy_theme_design_aligns` | `propagation.py` | | ◐ | | | | | | Isolated; not core |
| `run_user_scenario` | `runner.py` | | | | | | | ● | Orchestrates retrieval→B3→B4→`build_propagation_plan`→`apply_b4_b5_patches`; writes traces/reviews |
| `_write_review_docs` | `runner.py` | | | | | | | ● | Human-readable summaries |

**Role mixing (must be broken):**

- Discovery hidden inside plan loop (`by_key.get((req_id,"MDDR"))`).
- Alignment function also **decides** propagation enum.
- Plan both **decides** and **drafts** after_snippet text.
- Apply both **plans eligibility** and **generates+writes** text.
- No Atomic Change Unit; no Patch Plan artifact distinct from generated prose.

---

## 4. Target End-to-End Architecture

```text
CR Intake
    ↓
Atomic Change Decomposition          [ACU]
    ↓
B3 Requirement Impact Discovery
    ↓
B4 Requirement Consistency
    ↓
B5a Design Candidate Discovery
    ↓
B5b Responsibility Alignment
    ↓
B5c Propagation Decision
    ↓
B6 Patch Planning
    ↓
Generation (sentence / field text)
    ↓
DOCX Patch Application
    ↓
Semantic Validation / Review artifacts
```

Upstream retrieval (hybrid Top-k) remains as today before B3.  
NEW_REQUIREMENT (zero IMPACTED) remains B3-adjacent; NEW_DESIGN is B5c/B6.

### Per-stage card

#### CR Intake
| | |
|--|--|
| **Purpose** | Load immutable CR + reference docs; hash inputs |
| **Input** | scenario paths |
| **Output** | `cr_text`, docx paths, input hashes |
| **Responsibility** | I/O only |
| **Forbidden** | Judgment, patch |
| **Trace** | `execution_report` input hashes |
| **Failure** | Missing inputs → abort |

#### Atomic Change Decomposition
| | |
|--|--|
| **Purpose** | Split CR into Atomic Change Units (ACUs) |
| **Input** | `cr_text` |
| **Output** | `atomic_change_units[]` |
| **Responsibility** | Span-level responsibility units |
| **Forbidden** | Owner selection, PATCH, DOCX write, Scenario keyword rules |
| **Trace** | `trace/atomic_change_units.json` |
| **Failure** | Cannot decompose safely → single ACU = whole CR marked `decomposition=FALLBACK` + later NEEDS_REVIEW bias |

#### B3 Requirement Impact Discovery
| | |
|--|--|
| **Purpose** | Which Req/Design blocks are IMPACTED / UNCERTAIN / NOT |
| **Input** | CR, ranked retrieval, index blocks |
| **Output** | impact decisions (MDSR+MDDR) |
| **Responsibility** | Candidacy for impact — **not** design ownership final |
| **Forbidden** | DOCX patch, consistency CONSISTENT as ownership |
| **Trace** | `trace/impact_judgments.json` |
| **Failure** | Zero IMPACTED → NEW_REQUIREMENT path |

#### B4 Requirement Consistency
| | |
|--|--|
| **Purpose** | Can CR be modify/extend **within** an IMPACTED requirement’s meaning? |
| **Input** | CR, IMPACTED MDSR, B3 evidence |
| **Output** | CONSISTENT / CONFLICT / NEEDS_REVIEW |
| **Responsibility** | Requirement-level consistency only |
| **Forbidden** | Choosing MDDR owner; appending CR text |
| **Trace** | `trace/consistency_decisions.json` |
| **Failure** | CONFLICT/NEEDS_REVIEW → no auto design patch for that Req |

#### B5a Design Candidate Discovery
| | |
|--|--|
| **Purpose** | Collect **possible** design candidates for each (Req, ACU) |
| **Input** | CONSISTENT (or reviewable) Req, ACUs, B3 MDDR decisions, index, traceability |
| **Output** | `design_candidates[]` with sources |
| **Responsibility** | Pool building + dedupe + cap |
| **Forbidden** | PATCH/EXTEND/SKIP decisions; text generation |
| **Trace** | `trace/design_candidates.json` |
| **Failure** | Empty pool → B5c NEW_DESIGN / NEEDS_REVIEW |

#### B5b Responsibility Alignment
| | |
|--|--|
| **Purpose** | Is candidate a **real responsibility owner** for this ACU? |
| **Input** | ACU, one design candidate, evidence provenance |
| **Output** | ALIGNED / PARTIAL_ALIGNMENT / NOT_ALIGNED / UNCERTAIN + evidence classes |
| **Responsibility** | Discriminative vs generic evidence; no decision enum PATCH |
| **Forbidden** | Opening PATCH via generic-only/prior-only; DOCX write |
| **Trace** | `trace/responsibility_alignment.json` |
| **Failure** | All NOT_ALIGNED → NEW_DESIGN path; all UNCERTAIN → NEEDS_REVIEW |

#### B5c Propagation Decision
| | |
|--|--|
| **Purpose** | Choose propagation outcome given alignments |
| **Input** | ACU, B5a pool, B5b results, traceability flags |
| **Output** | PATCH_EXISTING / EXTEND_EXISTING / NEW_DESIGN_CANDIDATE / SKIP / NEEDS_REVIEW |
| **Responsibility** | Decision + selected `design_id` (or null) |
| **Forbidden** | Generating final prose; same-ID-alone positive decision |
| **Trace** | `trace/propagation_decisions.json` |
| **Failure** | Competing ALIGNED → NEEDS_REVIEW |

#### B6 Patch Planning
| | |
|--|--|
| **Purpose** | Map ACU → document/field/operation **plan** (semantic) |
| **Input** | B5c decisions |
| **Output** | `patch_plan[]` (`generation_status=PLANNED`) |
| **Responsibility** | What to change where — **not** final wording |
| **Forbidden** | Blind whole-CR multi-owner append; inventing Req/Design IDs |
| **Trace** | `trace/patch_plan.json` |
| **Failure** | Ambiguous field → `operation=REVIEW` |

#### Generation
| | |
|--|--|
| **Purpose** | Produce field text from plan + source spans |
| **Input** | patch plan, ACU spans |
| **Output** | generated strings per patch_id |
| **Responsibility** | Localized semantic text for **one ACU** |
| **Forbidden** | Re-deciding ownership; whole-CR dump when multiple ACUs exist |
| **Trace** | `trace/generated_patches.json` |
| **Failure** | Empty/unsafe generation → skip apply + NEEDS_REVIEW |

#### DOCX Patch Application
| | |
|--|--|
| **Purpose** | Write planned generated text into copies of refs |
| **Input** | generated patches, ref docx |
| **Output** | updated MDSR/MDDR + hashes |
| **Responsibility** | Mechanical apply + preserve structure |
| **Forbidden** | New judgments |
| **Trace** | `trace/patch_application.json` (+ diffs) |
| **Failure** | Locator miss → record failure, do not invent blocks |

#### Semantic Validation
| | |
|--|--|
| **Purpose** | Review flags, contradiction surfacing, human artifacts |
| **Input** | all traces + outputs |
| **Output** | CHANGE_SUMMARY / REVIEW_REQUIRED / eval hooks |
| **Responsibility** | Reporting |
| **Forbidden** | Silent auto-fix of ownership |
| **Trace** | `review/*` |

---

## 5. Atomic Change Unit Contract

### Schema

```json
{
  "change_id": "ACU-001",
  "source_span": "…verbatim CR substring…",
  "actor": [],
  "action": [],
  "object": [],
  "condition": [],
  "constraint": [],
  "output": [],
  "responsibility_type": "classify | display | update | enforce | audit | other",
  "provenance": {
    "cr_hash": "…",
    "span_start": 0,
    "span_end": 0,
    "decomposition_method": "rule_v0 | llm_v0 | FALLBACK_WHOLE_CR"
  }
}
```

### Rules

| Rule | Contract |
|------|----------|
| Multi-ACU | One CR **may** yield many ACUs |
| Multi-artifact | One ACU **may** map to MDSR and/or MDDR (via B6) |
| No Scenario parsing hard-codes | No inactive/3-day/Req.204 rules in decomposer |
| No keyword ownership lists | Responsibility_type is a **role enum**, not domain lexicon gate |
| Whole-CR append | **Forbidden direction** for multi-ACU; FALLBACK_WHOLE_CR forces conservative NEEDS_REVIEW / single-owner only with explicit flag |
| Parser | **Not implemented in this contract step**; Phase 4 introduces minimal structure |

Illustrative (non-normative) Scenario-001 units: classify-from-records / dashboard-identify / auto-refresh — used only in tests as fixtures, not production rules.

---

## 6. B5a — Design Candidate Discovery Contract

### Purpose
Collect design candidates that **might** own an ACU for a consistent (or reviewable) requirement.

### Inputs
- `requirement_id`, `atomic_change_id`, ACU
- Index blocks (MDDR)
- B3 decisions (IMPACTED / UNCERTAIN MDDR)
- Optional explicit traceability links
- Same-ID MDDR if present

### Candidate sources (minimum)

| Source | Meaning |
|--------|---------|
| `same_id` | MDDR with same Req ID as MDSR |
| `traceability` | Explicit MDSR↔MDDR link if present in corpus metadata |
| `b3_impacted` | B3 judgment IMPACTED on MDDR |
| `b3_uncertain_strong` | B3 UNCERTAIN MDDR with retrieval evidence above policy (rank/score bands — **policy later**, not hardcoded Scenario) |
| `structural_neighbor` | Optional later: shared component/API markers — optional |

### Rules

- **same_id ≠ owner**; **same_id ≠ PATCH evidence**
- B5a **must not** emit PATCH/EXTEND/SKIP
- Dedupe by `(document, design_id)`
- **Cap K** (recommended default 5–8): keep all `same_id` + `traceability`, then fill by B3 rank/score, then optional neighbors
- Shadow mode allowed: emit pool without changing decisions (Phase 2)

### Output schema

```json
{
  "requirement_id": "Req. …",
  "atomic_change_id": "ACU-001",
  "design_candidates": [
    {
      "design_id": "Req. …",
      "document": "MDDR",
      "sources": ["same_id", "b3_impacted"],
      "retrieval_rank": 5,
      "retrieval_evidence": {
        "hybrid_score": 0.0,
        "b3_judgment": "IMPACTED",
        "b3_change_type": "EXTEND_EXISTING"
      }
    }
  ]
}
```

### Trace
`trace/design_candidates.json`

---

## 7. B5b — Responsibility Alignment Contract

### Purpose
Decide whether a **specific** design candidate owns the ACU’s responsibility.

### Inputs
- ACU
- One design candidate (body/title/fields)
- Evidence provenance graph (see §8)
- Optional B3/B4 context **as derived nodes only**

### Judgment dimensions
actor · action · object · condition · constraint · responsibility · component role · data/interface flow

### Evidence classes

| Class | Role |
|-------|------|
| **DIRECT** | CR↔design span/concept binding for this ACU |
| **SUPPORTING** | Compatible secondary signal; cannot alone ALIGN |
| **GENERIC** | High-frequency / discourse / universal actors-objects |
| **CONFLICTING** | Responsibility mismatch / false-friend / negation |
| **MISSING** | Needed facet absent |

**Generic-only ⇒ cannot be ALIGNED.**  
Examples of *generic class* (illustrative, not Scenario rules): patient/user/admin labels; demonstratives; bare status/record/data/dashboard without action–condition binding.

### Outputs

`ALIGNED` | `PARTIAL_ALIGNMENT` | `NOT_ALIGNED` | `UNCERTAIN`

Each with:

```json
{
  "requirement_id": "...",
  "atomic_change_id": "...",
  "design_id": "...",
  "alignment": "ALIGNED | PARTIAL_ALIGNMENT | NOT_ALIGNED | UNCERTAIN",
  "evidence": [
    {
      "evidence_id": "EV-…",
      "class": "DIRECT | SUPPORTING | GENERIC | CONFLICTING | MISSING",
      "facet": "action",
      "note": "..."
    }
  ],
  "reason": "..."
}
```

### Forbidden
Emitting PATCH/EXTEND; treating same-ID as DIRECT ownership; counting prior copies as DIRECT.

### Trace
`trace/responsibility_alignment.json`

---

## 8. Evidence Provenance / Independence Contract

### Schema

```json
{
  "evidence_id": "EV-001",
  "source_type": "CR_DIRECT | DESIGN_DIRECT | B3_DERIVED | B4_DERIVED | TRACEABILITY",
  "source_span": "...",
  "concept": "...",
  "facet": "actor | action | object | condition | constraint | responsibility | other",
  "evidence_class": "DIRECT | SUPPORTING | GENERIC | CONFLICTING | MISSING",
  "derived_from": [],
  "independent_group": "G-…",
  "pair": "CR_DESIGN | MDSR_MDDR | CR_MDSR | NONE"
}
```

### Rules (normative)

1. **Same lineage / same `independent_group` → at most one contribution** to any confidence or “facet count.”
2. **B3_DERIVED / B4_DERIVED are context**, never sole DIRECT for ALIGNED/PATCH/EXTEND.
3. **`TRACEABILITY` / same-ID** is **not** ownership evidence; store separately from DIRECT.
4. **`pair=MDSR_MDDR` echo cannot replace `pair=CR_DESIGN`.**
5. Confidence formulas (future) must consume **independent_group** set — **not implemented in this step**.

### Anti-bleed example (forbidden pattern)

```text
CR "환자" → B3 actor → B4 compatible actor → B5 b3_prior_actor + B5 actor
= quadruple count of one independent_group
```

Contracted fix: one `EV` with `derived_from` chain; B5b sees one group.

---

## 9. B5c — Propagation Decision Contract

### Inputs
ACU · B5a candidates · B5b alignments · traceability flags · provenance summary

### Outputs

| Decision | Definition |
|----------|------------|
| **PATCH_EXISTING** | Selected design already owns ACU; ≥1 DIRECT discriminative; in-scope modify; no CONFLICTING |
| **EXTEND_EXISTING** | Clear responsibility connection; ≥1 DIRECT discriminative CR↔design; natural scope growth; **not** generic-only; **not** prior-only; **not** same-ID-echo-only; no contradiction |
| **NEW_DESIGN_CANDIDATE** | ACU impact clear; no safe ALIGNED/PARTIAL owner; **no** forced nearest thematic patch; no invented design ID |
| **SKIP** | NOT_ALIGNED / mismatch / false-friend / generic-only similarity |
| **NEEDS_REVIEW** | Multiple ALIGNED competitors; insufficient DIRECT; UNCERTAIN alignments; multi-ACU ownership conflict |

### Hard prohibitions
- same-ID alone → PATCH/EXTEND  
- generic-only → PATCH/EXTEND  
- prior-only → PATCH/EXTEND  
- MDSR↔MDDR echo-only → PATCH/EXTEND  

### Trace
`trace/propagation_decisions.json`  
(Legacy `propagation_trace.json` may wrap for compatibility during migration.)

---

## 10. B6 — Patch Planning Contract

### Purpose
Answer: *Which document, which id, which field, which operation for this ACU?*

### Separation

| Layer | Role |
|-------|------|
| **B6 Patch Planning** | Semantic plan (`generation_status=PLANNED`) |
| **Generation** | Concrete sentences from ACU `source_span` + intent |
| **Apply** | DOCX write |

B5c **must not** call whole-CR append helpers as a side effect of decision.

### Schema

```json
{
  "patch_id": "P-001",
  "atomic_change_id": "ACU-001",
  "target_document": "MDSR | MDDR",
  "target_id": "Req. …",
  "target_field": "title | description | purpose | criteria | design_body",
  "operation": "ADD | MODIFY | SPLIT | REVIEW",
  "semantic_intent": "…",
  "source_span": "…ACU span only…",
  "justification": "links to B5c decision id",
  "generation_status": "PLANNED"
}
```

### Rules
- One patch item scopes **one ACU** (or REVIEW if ambiguous).
- Blind whole-CR replication across many owners: **forbidden**.
- NEW_DESIGN → plan may be `operation=REVIEW` / proposal only (no DOCX insert in v3 first slices).

### Trace
`trace/patch_plan.json`

---

## 11. Runner Orchestration

### Current
```text
B3 → B4 → build_propagation_plan → apply_b4_b5_patches
```

### Target
```text
B3
 → B4
 → decompose_change_units
 → discover_design_candidates        (B5a)
 → align_design_candidates           (B5b)
 → decide_propagation                (B5c)
 → plan_patches                      (B6)
 → generate_patch_text
 → apply_patches
 → write_review / validate
```

### Compatibility shim
During Phase 1–2, `build_propagation_plan` may become a façade calling B5a→B5c with same-ID-only pool to preserve behavior, while emitting new trace files in shadow form.

---

## 12. Trace Artifact Contract

| File | Producer |
|------|----------|
| `trace/atomic_change_units.json` | Decomposition |
| `trace/design_candidates.json` | B5a |
| `trace/responsibility_alignment.json` | B5b |
| `trace/propagation_decisions.json` | B5c |
| `trace/patch_plan.json` | B6 |
| `trace/generated_patches.json` | Generation |
| `trace/patch_application.json` | Apply |
| `trace/impact_judgments.json` | B3 (existing) |
| `trace/consistency_decisions.json` | B4 (existing) |
| `trace/propagation_trace.json` | Legacy aggregate (optional bridge) |

All decisions must be reconstructible from traces without re-running LLM/heuristics.

---

## 13. Migration Plan

### Phase 1 — Interface split, behavior preserved
| | |
|--|--|
| **Modify** | `propagation.py` (extract B5a/B5b/B5c functions; façade `build_propagation_plan`); optional runner hook points |
| **Behavior** | Same-ID-only pool; same decisions as B5v2 as much as possible |
| **Tests** | Existing B5v2 + B4/B5 regression green |
| **Risk** | Refactor churn |
| **Acceptance** | Full pytest pass; no scenario freeze touch; golden unit outputs stable |
| **Rollback** | Revert PR |

### Phase 2 — Cross-ID candidate pool
| | |
|--|--|
| **Modify** | B5a sources: + `b3_impacted` MDDR; cap/dedupe; traces |
| **Tests** | Synthetic C/D/E (same-ID weak + cross-ID better); shadow eval optional |
| **Risk** | New FPs if alignment not ready — mitigate with **shadow mode** first (pool in trace, decisions still same-ID) then enable |
| **Acceptance** | Pool contains B3 IMPACTED MDDR; same-ID still present; no Scenario hard-codes |
| **Rollback** | Feature flag `enable_cross_id_candidates=false` |

### Phase 3 — Evidence provenance / anti-bleed
| | |
|--|--|
| **Modify** | Provenance schema; B5b classes; stop double-counting |
| **Tests** | G/H/I (generic-only, prior-only, false-friend) |
| **Risk** | Under-recall useful EXTEND |
| **Acceptance** | Acceptance criteria §15 provenance bullets; Req.100-class synthetic SKIP |
| **Rollback** | Flag off provenance gating |

### Phase 4 — Atomic Change Units (minimal)
| | |
|--|--|
| **Modify** | Decomposer v0 (conservative); B6 consumes ACU spans; block whole-CR multi-owner append |
| **Tests** | J/K multi-unit |
| **Risk** | FALLBACK_WHOLE_CR overuse |
| **Acceptance** | Multi-ACU fixture does not dump full CR into false owner |
| **Rollback** | Force FALLBACK + old text path behind flag |

### Phase 5 — B6 Patch Planning separation
| | |
|--|--|
| **Modify** | `plan_patches` distinct from `generate` / `apply`; runner orchestration |
| **Tests** | Plan-only unit tests; apply uses plan |
| **Risk** | Wiring bugs |
| **Acceptance** | `patch_plan.json` present; generate does not re-decide owners |
| **Rollback** | Façade plan-from-legacy |

### Phase 6 — New Scenario-001 rerun dir only
| | |
|--|--|
| **Modify** | None to freezes; new `scenario-001-rerun-b5v3/` (or similar) |
| **Tests** | Full pytest + freeze integrity |
| **Risk** | Eval interpretation |
| **Acceptance** | Contract acceptance criteria on unseen CR; no overwrite of b5v2 freeze |
| **Rollback** | N/A (evidence dir) |

---

## 14. Synthetic Test Matrix

| ID | Scenario | Expected B5a | Expected B5b | Expected B5c | Expected B6/Gen |
|----|----------|--------------|--------------|--------------|-----------------|
| **A** | same-ID true owner | includes same_id | ALIGNED (DIRECT) | PATCH_EXISTING | ACU-scoped ADD/MODIFY |
| **B** | same-ID false owner | includes same_id | NOT_ALIGNED | SKIP | no apply |
| **C** | same-ID weak + cross-ID better | both in pool | better ALIGNED; weak NOT/PARTIAL | prefer better or NEEDS_REVIEW — **not** weak EXTEND | plan to better owner |
| **D** | B3 IMPACTED MDDR cross-ID only | pool has it | align independently | PATCH/EXTEND/NEW/REVIEW per evidence | — |
| **E** | multiple plausible owners | ≥2 | ≥2 ALIGNED/PARTIAL | NEEDS_REVIEW | REVIEW ops |
| **F** | no existing owner | empty/weak | all NOT | NEW_DESIGN_CANDIDATE | proposal/REVIEW only |
| **G** | generic-only overlap | any | GENERIC only | SKIP | none |
| **H** | prior-only overlap | any | no DIRECT | SKIP or NEEDS_REVIEW | none |
| **I** | false-friend action | any | CONFLICTING | SKIP | none |
| **J** | multi-unit CR, different owners | per ACU pools | per ACU | per ACU decisions | **no** whole-CR to both |
| **K** | one ACU → MDSR+MDDR | — | ALIGNED | PATCH/EXTEND | two plan rows, same ACU span |
| **L** | non-security domain | works without lockout lexicon | — | — | — |

**No test code in this contract step.**

---

## 15. Acceptance Criteria (pre-implementation lock)

Must hold for architecture to be considered implemented:

1. same-ID is **candidate source only**  
2. same-ID **alone** cannot PATCH/EXTEND  
3. cross-ID design candidates **can** be evaluated  
4. B3 IMPACTED MDDR **can** enter B5a pool  
5. generic-only evidence **cannot** open PATCH/EXTEND  
6. prior-only evidence **cannot** open PATCH/EXTEND  
7. evidence lineage prevents duplicate independent counting  
8. traceability ≠ ownership  
9. whole CR is **not** blindly appended to multiple owners  
10. atomic changes can map to separate owners  
11. no safe owner → NEW_DESIGN or NEEDS_REVIEW  
12. all stage decisions traceable in JSON artifacts  
13. **no** Scenario-specific Req IDs / keywords in production logic  

---

## 16. Risks

| Risk | Mitigation |
|------|------------|
| Big-bang rewrite | Phased migration §13 |
| Cross-ID FPs | Shadow pool → provenance gating before decision cutover |
| Under-propagation of useful 110-class | Preserve discriminative DIRECT paths in tests A/L |
| Trial-2 regression | Keep façade + regression suite each phase |
| ACU decomposition quality | FALLBACK + NEEDS_REVIEW bias |
| Scope creep into B3/B4 | Explicit non-goals |

---

## 17. Non-goals (this architecture program)

- Threshold-only “B5v3” hotfix  
- Req.100/204/110/17 hard-codes  
- Scenario-001 keyword rules  
- Dense embedding as a required dependency for B5a v1  
- XXCS / form-fill changes  
- Editing frozen scenario/trial artifacts  
- Auto-inserting new Design IDs into DOCX  
- Rewriting B3/B4 in the same first PRs (B4 FP is a **separate** follow-up)

---

## 18. Recommended First Implementation PR

### Goal
Lowest regression risk: **structural separation without behavior change**.

### Scope (PR-1)

1. In `propagation.py`, extract pure functions:
   - `discover_design_candidates_b5a(...)` — **same-ID only** (behavior parity)
   - `align_design_candidate_b5b(...)` — logic lifted from current assess **without** changing outcomes
   - `decide_propagation_b5c(...)` — enum mapping from alignment result
2. `build_propagation_plan` becomes a thin orchestrator calling B5a→B5b→B5c with **one** candidate (same-ID).
3. Emit **additional** trace files (`design_candidates.json`, `responsibility_alignment.json`, `propagation_decisions.json`) alongside legacy `propagation_trace.json`.
4. **Do not** enable cross-ID pool yet (Phase 2).
5. **Do not** change `proposed_*` whole-CR behavior yet (Phase 4–5).
6. **Do not** rerun Scenario-001.

### Tests
- Existing `test_b5v2_propagation.py`, `test_b4_b5_consistency_propagation.py`, `test_user_scenario_runner.py` pass unchanged.
- Optional: assert new trace keys exist in a tmp scenario smoke.

### Explicitly next PR (PR-2)
Cross-ID B5a sources + shadow evaluation traces (Phase 2).

### Why this order
Separating interfaces first makes Phase 2 a **dataflow** change instead of a tangled rewrite; preserves B5v2 freeze meaning while unlocking contract compliance.

---

## Final checklist

| Item | Status |
|------|--------|
| Current code problem mapped | Yes (§1–3) |
| Target E2E architecture | Yes (§4) |
| Stage contracts ACU/B5a/B5b/provenance/B5c/B6 | Yes (§5–10) |
| Runner + traces | Yes (§11–12) |
| Migration phases | Yes (§13) |
| Synthetic matrix | Yes (§14) |
| Acceptance criteria locked | Yes (§15) |
| First PR scoped | Yes (§18) |

### Verdict

**READY_TO_IMPLEMENT_STAGED_B5_ARCHITECTURE**

Implementation must follow this contract and start with **PR-1 (interface split + parity traces)** — not threshold tuning and not a full rewrite in one PR.
