# B5 Staged Architecture — PR-5 B6 Semantic Patch Planning Report

**Verdict:** `READY_FOR_STAGED_B5_PR6`  
**Scope:** B6 Semantic Patch Planning as **shadow-only** layer.  
**Date:** 2026-07-25

---

## 1. PR-5 Objective

Implement B6 to answer:

> Which ACU meaning should be reflected on which document / id / field with which operation?

B6 does **not** find owners, re-judge B3–B5, generate final prose, or mutate DOCX.

> **B6 output ≠ actual document mutation.**  
> Actual whole-CR append path remains unchanged in PR-5.

---

## 2. Current Whole-CR Patch Problem

Actual path still does:

`proposed_mdsr_description` / `proposed_mddr_design_description` → whole CR append into every allowed owner.

B6 shadow plans show ACU-scoped alternatives for comparison without switching over yet.

---

## 3. PatchPlan Schema

Module: `src/document_ai/impact/patch_plan.py`

```text
PatchPlanItem:
  patch_id, atomic_change_id
  target_document, target_id, target_field
  operation          # ADD | MODIFY | EXTEND | SPLIT | NO_CHANGE | REVIEW
  semantic_intent    # ACU-scoped; not whole CR
  source_cr_span, justification
  owner_evidence_ids, provenance
  planning_status    # PLANNED | NEEDS_REVIEW | BLOCKED
  review_reason
  plan_group_id, conflict_status, merge_candidate
```

---

## 4. ACU → Plan Mapping

- Input: PR-4 `AtomicChangeUnit` list + actual B5c `PropagationTrace`s  
- Owner match requires **responsibility overlap** (ACU action/object vs owner evidence)  
- No blind cloning of one whole-CR owner onto every ACU  
- Unmatched ACU → `NEEDS_REVIEW`  
- Ambiguous / NEEDS_REVIEW ACU → no auto PLANNED items  

`semantic_intent_from_acu` builds intent from ACU facets only.

---

## 5. Target Field Selection

Grounded in existing parsers (`FieldSnapshot` + MDDR body):

| Document | Allowed fields |
|----------|----------------|
| MDSR | `title`, `description`, `purpose`, `criteria` |
| MDDR | `title`, `design_body`, `design_condition` |

Rules (domain-independent):

- MDSR behavior/capability → prefer `criteria`  
- MDDR logic → `design_body`; with condition → also `design_condition`  
- Uncertain → REVIEW (no invented fields)  

---

## 6. B5c Decision Mapping

| B5c | B6 |
|-----|----|
| PATCH_EXISTING | PLANNED ADD/MODIFY on matched fields |
| EXTEND_EXISTING | PLANNED EXTEND |
| NEW_DESIGN_CANDIDATE | REVIEW; `target_id=null`; no existing field auto-plan |
| SKIP | ignored for planning (or no plan) |
| NEEDS_REVIEW owner | no auto plan against that owner |

---

## 7. Provenance Chain

Each plan carries:

CR span → `atomic_change_id` → ACU `evidence_ids` → B5c decision / owner id → `path=shadow_only`

---

## 8. Multiple Owner Support

- One ACU → N plans (MDSR + MDDR) when match + design alignment  
- Multiple ACUs → different owners when overlap differs  
- Multiple ACUs → same target → `plan_group_id` + conflict metadata  

---

## 9. Conflict / Duplicate Planning

Same `(document, id, field)` groups:

- `compatible` | `potentially_duplicate` | `conflict`  
- `merge_candidate=true`  
- **No auto-merge** in PR-5  

---

## 10. Shadow Traces

| File | Role |
|------|------|
| `patch_plan_shadow.json` | ACU units + patch plans |
| `legacy_vs_patch_plan_shadow.json` | whole-CR legacy targets vs ACU-scoped plans |

Runner writes these after B5 apply traces exist; **apply path unchanged**.

---

## 11. Synthetic Tests

`tests/test_b5_staged_pr5_b6_patch_plan.py` — A–J + Inventory / Reservation / Reporting.

---

## 12. Actual Behavior Parity

- B3/B4/B5 decisions unchanged  
- `allow_mdsr_patch` / patched IDs / `proposed_*` unchanged  
- B6 is observational only  

---

## 13. Full pytest

```text
python -m pytest -q
→ 443 passed in 178.08s (0 failed, 0 skipped)
```

Baseline was 430; PR-5 adds B6 shadow planning tests (+13). No regressions.

---

## 14. Freeze Integrity

Unmodified / not re-run: scenario-001, b3v2, b4v2, b5v2, Trial 1, Trial 2.

---

## 15. Known Limitations

- B6 shadow only  
- actual whole-CR patch remains  
- cross-ID actual owner selection still inactive  
- ACU actual B3/B4/B5 processing inactive  
- final text generation not implemented  
- semantic validation not integrated with B6 yet  

---

## 16. Next PR Recommendation (PR-6)

Feature-flagged cutover: when ACU has PLANNED plans, generate **ACU-scoped** text from `semantic_intent` + `source_cr_span` instead of whole-CR append; keep REVIEW/unmatched on legacy or block. Still no Scenario hard-codes; gate with golden parity tests.

**Final judgment:** `READY_FOR_STAGED_B5_PR6`
