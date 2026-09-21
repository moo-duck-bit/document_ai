# Scenario-001 B3v2 Rerun — Evaluation Report

- created_at: `2026-07-23T02:41:42Z`
- baseline: `data/user_scenarios/scenario-001/` (PARTIAL, FROZEN) — not modified
- rerun: `data/user_scenarios/scenario-001-rerun-b3v2/`
- purpose: measure B3v2 effect on unseen CR; **not** force PASS

## Component-level results

| Component | Result | Notes |
|-----------|--------|-------|
| Retrieval | PASS (stable) | Identical to baseline Top-k |
| B3 Impact Judgment | IMPROVED / PARTIAL | IMPACTED 0→6; evidence traces present |
| NEW_REQUIREMENT Handling | N/A or PASS-safety | IMPACTED>0 ⇒ zero-IMPACTED fallback correctly idle (`proposal_file=False`) |
| B4 | BOTTLENECK | summary={'CONSISTENT': 0, 'CONFLICT': 0, 'NEEDS_REVIEW': 4}; 0 CONSISTENT → no auto-patch |
| B5 | NO_PATCH | summary={'PATCHED': 0, 'SKIPPED_WITH_REASON': 0, 'NEEDS_REVIEW': 4} |
| Document Output | NO_CR_CONTENT_PATCH | patched IDs empty |
| **Overall** | **PARTIAL** | B3 better; end-to-end CR still not applied |

## Valid outcome paths

- PATH A (existing IMPACTED): **partially entered** (IMPACTED>0) but blocked at B4 NEEDS_REVIEW.
- PATH B (NEW_REQUIREMENT): **not taken** (because IMPACTED>0).

## Overall verdict rationale

**PARTIAL**: B3v2 achieved domain-independent IMPACTED with structured evidence on an unseen non-lockout CR, without retrieval drift and without destructive patches. However the scenario still fails to produce CONSISTENT auto-updates or NEW_REQUIREMENT proposal (PATH B idle), and B4/B5 leave documents without CR semantics. Not PASS. Not FAIL (no wrong silent overwrite; safety intact).

## Do not tune further in this step

Root causes / next candidates only — no code changes after this report.

