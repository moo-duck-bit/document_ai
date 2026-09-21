# Holdout Human Review Protocol

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


**Document type:** Evaluation protocol (paper-ready)  
**Version:** 1.0  
**Date:** 2026-07-14  
**Holdout case:** `hospital_reservation`  
**Companion:** [`human_evaluation_protocol.md`](human_evaluation_protocol.md), [`gold_dataset_design.md`](gold_dataset_design.md)

---

## 1. Holdout selection rationale

| Criterion | Why `hospital_reservation` |
|-----------|----------------------------|
| Domain shift | Medical appointment domain vs ecommerce train cases (`lab_ec_sw`, `jm_collection`, `inventory_mgmt`) |
| Pipeline coverage | Same MDSR/MDDR harness; tests generalization of replacement + structure |
| Prior auto score | Holdout harness score **94.3 PASS** (provisional self-gold) — strong *candidate*, not yet human-approved |
| Freeze-friendly | Single holdout keeps experimental control simple for a short paper |

Train set (3): `lab_ec_sw`, `inventory_mgmt`, `jm_collection`.  
Holdout (1): `hospital_reservation` — **frozen**; no form-fill rule changes to chase this score.

---

## 2. Reviewer procedure

Package location: `data/review/hospital_reservation/`

1. Read `reviewer_instructions.md`
2. Open `generated_mdsr.docx` / `generated_mddr.docx`
3. Cross-check `gold_fields_review.json` and `human_review_checklist.md`
4. Copy `review_result.template.json` → `review_result.json` and fill scores / decision
5. Run summary:
   ```powershell
   python -m document_ai.cli document-review-summary --case hospital_reservation
   ```
6. Only if recommended gate is `promote_to_human_approved`:
   ```powershell
   python -m document_ai.cli document-bootstrap-gold `
     --case data/cases/hospital_reservation `
     --split holdout `
     --approve
   ```

Optional dual review: store second file as `reviewers/R2.json` (same schema). Summary aggregates all results for agreement.

---

## 3. Rating scales

Each dimension is **integer 1–5** (Likert):

| Score | Meaning |
|------:|---------|
| 1 | Unusable / wrong domain |
| 2 | Major gaps |
| 3 | Borderline; needs revise |
| 4 | Acceptable with minor nits |
| 5 | Ready as independent gold |

Dimensions:

- `terminology_score`
- `requirement_correctness_score`
- `design_correctness_score`
- `traceability_score`
- `regulatory_appropriateness_score`

Document statuses: `pending` | `accept` | `accept_with_nits` | `revise` | `reject`  
Approval: `pending` | `approve` | `revise` | `reject`

---

## 4. Approval criteria

**Approve** when:

1. MDSR and MDDR status ∈ {`accept`, `accept_with_nits`}
2. Mean Likert ≥ 4.0
3. No blocking `required_changes`
4. Domain/regulation coherent with case facts

Otherwise **revise** or **reject** — do not run `--approve`.

---

## 5. Bias controls

| Risk | Control |
|------|---------|
| Author = only reviewer | Prefer external reviewer for holdout; disclose if author-reviewed |
| Tuning rules after seeing holdout | Freeze generation; document any later change as post-hoc |
| Self-gold inflation | Provisional bootstrap ≠ human-approved; report both labels |
| Checklist leading | Attention items are hints; decisions use full DOCX reading |
| Multiple testing on holdout | One primary approve decision; exploratory notes separated |

---

## 6. Provisional self-gold vs human-approved gold

| | Provisional | Human-approved |
|--|-------------|----------------|
| Source | Copied from system `output_*.docx` | Reviewer-approved (optionally lightly edited) DOCX + bootstrap `--approve` |
| Status field | `provisional` | `human_approved` |
| Use in paper | Tooling / pipeline smoke; **not** claimed as independent reference | Holdout Results / Gold quality claims |
| Auto scores | May equal system self-comparison | Compared against frozen approved gold thereafter |

---

## 7. Tables for paper Results

### Table A — Holdout automatic scores (pre-approval)

| Case | Split | Quality | Validation | Benchmark | Gold status |
|------|-------|--------:|-----------:|----------:|-------------|
| hospital_reservation | holdout | 95.3 | 93.3 | 94.3 | provisional |

### Table B — Human evaluation (fill after review)

| Reviewer | Mean (1–5) | Term. | Req | Design | Trace | Reg. | Decision |
|----------|-----------:|------:|----:|-------:|------:|-----:|----------|
| R1 |  |  |  |  |  |  |  |
| R2 _(optional)_ |  |  |  |  |  |  |  |
| **Agg.** |  |  |  |  |  |  |  |

### Table C — Issue accounting

| Case | #Issues | #Required changes | Gate |
|------|--------:|------------------:|------|
| hospital_reservation |  |  | promote / hold |

### Suggested Methods sentence

> We freeze `hospital_reservation` as a domain-shift holdout. Automatic harness scores are reported under provisional gold; human approval follows a fixed Likert checklist (terminology, requirements, design, traceability, regulation). Only after `approval_decision=approve` do we promote artifacts to `human_approved` gold via `document-bootstrap-gold --approve`, without further generation-rule tuning aimed at this case.

---

## 8. Metrics inventory (for reporting)

| Metric | Source |
|--------|--------|
| Harness holdout score | `harness-benchmark --holdout-only` |
| Mean human Likert | `human_evaluation_summary` |
| Approval rate | approve_count / n_reviewers |
| Issue / required-change counts | summary |
| Cohen's κ | reserved (`agreement.cohen_kappa`) when ≥2 reviewers |
