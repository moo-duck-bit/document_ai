# B4v2 Implementation Report

**Date:** 2026-07-23  
**Scope:** Domain-independent consistency gate only (no Scenario-001 rerun, no B3/B5/DOCX changes).

---

## 1. Previous B4 structure

Legacy B4 (`consistency_gate.py` pre-B4v2) was a **role × theme matcher**:

1. Classify requirement role ∈ `{ux, audit, policy, other}` via auth/UX/policy keywords.
2. Detect CR themes via `POLICY_TERMS` / `UX_TERMS` / `AUDIT_TERMS`.
3. Hard gates:
   - `ux` + policy CR → **CONFLICT** (Trial-1 Req.6 pattern)
   - `audit` + audit CR → **CONSISTENT**
   - `policy` + policy CR → **CONSISTENT**
4. Else → **NEEDS_REVIEW** (“Insufficient evidence…”) — dominated Scenario-001 non-lockout CRs.
5. B3 evidence was **not** passed into `check_consistency`.

---

## 2. Removed / isolated domain-specific logic

| Item | Disposition |
|------|-------------|
| `POLICY_TERMS` / `UX_TERMS` / `AUDIT_TERMS` as decision bags | **Removed from core path** |
| `_role()` ux/audit/policy classifier | **Removed from core path** |
| Lockout hard-coded CR evidence spans / reasons | **Removed from core path** |
| Theme-miss → NEEDS_REVIEW fallback | **Removed** |
| Legacy theme bags | **Isolated** as `legacy_lockout_theme_hits()` diagnostic helper — **not called** by `check_consistency` / `gate_impacted_decisions` |

Legacy path does **not** dominate default decisions.

---

## 3. New domain-independent decision structure

**Question:** Can this CR be modify/extend-applied to this Requirement without breaking its responsibility/meaning?

**Facets evaluated:**

- actor compatibility  
- action compatibility  
- object / scope compatibility  
- condition mapping  
- constraint / field presence  
- responsibility via cross-domain **action families** (`inform`, `enforce`, `audit`, `observe`, `mutate`, `manage`)  
- contradiction risk (family conflict pairs, e.g. enforce vs inform ownership)  
- missing information  

**Families** are generic software/requirements verbs — not auth/lockout scenario keywords, and not Scenario-001 terms (`비활성`, `3일`, inactive patient, etc.). No Req.204/110/203/100 hard-codes.

**Outputs per candidate:**

```json
{
  "candidate": "...",
  "document": "...",
  "consistency": "CONSISTENT | CONFLICT | NEEDS_REVIEW",
  "status": "...",
  "evidence": {
    "compatible_facets": [],
    "conflicting_facets": [],
    "missing_information": [],
    "cr_spans": [],
    "candidate_spans": [],
    "facet_detail": {}
  },
  "reason": "...",
  "confidence": 0.0,
  "b3_prior": {},
  "allow_auto_patch": true/false
}
```

`confidence` is informational; **never** sole CONSISTENT trigger (guard rejects CONSISTENT with empty core compatible facets).

---

## 4. B3 evidence handoff

`gate_impacted_decisions` now forwards each IMPACTED B3 decision dict into `check_consistency(..., b3_decision=d)`.

Prior fields consumed (read-only):

- `cr_spans`, `candidate_spans`
- `matched_concepts`, `behavioral_overlap`
- `change_type`, `reason`, `confidence`
- judgment label

B4 uses priors to enrich spans / soft compatible hints (`b3_prior_*`) but **does not copy** B3 IMPACTED → CONSISTENT.

---

## 5. CONSISTENT / CONFLICT / NEEDS_REVIEW criteria

| Status | Criteria (summary) |
|--------|-------------------|
| **CONSISTENT** | Responsibility families compatible; ≥1–2 core compatible facets; no conflicting facets; object/token/action overlap evidence; allow_auto_patch=True |
| **CONFLICT** | Responsibility/action hard conflict (e.g. enforce CR onto inform-owned title/purpose); or thematic-neighbor FP (low object/responsibility alignment with enough CR content) |
| **NEEDS_REVIEW** | Ambiguous / missing facet evidence; vague short CR; cannot prove safe extend or hard conflict — **not** “theme keyword miss” |

MODIFY_EXISTING and EXTEND_EXISTING from B3 may both map to CONSISTENT when facets allow.

---

## 6. Test results (targeted)

| Suite | Result |
|-------|--------|
| `tests/test_b4v2_consistency_gate.py` (A–G + evidence/confidence guards) | PASS |
| `tests/test_b4_b5_consistency_propagation.py` (Trial-2 Req.6/103/105) | PASS |
| `tests/test_user_scenario_runner.py` smoke/conflict | PASS |

**Full suite:** `python -m pytest -q` → **373 passed / 0 failed / 0 skipped** (~162s).

**Regression note:** Trial-2 expectations **unchanged** — Req.6 still CONFLICT, Req.103/105 still CONSISTENT — now via family/facet rules (inform vs enforce; audit/enforce alignment), not POLICY/UX/AUDIT bags. Assertions were **not** weakened.

---

## 7. Regression results

Trial-2 lockout/audit/UX path behavior preserved under B4v2 facet rules (see §6). No assertion softening.

---

## 8. Freeze integrity

Verified post-test (canonical hashes / freeze flags):

| Artifact | Status |
|----------|--------|
| `data/user_scenarios/scenario-001/` | OK PARTIAL |
| `data/user_scenarios/scenario-001-rerun-b3v2/` | untouched (manifest still `PARTIAL` @ `2026-07-23T02:41:42Z`) |
| Trial 2 | OK PASS |
| Trial 1 | freeze flag True / FAILED |

**Scenario-001 was not re-run** in this step.

---

## 9. Known risks

1. **Family marker coverage:** Rare domains with unfamiliar verbs may under-fire → more NEEDS_REVIEW (safe bias).
2. **Object Jaccard on short Korean text:** Tokenization can under-estimate object overlap; mitigated by action/responsibility paths.
3. **B5 unchanged:** Even if B4 returns CONSISTENT on non-lockout CRs, B5 `_design_aligns` may still block MDDR patches (expected next bottleneck).
4. **False CONFLICT:** Aggressive thematic-neighbor rule could over-block borderline extends — monitored via Case B allowing CONSISTENT|NEEDS_REVIEW.
5. **Legacy helper leftover:** `legacy_lockout_theme_hits` exists for diagnostics only; must stay unused in core.

---

## 10. Rerun readiness

Ready for a **separate** Scenario-001 B4v2 rerun directory after approval, provided full pytest PASS and freezes intact.

Do **not** overwrite `scenario-001` or `scenario-001-rerun-b3v2`.

---

## Files touched

- `src/document_ai/impact/consistency_gate.py` — B4v2 core rewrite + B3 prior wiring  
- `tests/test_b4v2_consistency_gate.py` — synthetic Cases A–G  
- `docs/impact_judgment/B4V2_IMPLEMENTATION_REPORT.md` — this document  

B5 / B3 / runner patch logic intentionally untouched (runner already passed full B3 dicts into `gate_impacted_decisions`).
