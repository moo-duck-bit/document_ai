# Document Set Benchmark v1 → v1.1 → v1.2 Comparison

**Verdict:** `READY_FOR_DOCUMENTSET_BENCHMARK_V1_2_RERUN`

| | v1 | v1.1 | v1.2 |
|--|----|------|------|
| Run ID | `20260801T033458Z_209e1bb9` | `20260801T035304Z_298421a1` | `20260801T041708Z_7a6edf9a` |
| `--fail-on-unsafe` | exit 2 | exit 0 | **exit 0** |

Prior runs were **not** overwritten.

## Metric comparison

| Metric | v1 | v1.1 | v1.2 | Δ v1.1→v1.2 |
|--------|---:|-----:|-----:|-------------:|
| Document Macro F1 | 0.603 | 0.926 | **1.000** | **+0.074** |
| Node Top-1 | 0.625 | 0.667 | 0.625 | −0.042 |
| Node Recall@3 | 0.625 | 0.667 | 0.625 | −0.042 |
| Node Recall@5 | 0.625 | 0.667 | 0.625 | −0.042 |
| MRR | 0.292 | 0.292 | 0.292 | 0.000 |
| Decision Macro F1 | 0.641 | 0.641 | 0.641 | 0.000 |
| False Patch Rate | 0.000 | 0.000 | **0.000** | 0.000 |
| E2E Success Rate | 0.667 | 0.917 | **1.000** | **+0.083** |
| Partial Rate | 0.167 | 0.000 | **0.000** | 0.000 |
| Safe Failure Rate | 0.083 | 0.083 | **0.000** | **−0.083** |
| Unsafe Failure Rate | 0.083 | 0.000 | **0.000** | 0.000 |
| Original Preservation | 1.000 | 1.000 | **1.000** | 0.000 |

### Note on Node Top-1

Former SAFE_FAILURE cases have **empty node gold**. Schedule REVIEW now emits legitimate REVIEW node candidates → retrieval treats “empty gold + non-empty ranked” as miss (−1/24 ≈ −0.042).  
Document-level REVIEW still yields **E2E SUCCESS**. Safety and False Patch unchanged. Node gold enrichment is a future labeling task (not score gaming).

## Domain breakdown

### EC-SW (15)

| Status | v1.1 | v1.2 |
|--------|-----:|-----:|
| SUCCESS | 14 | **15** |
| SAFE_FAILURE | 1 | **0** |
| UNSAFE_FAILURE | 0 | 0 |

### General Report (9)

| Status | v1.1 | v1.2 |
|--------|-----:|-----:|
| SUCCESS | 8 | **9** |
| SAFE_FAILURE | 1 | **0** |

## What changed

| Area | Change |
|------|--------|
| EC-SW semantic | Domain-concept REVIEW evidence; `supports_patch=false`; document REVIEW_REQUIRED |
| Concept normalization | SCHEDULE/TABLE/MILESTONE/… synonyms |
| GR schedule/table | Heading/table/time-unit retrieval + schedule section on `general_report_v1` |
| PATCH / Writer | Unchanged gates |

## Success criteria

| Criterion | Result |
|-----------|--------|
| semantic-only left DOCUMENT_MISSED | **PASS** (SUCCESS) |
| schedule/table left DOCUMENT_MISSED | **PASS** (SUCCESS) |
| semantic-only PATCH 0 | PASS |
| table-only PATCH 0 | PASS |
| False Patch 0 | PASS |
| Unsafe 0 | PASS |
| Original Preservation 1.0 | PASS |
| pytest | **1175 passed** |
| Prior runs immutable | PASS |

권장 목표: E2E=1.0 ✓ · Document Macro F1≥0.95 ✓ · DOCUMENT_MISSED=0 ✓ · Node Recall@3≥0.75 (미달, 원인 상단 설명)

## Functional vs Benchmark

**Functional Verification:** pytest **1175 passed**

**Benchmark Performance (v1.2):** Document Macro F1 **1.000** · E2E **1.000** · False Patch **0.000** · Unsafe **0.000**

## Reproduce

```powershell
python -m pytest -q
python -m document_ai.cli eval-document-set `
  --manifest data/eval/document_set_benchmark/manifest.json `
  --domains ec_sw,general_report `
  --repeat 1 `
  --fail-on-unsafe
```

## Artifacts

- Root cause: `docs/evaluation/SAFE_RECALL_V1_2_ROOT_CAUSE_ANALYSIS.md`
- This report: `docs/evaluation/DOCUMENT_SET_BENCHMARK_V1_2_COMPARISON.md`
- Run: `data/eval/results/document_set_benchmark/20260801T041708Z_7a6edf9a/`
