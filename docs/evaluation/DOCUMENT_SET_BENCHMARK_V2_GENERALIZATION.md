# Document Set Benchmark V2 — Generalization, Robustness, Blind Holdout

**Verdict:** `READY_FOR_DOCUMENTSET_BENCHMARK_V2_GENERALIZATION`

| | Value |
|--|------|
| Run ID | `20260801T062321Z_c70af996` |
| Protocol | UNSEALED (seal → freeze → unseal OK) |
| pytest | **1329 passed** |

v1–v1.4 runs and the Regression 24-case tree were **not** modified.

## 1. Objective

Measure generalization beyond the frozen v1.4 24-case set via Development Extension, Blind Holdout, metamorphic robustness, and domain breakdown — **without** tuning thresholds on the new results in this cycle.

## 2. Why New Holdout Was Required

v1.4 Required/Ambiguous metrics reached 1.000 on 24 cases. Further ranking tweaks on that set risk overfitting. V2 separates regression from sealed holdout evaluation.

## 3. Split

| Split | Count | Role |
|-------|------:|------|
| Regression | 24 | Immutable v1 reference |
| Development | 31 | Extension / error analysis |
| Holdout | 20 | Blind sealed labels |

## 4. Dataset Sources

- `GENERATED` MDTM-like / report / proposal DOCX fixtures under `data/eval/document_set_benchmark_v2/fixtures/`
- Labels authored from fixture structure + CR intent **before** prediction
- Holdout labels in `holdout/sealed_labels/` with hash manifest

## 5. Holdout Protocol

1. Seal labels + hashes  
2. Run predictions **without** loading sealed gold  
3. Freeze `holdout_predictions.jsonl`  
4. Unseal + evaluate  

`evaluation_unseal_log.json`: `protocol_ok=true`, `status=UNSEALED`.  
`gold_read_during_inference=false`.

## 6. Domain Distribution (dev+holdout new cases)

EC-SW ≥20, General Report ≥12, Business Proposal ≥8 (generator counts).

## 7. Robustness Transformations

Metamorphic pairs cover identifier format, whitespace, file order, schedule structure variants.

## 8. Regression Metrics

| Metric | Value |
|--------|------:|
| Document Macro F1 | **1.000** |
| Required Node Top-1 | **1.000** |
| Required Recall@3 | **1.000** |
| E2E Success | **1.000** |
| False Patch | **0.000** |
| Unsafe Failure | **0.000** |

## 9. Development Metrics

| Metric | Value |
|--------|------:|
| Document Macro F1 | 0.353 |
| Required Node Top-1 | 0.250 |
| Required Recall@3 | 0.250 |
| E2E Success | 0.516 |
| False Patch | **0.000** |
| Unsafe Failure | 0.065 (2/31) |

## 10. Blind Holdout Metrics

| Metric | Value |
|--------|------:|
| Document Macro F1 | 0.416 |
| Required Node Top-1 | 0.300 |
| Required Recall@3 | 0.300 |
| Required MRR | 0.300 |
| Decision Macro F1 (node) | 0.296 |
| E2E Success | 0.550 |
| False Patch | **0.000** |
| Unsafe Failure | 0.050 (1/20) |

## 11. Domain Metrics (all evaluated cases in run)

| Domain | E2E Success | Doc hit | Unsafe |
|--------|------------:|--------:|-------:|
| EC-SW | 0.462 | 0.462 | 0.000 |
| General Report | 0.875 | 0.875 | 0.125 |
| Business Proposal | 1.000 | 1.000 | 0.000 |

## 12. Generalization Gap (dev − holdout)

| Gap | Value |
|-----|------:|
| Document F1 | −0.063 |
| Node Top-1 | −0.050 |
| Recall@3 | −0.050 |
| E2E Success | −0.034 |

Holdout is slightly **higher** than development on several metrics → gap is small; both sit well below regression (expected for new fixtures / first BP domain).

## 13. Calibration

Scores are **not** probabilities (`score_is_probability=false`). High-confidence error count (proxy bins): 15.

## 14. Formatting Preservation

Writer gated (`should_write=false`) → N/A aggregate (`n_applicable=0`).

## 15. Safety Stress Tests

Original/examples/freeze unchanged; unauthorized writer 0; unsafe auto patch 0; stress suite pass_rate 1.0.

## 16. Human Review Protocol

Forms: `data/eval/document_set_benchmark_v2/human_review/` (separate from automatic metrics).

## 17. Error Analysis

- **Major bottleneck:** EC-SW generated fixtures — upload `document_id` / table indexing vs gold IMPACTED+REQUIRED expectations; many exact-ID CRs predicted UNRELATED/SAFE_FAILURE.
- **Most affected domain:** EC-SW (doc hit ~0.46 on mixed splits).
- **False Patch:** 0 across splits.
- **Unsafe:** few GR e2e UNSAFE classifications on new sets (investigate in next cycle; do not case-id patch here).

## 18. Dataset Limitations

- Fixtures are GENERATED, not SANITIZED_REAL pilot docs yet.
- Business Proposal labeled OPTIONAL / document REVIEW only.
- Table-structure metamorphic pair coverage thin (`table_structure_robustness` 0.0 denominator/empty filter).

## 19. Reproduction

```powershell
python scripts/generate_document_set_benchmark_v2.py  # if regenerating (reseals holdout)
python -m pytest -q
python -m document_ai.cli eval-document-set-v2 `
  --manifest data/eval/document_set_benchmark_v2/manifest.json `
  --split regression,development,holdout `
  --domains ec_sw,general_report,business_proposal `
  --fail-on-unsafe `
  --fail-on-protocol-violation
```

Exit 2 on this run = unsafe failures present on **non-regression** splits (reported, not patched).

## 20. Next Priority

1. Align EC-SW upload document_id / MDTM indexing with label document_id  
2. Add SANITIZED_REAL pilot documents under sealed holdout  
3. Investigate GR UNSAFE_FAILURE e2e classifications  
4. Expand table-structure metamorphic pairs  
5. Optional: Writer format-preservation runs on gated copy path only  

**Do not** raise v2 scores via case-id exceptions or holdout gold edits from predictions.
