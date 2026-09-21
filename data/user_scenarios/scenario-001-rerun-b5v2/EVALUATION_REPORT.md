# Scenario-001 B5v2 Rerun — Evaluation Report

- executed_at: `2026-07-24T19:35:30Z`
- commit: `52c3af5a4ae045ec0efb79243975d1cda238e3dc`
- freezes not modified: baseline / B3v2 / B4v2 / Trial 1 / Trial 2
- purpose: measure B5v2 effect; **not** force PASS

## Component-level results

| Component | Result | Notes |
|-----------|--------|-------|
| Retrieval | PASS (stable) | Identical to B4v2 |
| B3 | STABLE | IMPACTED 6 / NOT 8 / UNCERTAIN 1 — identical |
| B4 | STABLE | CONSISTENT 4 — identical |
| B5 Propagation | IMPROVED / PARTIAL | PATCH_EXISTING 1, EXTEND 2, SKIP 1; audit-theme path gone; Req.100 residual EXTEND FP |
| MDSR safety gate | PARTIAL | Req.203 blocked ✓; 204/110 allowed; **100 still allowed** |
| MDDR patch | MIXED | 204/110 useful; **100 wrong owner remains** |
| NEW_DESIGN | none | 0 |
| Document semantics | PARTIAL / RISKY | CR append on 204/100/110; 100 contamination persists |
| **Overall** | **PARTIAL** | |

## Verdict rationale

**PARTIAL**: B5v2 removes the B4v2 `감사`-theme false-align path, correctly SKIPs Req.203 (no MDSR/MDDR pollution), and enables useful PATCH/EXTEND on Req.204/110. However Req.100 still receives EXTEND_EXISTING / document patch via weak CR↔design token evidence (`해당` etc.), so wrong-owner contamination is **not fully eliminated**. Not PASS. Not FAIL (targeted audit-theme regression fixed; useful propagation appeared).

## Do not tune further in this step

Residual bottleneck recorded only — no post-rerun code changes.
