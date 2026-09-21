# B5 Staged Architecture — PR-4 Atomic Change Unit Report

**Verdict:** `READY_FOR_STAGED_B5_PR5`  
**Scope:** Minimal viable ACU decomposition for trace / shadow analysis.  
**Date:** 2026-07-25

---

## 1. PR-4 Objective

Introduce an Atomic Change Unit (ACU) layer that structures a Natural Language Change Request into independently ownable meaning units — **without** changing actual B3/B4/B5 decisions or whole-CR patch text.

> **PR-4 introduces ACU decomposition but does not yet replace whole-CR patching.**

---

## 2. Whole-CR Problem

A single CR may bundle multiple responsibilities (classify / display / update / notify). Treating it as one opaque string causes whole-CR append into every allowed owner. ACU decomposition is the prerequisite for scoped patch planning (B6).

---

## 3. ACU Schema

Module: `src/document_ai/impact/atomic_change.py`

```text
AtomicChangeUnit:
  change_id              # ACU-001, ACU-002, …
  source_span
  actor / action / object / condition / constraint / output
  responsibility_type    # classify | display | update | enforce | audit | other
  provenance             # cr_hash, span offsets, evidence_ids, independent_group, method
  confidence
  decomposition_status   # EXTRACTED | AMBIGUOUS | NEEDS_REVIEW
```

---

## 4. Decomposition Rules (rule_v0)

1. Sentence segmentation (`.` / `。` / newlines)  
2. Clause segmentation on connectives (`하고`, `하며`, `고␠`, `그리고`, `,`, `및`)  
3. Action stem matching (incl. conjugations like `알린다`, `바꾸고`) with actor-embedding guard (`관리` ⊂ `관리자` skipped)  
4. If ≥2 clauses each have actions → one ACU per actionable clause  
5. Single action sentence → one EXTRACTED ACU  
6. Multi-action without safe clause split → AMBIGUOUS / NEEDS_REVIEW (no forced split)  
7. Shared actor carry-over from prior ACU when omitted  
8. Sentence-level conditions attach to the first actionable clause  

No Scenario Req-ID or domain special cases.

---

## 5. Ambiguity Handling

| Case | Status |
|------|--------|
| No action markers | `NEEDS_REVIEW` (`FALLBACK_WHOLE_CR`) or orphan note on prior unit |
| Multi-action, same responsibility, no clean clauses | `AMBIGUOUS` |
| Unsafe multi-responsibility split | `AMBIGUOUS` |

---

## 6. Provenance Integration

Each ACU records:

- `source_span` + `span_start` / `span_end`  
- `independent_group` via PR-3 `independent_group_for_span`  
- `evidence_ids` via `make_evidence_id(..., stage="ACU")`  
- `decomposition_method`: `rule_v0` | `FALLBACK_WHOLE_CR`  

---

## 7. Runner Integration

In `runner.py`, after retrieval and **before B3**:

1. `decompose_change_request(cr_text)`  
2. Write `output/trace/atomic_change_units.json`  
3. B3/B4/B5 continue to use **whole** `cr_text`  

Shadow hooks included in the trace payload (not executed):

- `acu_as_requirement_discovery_input`  
- `acu_as_design_discovery_input`  

---

## 8. Trace Schema

`atomic_change_units.json`:

```json
{
  "stage": "ACU",
  "source_cr": "...",
  "units": [ ... ],
  "shadow_hooks": {
    "requirement_discovery_inputs": [...],
    "design_discovery_inputs": [...]
  },
  "note": "…does not yet replace whole-CR patching…"
}
```

---

## 9. Synthetic Tests

`tests/test_b5_staged_pr4_atomic_change.py`

| ID | Coverage |
|----|----------|
| A | Single responsibility → 1 ACU |
| B | Two independent actions |
| C | Shared actor inheritance |
| D | Condition attached to create action |
| E | Ambiguous conjunction handling |
| F | Multi-sentence stable `ACU-00N` order |
| G | Provenance `source_span` / evidence ids |
| H | No Scenario hard-codes in module source |
| I/J | Actual plan decision / patch eligibility unchanged |
| Domains | Inventory / Reservation / Reporting |

---

## 10. Behavior Parity

- Actual B3 input = whole CR  
- B4 / B5 / `allow_mdsr_patch` / `proposed_*_description` unchanged  
- ACU is observational only  

---

## 11. Full pytest

```text
python -m pytest -q
→ 430 passed in 189.93s (0 failed, 0 skipped)
```

Baseline was 417; PR-4 adds ACU tests (+13). No regressions.

(Note: one earlier full-run flake in unrelated `test_xxcs_pipeline` round-trip; re-run clean: 430 passed.)

---

## 12. Freeze Integrity

Unmodified / not re-run:

- scenario-001, b3v2, b4v2, b5v2  
- trial-001-mindrium-xa, trial-002-lockout-multireq  

---

## 13. Known Limitations

- actual B3/B4/B5 still whole-CR based  
- cross-ID still shadow only  
- ACU owner selection not active  
- whole-CR patch actual behavior unchanged  
- B6 not implemented  
- full semantic decomposition not complete (rule_v0 only)  

---

## 14. PR-5 Recommendation

Next: use ACU + provenance to **gate** or **shadow-score** per-unit design alignment (still without auto-activating cross-ID owners), then introduce B6 patch plans that emit ACU-scoped spans instead of whole-CR append.

**Final judgment:** `READY_FOR_STAGED_B5_PR5`
