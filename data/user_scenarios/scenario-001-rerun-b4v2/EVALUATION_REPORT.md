# Scenario-001 B4v2 Rerun — Evaluation Report

- created_at: `2026-07-23T10:55:30Z`
- baseline: `data/user_scenarios/scenario-001/` (PARTIAL, FROZEN) — not modified
- B3v2 rerun: `data/user_scenarios/scenario-001-rerun-b3v2/` (PARTIAL, FROZEN) — not modified
- this rerun: `data/user_scenarios/scenario-001-rerun-b4v2/`
- purpose: measure B4v2 effect on unseen CR; **not** force PASS

## Component-level results

| Component | Result | Notes |
|-----------|--------|-------|
| Retrieval | PASS (stable) | Identical to baseline / B3v2 Top-k |
| B3 Impact Judgment | STABLE / PARTIAL | Identical to B3v2: IMPACTED 6 / NOT 8 / UNCERTAIN 1 |
| B4 Consistency | IMPROVED / PARTIAL | CONSISTENT **4** (was 0); no theme-keyword-miss fallback. Over-eager: Req.100 also CONSISTENT (FP defense miss) |
| B5 Propagation | BOTTLENECK / MIXED | PATCHED **1** (Req.100 MDDR only); 203/204/110 SKIPPED — lockout-shaped `_design_aligns` |
| Document Output | PARTIAL / RISKY | MDSR CR-append on 203/204/100/110; MDDR only Req.100; wrong owner got design patch |
| **Overall** | **PARTIAL** | B4 theme-miss bottleneck cleared; FP defense + B5 alignment remain |

## B4 candidate highlights

| Candidate | B3 | B4v1 (B3v2 rerun) | B4v2 | Notes |
|-----------|----|-------------------|------|-------|
| Req.204 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | observe↔mutate extend; evidence facets present |
| Req.110 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | observe API ↔ CR mutate/classify; justified extend lean |
| Req.203 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | registration/list — weaker ownership; over-inclusive |
| Req.100 | IMPACTED | NEEDS_REVIEW | **CONSISTENT** | **Should lean CONFLICT**; thematic neighbor not blocked |

Confidence alone did not drive CONSISTENT (compatible facets recorded); however facet rules were too permissive for Req.100.

## Overall verdict rationale

**PARTIAL**: B4v2 successfully escapes lockout theme-miss NEEDS_REVIEW and produces evidence-traced CONSISTENT on non-auth CR. End-to-end quality remains incomplete: (1) B4 FP defense failed on Req.100; (2) B5 patches the wrong MDDR via audit-theme align while skipping stronger clinical owners; (3) MDSR patches are raw CR-append, not field-precise semantics. Not PASS. Not FAIL (pipeline progressed safely with review artifacts; Trial freezes intact).

## Do not tune further in this step

Root causes / next candidates only — no code changes after this report.
