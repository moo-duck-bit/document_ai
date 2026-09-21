# Human Evaluation Protocol

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


**Document type:** Evaluation protocol (research-ready)  
**Version:** 1.0  
**Date:** 2026-07-14  
**Companion:** [`gold_dataset_design.md`](gold_dataset_design.md)

---

## 1. Purpose

Define how humans evaluate Document Harness outputs for gold approval and paper reporting. Complements automatic DOCX + `gold_fields` validation.

---

## 2. Roles

| Role | Responsibility |
|------|----------------|
| **Operator** | Run generate / validate / bootstrap CLI |
| **Reviewer** | Complete `human_review_checklist.md` |
| **Adjudicator** (optional) | Resolve reviewer disagreements |
| **Maintainer** | Update `case_manifest.json` status |

For a thesis / short paper: ≥1 reviewer. For camera-ready: ≥2 independent reviewers on holdout.

---

## 3. Materials per case

1. `output_mdsr.docx`, `output_mddr.docx` (generated)
2. Gold DOCX under `data/gold/mdsr|mddr/` (or candidate bootstrap)
3. `gold_fields.json`
4. Auto reports:
   - `quality_report.md`
   - `validation_report.md` / `.json`
   - `human_review_checklist.md` ← **primary human form**

---

## 4. Checklist dimensions

Generated checklist always includes:

| Category | Question |
|----------|----------|
| **figure** | Are diagrams/captions correct or acceptably placeholder? |
| **table** | Req / design / traceability tables complete? |
| **terminology** | Domain-consistent product/service terms? |
| **regulation** | Standards (e.g. PCI, OWASP, PIPA) match case facts? |
| **traceability** | IA/UC/SI linked_reqs align with MDSR Req IDs? |
| **product_name** | Cover / overview / tables consistent? |
| **placeholders** | No blocking `XX-XX-XXXX` / empty critical cells? |

Attention items are auto-appended from validation (scores &lt; 85, residuals, missing IDs, high-risk diffs).

---

## 5. Procedure

### Step A — Generate (unchanged system)

```powershell
python -m document_ai.cli project-validate --case data/cases/{case_id} --skip-generate
# or --force-generate when regeneration is required
```

### Step B — Review

1. Open `{case}/human_review_checklist.md`
2. Tick each `[ ]` item; note defects in a short comment block
3. Decide one of:
   - **Approve as gold** — outputs acceptable as independent reference
   - **Revise generation** — system bug / incomplete fill
   - **Revise gold_fields** — labels wrong but DOCX OK

### Step C — Commit gold

```powershell
python -m document_ai.cli document-bootstrap-gold `
  --case data/cases/{case_id} `
  --split train|holdout `
  --approve
```

`--approve` sets `human_approved`. Without it, status stays `provisional`.

### Step D — Freeze holdout

After holdout approval, **do not** tune form-fill rules solely to improve holdout scores without documenting the change as a post-hoc experiment.

---

## 6. Scoring for papers

### 6.1 Automatic (always reported)

- Quality overall (6 dimensions)
- Validation overall (DOCX)
- Semantic overall (`gold_fields`)
- Design block coverage
- Holdout vs train harness benchmark

```powershell
python -m document_ai.cli harness-benchmark
python -m document_ai.cli harness-benchmark --holdout-only
```

### 6.2 Human (recommended table)

| Case | Split | Reviewer | Approve? | Critical defects | Time (min) |
|------|-------|----------|----------|------------------|------------:|
| … | holdout | R1 | Y/N | … | … |

Optional agreement: Cohen’s κ on approve/reject across reviewers.

### 6.3 Threats to validity

| Threat | Mitigation |
|--------|----------|
| Self-gold inflation | Mark provisional; report holdout only for claims |
| Reviewer bias (author = reviewer) | External reviewer for holdout |
| Overfitting to proxy jm_collection | Independent gold resolution order |
| Checklist fatigue | Cap attention items; focus high-risk diffs |

---

## 7. Pass criteria (suggested defaults)

| Gate | Criterion |
|------|-----------|
| Auto quality | overall ≥ 85 |
| Auto validation | overall ≥ 70 (DOCX); ≥ 85 preferred for paper claims |
| Semantic | requirement + design ID coverage ≥ 0.90 |
| Human | checklist approve + no unresolved critical terminology/traceability item |

---

## 8. Reporting template (paper Methods)

> We maintain an independent gold set under `data/gold/` with train/holdout splits registered in `case_manifest.json`. Each case provides gold MDSR/MDDR DOCX and structured `gold_fields` (requirement IDs, design IDs, traceability rows). Systems are scored with (i) DOCX structural validation, (ii) semantic field coverage against `gold_fields`, and (iii) human review using a fixed checklist (figures, tables, terminology, regulation, traceability). Holdout scores are computed with `harness-benchmark --holdout-only` without further rule tuning.

---

## 9. Tooling map

| CLI | Role |
|-----|------|
| `document-validate` | DOCX + semantic + writes checklist |
| `document-bootstrap-gold` | Promote outputs → gold dataset |
| `harness-benchmark [--holdout-only]` | Aggregate / holdout scores |
| `project-validate` | E2E harness → quality → validation |
