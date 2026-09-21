# Document-TNR Paper Skeleton (RQ1–RQ3)

**Status**: draft skeleton aligned with implementation  
**Venue target**: SANER 2027 (primary) / FSE 2027  
**Thesis**: Document write agents may draft or patch, but must not worsen the externally visible document state — formalized as **Document-TNR**, enforced in a DOCX pipeline, validated on holdout + pilot with Safety-first metrics.

---

## Title (working)

**Document-TNR: A Non-Regression Safety Contract for Document Write Agents**

Optional subtitle: *Dual-mode Form Fill and Change Impact under one transaction guarantee*

---

## Abstract (outline)

Document automation agents that write DOCX sets risk silent damage to originals and unapproved edits. We define **Document-TNR**, a document-domain non-regression contract: after a transaction, severity μ = (false_patch, unsafe_write, original_broken, unapproved_write) must remain zero and source fingerprints must match baseline *b*. We enforce the contract in a dual-mode agent (Form Fill = `new`, Change Impact = `change`) via impact localization (B1–B5), copy-only writes, and a human approval gate. On a real-user pilot and sealed holdout writer expectations, the full system satisfies Document-TNR; ablating the gate or copy-only invariant yields counterfactual violations. Field F1 / usability are reported as secondary usefulness, not as the primary claim.

---

## 1. Introduction

- Problem: LLM/agent document writers can hallucinate structure and overwrite sources.
- Gap: Prompt-level safety ≠ transactional non-regression for document sets.
- North Star: Form Fill from blank template + case; today’s substrate is Change Impact safety.
- Contribution: (1) Document-TNR definition, (2) DOCX enforcement, (3) Safety-first validation + ablation.

## 2. Related Work

- SRE / agent TNR (e.g. STRATUS-style): safety-before-write posture — **inspiration, not domain transfer**.
- Doc automation / multi-agent writing (DocAgent etc.): generation quality ≠ write safety.
- Change impact / traceability in SE documents.
- Position: we do **not** port AIOpsLab; we redefine observables for DOCX document sets.

## 3. RQ1 — Document-TNR Definition

**Statement.** A document-set write transaction satisfies Document-TNR iff  
μ(s) = (false_patch, unsafe_write, original_broken, unapproved_write) = **0** and every source original still matches baseline fingerprint **b**.

| Component | Meaning |
|-----------|---------|
| false_patch | Wrong document/node relative to gold or human review |
| unsafe_write | Auto-approve / path escape / policy-violating write path |
| original_broken | Source fingerprint changed (copy-only broken) |
| unapproved_write | Write without explicit human approval |

**Modes (same contract):** `new` (Form Fill) · `change` (Change Impact).

Export: `document_ai.safety.document_tnr.document_tnr_definition()`.

## 4. RQ2 — Enforcement in the DOCX Pipeline

How Document-TNR is forced:

1. **Read/write split** — analysis agents propose; writer is gated.
2. **Impact localization (B1–B5)** — bundle affected locations for human review.
3. **Human approval gate** — no write without explicit approve.
4. **Copy-only writer** — originals never mutated; fingerprint *b* preserved.
5. **C1 dependency closure** — patch/rollback candidates expanded via traceability.
6. **Deterministic control flow** — LLM only in constrained data paths (e.g. free_text).

Dual-mode entry: `DocumentAgent` (`mode=new|change`) with `DocumentTNRSpec`.

## 5. RQ3 — Validation (Safety first)

### 5.1 Primary evidence

- **Pilot** (`data/pilot/results/pilot_run_01`): observed μ = 0, TNR satisfied; trust/usability secondary.
- **Holdout writer expectations**: sealed labels require GATED + original unchanged for all cases.

### 5.2 Ablation

| Variant | What is removed | Expected break |
|---------|-----------------|----------------|
| `full` | — | TNR holds (observed) |
| `no_gate` | human approval | unapproved_write / unsafe_write |
| `no_copy_only` | copy-only | original_broken |
| `no_closure` | C1 expansion | incomplete dependent set (false_patch proxy + closure delta) |

Counterfactuals are derived from gated sessions / labels — we do not disable safety in live writes.

### 5.3 Secondary (not primary claim)

- Field F1 on Form Fill cases (`hospital_reservation`, `mindrium_xa`)
- Pilot trust / usability scores

### 5.4 Reproduce

```bash
python -m document_ai.cli rq3-experiment
# outputs: data/eval/results/document_tnr/rq3_experiment.{json,md}
```

## 6. Discussion

- Form Fill is the North Star under the **same** contract, not a competing system.
- Limitations: counterfactual ablation; broader DOCX corpora; XXCS template gaps.
- Threats: pilot size; sealed-label coverage.

## 7. Conclusion

Document-TNR makes “do not make the visible document state worse” a checkable contract; B1–B5 + copy-only + gate enforce it; pilot/holdout show Safety holds while usefulness remains secondary.

---

## Artifact checklist

- [x] `document_tnr_definition()` / μ mapping
- [x] Dual-mode `DocumentAgent`
- [x] RQ3 experiment runner + markdown tables
- [ ] Camera-ready figures (pipeline diagram, ablation bar chart)
- [ ] Venue-format LaTeX
