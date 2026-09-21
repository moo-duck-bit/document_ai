# B5v2 Implementation Report

**Date:** 2026-07-25  
**Scope:** Domain-independent design propagation only (no Scenario-001 rerun; no B3/B4 changes).

---

## 1. Previous B5 structure

Legacy B5 (`propagation.py` pre-B5v2):

1. Pair MDSR↔MDDR by **same Req ID** only.
2. `_design_aligns` = Trial-2 **theme co-occurrence** bags:
   - 감사/audit
   - 안내/에러/오류/메시지
   - 잠금/임계/차단/제한
   - fallback: both contain `로그인`
3. `cr_text` passed but **unused**.
4. B4 CONSISTENT + aligned → MDDR CR-append PATCH.
5. MDSR CR-append on **every** B4 CONSISTENT — **no** design ownership gate.
6. B3/B4 facet evidence **not** consumed.

Failure mode (Scenario-001 B4v2 freeze): Req.100 false PATCH via `감사`; 204/110 false SKIP despite related designs; MDSR polluted on all four CONSISTENT IDs.

---

## 2. Removed / isolated theme logic

| Item | Disposition |
|------|-------------|
| Theme pair bags in core `_design_aligns` | **Removed from decision path** |
| Login co-occurrence gate | **Removed from decision path** |
| Theme-hit → PATCH | **Removed** |
| `legacy_theme_design_aligns()` | **Isolated** diagnostic helper — not called by plan/apply |
| Compat `_design_aligns` | Now wraps `assess_design_propagation` (evidence-based) |

Legacy must not dominate default decisions.

---

## 3. New responsibility / facet alignment structure

Core API: `assess_design_propagation(cr, mdsr, mddr, decision, b3_prior)`.

Judges using:

- CR↔MDDR content object overlap (weak boilerplate tokens demoted: 감사/서버/시스템/…)
- Actor / action facet overlap with **CR participation required**
- MDSR↔MDDR as secondary support, not sufficient alone
- Direct traceability (`same_req_id`) as prior only
- B4 status (CONFLICT → SKIP; not auto-eligible → NEEDS_REVIEW)
- Structured `PropagationEvidence`

`build_propagation_plan` emits `PropagationTrace` with:

- `propagation_decision`
- `structured_evidence`
- `confidence` (informational; never sole PATCH trigger)
- `allow_mdsr_patch`
- `b3_prior` / `b4_prior`

---

## 4. B3/B4 evidence handoff

| Source | Fields | Usage |
|--------|--------|-------|
| B3 (runner passes `b3_decisions=`) | matched_concepts, behavioral_overlap, spans, change_type, reason | Priors for spans/facets; **not** copied as PATCH |
| B4 (`ConsistencyDecision`) | consistency, compatible/conflicting/missing facets, reason | Gate + prior detail in evidence |
| CR text | full | **Required** for CR↔design ownership |

Minimal runner change: `build_propagation_plan(..., b3_decisions=[d.to_dict() for d in decisions_b3])`.

---

## 5. Decision criteria

| Decision | When |
|----------|------|
| **PATCH_EXISTING** | CR↔design object/action alignment strong; no conflicts; B4 CONSISTENT |
| **EXTEND_EXISTING** | Related design + partial CR align / novel scope |
| **NEW_DESIGN_CANDIDATE** | No MDDR block or no safe owner; **no** Req/Design ID invention; **no** DOCX insert |
| **SKIP** | B4 CONFLICT; or responsibility mismatch / boilerplate-without-CR (Req.100-class) |
| **NEEDS_REVIEW** | Same-ID present but CR↔design evidence insufficient; B4 not auto-eligible |

Apply mapping: PATCH/EXTEND → outcome `PATCHED` (if design delta exists); SKIP → `SKIPPED_WITH_REASON`; NEW_DESIGN/NEEDS_REVIEW → `NEEDS_REVIEW`.

---

## 6. Req.100-class false propagation defense

General rule (no Req-ID hard-code):

> If MDSR↔MDDR share content (often audit/boilerplate) but **CR↔MDDR** lacks object/action alignment → **SKIP** (`responsibility_mismatch` / `boilerplate_overlap_without_cr`).

Synthetic Case C + `test_legacy_theme_helper_isolated_not_required_for_patch` encode this: legacy `감사` pair would align; B5v2 **SKIPs**.

---

## 7. MDSR patch safety analysis

**Previous coupling:** `B4 CONSISTENT == unconditional MDSR CR append` (independent of `_design_aligns`).

**B5v2 safety gate (minimal, B4 logic untouched):**

- `proposed_mdsr_description` still B4-gated (for unit helpers / Trial text checks).
- `apply_b4_b5_patches` applies MDSR append **only if** `trace.allow_mdsr_patch` (PATCH_EXISTING / EXTEND_EXISTING with design delta).

Therefore B4 CONSISTENT alone no longer forces MDSR pollution when design ownership is SKIP/NEW_DESIGN/NEEDS_REVIEW.

B4 judgment code was **not** modified.

---

## 8. Test results (targeted)

| Suite | Result |
|-------|--------|
| `tests/test_b5v2_propagation.py` (A–G + schema/gate/legacy isolation) | PASS |
| `tests/test_b4_b5_consistency_propagation.py` | PASS |
| `tests/test_user_scenario_runner.py` | PASS |

**Full suite:** `python -m pytest -q` → **382 passed / 0 failed / 0 skipped** (~223s).

---

## 9. Regression results

Trial-2 expectations preserved without reintroducing theme bags:

- Req.6 B4 CONFLICT → B5 SKIP / no MDSR auto text via `proposed_mdsr_description`
- Req.103 / 105 remain eligible for PATCHED or SKIPPED_WITH_REASON under evidence rules (assertions unchanged; not weakened)

If future Trial-2-only theme pairs were the sole align signal without CR↔design content, B5v2 correctly requires CR participation — that is intentional semantics, not assertion softening.

---

## 10. Freeze integrity

Verified post-test:

| Artifact | Status |
|----------|--------|
| `scenario-001` | OK PARTIAL |
| `scenario-001-rerun-b3v2` | intact (B4 0 CONSISTENT / 4 NEEDS_REVIEW) |
| `scenario-001-rerun-b4v2` | intact (B4 4 CONSISTENT; B5 PATCHED 1) |
| Trial 2 | OK PASS |
| Trial 1 | freeze True / FAILED |

**Scenario-001 was not re-run** in this step.

---

## 11. Known risks

1. Token/Jaccard under-estimate on short Korean text → more NEEDS_REVIEW (safe bias).
2. Cross-ID better design owners still not searched (same-ID candidate only) — follow-up possible.
3. NEW_DESIGN is trace-only; humans must act.
4. Over-SKIP if CR and design use disjoint synonyms — monitor in future rerun.
5. WEAK_TOKENS demotes `감사` alone — intentional; audit CRs still align when CR shares audit/event content beyond boilerplate.

---

## 12. Rerun readiness

Ready for a **separate** Scenario-001 B5v2 rerun directory after approval, provided full pytest PASS and freezes intact.

Do **not** overwrite `scenario-001-rerun-b4v2` or earlier freezes.

---

## Files touched

- `src/document_ai/impact/propagation.py` — B5v2 core
- `src/document_ai/scenario/runner.py` — B3 evidence handoff + decision summary
- `tests/test_b5v2_propagation.py` — Cases A–G
- `docs/impact_judgment/B5V2_IMPLEMENTATION_REPORT.md` — this document
