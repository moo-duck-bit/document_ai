# Independent Gold Dataset Design

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


**Document type:** Dataset / Evaluation design (research-ready)  
**Version:** 1.0  
**Date:** 2026-07-14  
**Scope:** EC-SW Document Harness (MDSR / MDDR; XXCS reserved)

---

## 1. Motivation

Prior validation used **proxy gold**: `jm_collection/output_*.docx` compared against itself or against sibling cases. That inflates structural agreement and conflates *authoring baseline* with *independent reference*.

This design separates:

| Artifact | Role |
|----------|------|
| **Generated output** | System under test (`data/cases/*/output_*.docx`) |
| **Independent gold** | Human-curated or explicitly approved references (`data/gold/`) |
| **gold_fields** | Structured semantic labels for ID/text/traceability checks |

Proxy gold remains a migration fallback only.

---

## 2. Directory layout

```
data/gold/
├── case_manifest.json          # registry: case_id, split, status, paths
├── mdsr/{case_id}.docx         # gold MDSR
├── mddr/{case_id}.docx         # gold MDDR
├── xxcs/{case_id}.docx         # reserved for security report gold
└── fields/{case_id}.gold_fields.json
```

### 2.1 `case_manifest.json` schema

```json
{
  "version": "1.0",
  "cases": [
    {
      "case_id": "hospital_reservation",
      "split": "holdout",
      "domain": "hospital_reservation",
      "product_name": "Hospital Reservation System",
      "status": "provisional",
      "case_dir": "data/cases/hospital_reservation",
      "gold_mdsr": "mdsr/hospital_reservation.docx",
      "gold_mddr": "mddr/hospital_reservation.docx",
      "gold_fields": "fields/hospital_reservation.gold_fields.json",
      "notes": "..."
    }
  ]
}
```

**status values**

| status | Meaning |
|--------|---------|
| `provisional` | Bootstrapped from system output; **not** publication-grade |
| `human_approved` | Reviewer signed off via checklist |
| `revised` | Gold corrected after disagreement |

**split values:** `train` | `holdout`

---

## 3. `gold_fields.json` schema

Structured labels extracted (and optionally edited) from gold DOCX:

```json
{
  "version": "1.0",
  "case_id": "lab_ec_sw",
  "product_name": "JM COLLECTION",
  "domain": "ecommerce_b2c",
  "source": "case_output_bootstrap",
  "approval_status": "provisional",
  "section_titles": ["1. Introduction", "..."],
  "requirement_ids": ["Req. 1", "Req. 2"],
  "requirements": [
    {"req_id": "Req. 1", "requirement_text": "..."}
  ],
  "design_ids": ["Req. 1"],
  "design_items": [
    {"design_id": "Req. 1", "req_id": "Req. 1", "design_text": "...", "block_kind": "paragraph"}
  ],
  "linked_reqs": [
    {"requirement": "IA-01 ...", "linked_reqs": "Req. 2, Req. 3"}
  ],
  "traceability_rows": [
    {"requirement": "IA-01 ...", "linked_reqs": "Req. 2, Req. 3"}
  ]
}
```

Fields support paper metrics:

- Requirement / design **ID coverage** (exact set intersection after normalization)
- Requirement / design **text similarity** (token Jaccard / existing comparator)
- Traceability row **key coverage**
- Product name consistency
- Section title coverage

---

## 4. Construction protocol

### 4.1 Bootstrap (machine)

```powershell
python -m document_ai.cli document-bootstrap-gold --case data/cases/lab_ec_sw --split train
python -m document_ai.cli document-bootstrap-gold --case data/cases/hospital_reservation --split holdout
```

Copies `output_*.docx` → `data/gold/{mdsr,mddr}/` and builds `gold_fields.json`.  
Default status: **provisional**.

### 4.2 Human approval

1. Run `document-validate` → produces `human_review_checklist.md`
2. Reviewer completes figure / table / terminology / regulation / traceability checks
3. Re-bootstrap with `--approve` **or** edit `case_manifest.json` status to `human_approved`
4. Optionally edit `gold_fields.json` for label corrections without re-copying DOCX

### 4.3 Independence rules (for papers)

1. Holdout gold must not be tuned after seeing final system scores on that case.
2. Train gold may be used to develop rules / schemas / extractors.
3. Provisional self-gold (output == gold) is allowed only for tooling smoke tests; **report separately**.
4. Disclose approval status and annotator count in the paper.

---

## 5. Resolution order in validation

When resolving gold DOCX for a case:

1. Explicit CLI `--gold-mdsr` / `--gold-mddr`
2. Independent dataset `data/gold/`
3. Case-local `gold_*.docx`
4. Manifest `gold` / `gold_fallback` (legacy proxy)

Semantic validation additionally loads `data/gold/fields/{case_id}.gold_fields.json` when present.

---

## 6. Initial registry (2026-07-14)

| case_id | split | status | Notes |
|---------|-------|--------|-------|
| lab_ec_sw | train | provisional | Real lab EC-SW; bootstrapped |
| inventory_mgmt | train | provisional | Harness dummy |
| jm_collection | train | provisional | Authoring reference |
| hospital_reservation | holdout | provisional | Domain-shift holdout |

XXCS gold slots are empty until Phase-XXCS sprint.

---

## 7. Metrics enabled by this dataset

| Metric | Source |
|--------|--------|
| DOCX structural validation | gold DOCX vs generated |
| Design block coverage (Req-ID) | extract + match |
| Semantic ID / text / traceability | gold_fields |
| Blended overall | \(0.85 \times\) DOCX \(+\) \(0.15 \times\) semantic |
| Human review agreement | checklist + future κ (annotator study) |
| Holdout benchmark score | `--holdout-only` |

---

## 8. Limitations

- Current gold files are **provisional self-copies** until human approval.
- Section heading extractor may under-report non-numeric titles.
- XXCS not populated.
- Single-annotator approval is a threat to validity; plan dual review for camera-ready experiments.
