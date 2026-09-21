# Document Set Benchmark v1 → v1.1 Comparison

**Verdict target:** `READY_FOR_DOCUMENTSET_BENCHMARK_V1_1_RERUN`

| | v1 | v1.1 |
|--|----|------|
| Run ID | `20260801T033458Z_209e1bb9` | `20260801T035304Z_298421a1` |
| CLI `--fail-on-unsafe` | exit 2 | **exit 0** |
| v1 directory | immutable (kept) | not overwritten |

## Metric comparison

| Metric | v1 | v1.1 | Delta |
|--------|----:|----:|------:|
| Document Macro F1 | 0.603 | **0.926** | **+0.323** |
| Node Top-1 | 0.625 | 0.667 | +0.042 |
| Node Recall@3 | 0.625 | 0.667 | +0.042 |
| MRR | 0.292 | 0.292 | 0.000 |
| Decision Macro F1 | 0.641 | 0.641 | 0.000 |
| False Patch Rate | 0.000 | **0.000** | 0.000 |
| E2E Success Rate | 0.667 | **0.917** | **+0.250** |
| Partial Rate | 0.167 | 0.000 | −0.167 |
| Unsafe Failure Rate | 0.083 | **0.000** | **−0.083** |
| Original Preservation | 1.000 | **1.000** | 0.000 |

## Domain breakdown

### EC-SW (15)

| Status | v1 | v1.1 |
|--------|---:|-----:|
| SUCCESS | 8 | **14** |
| PARTIAL | 4 | 0 |
| SAFE_FAILURE | 1 | 1 |
| UNSAFE_FAILURE | **2** | **0** |

UNSAFE fixed (generalized policy, not case-id):

- malformed Req (REQ2) → no longer exact / IMPACTED
- MDTM-only multi-doc → sibling `requirements` role no longer IMPACTED

Remaining SAFE_FAILURE: `ec_sw_semantic_only` (DOCUMENT_MISSED — expected gap)

### General Report (9)

| Status | v1 | v1.1 |
|--------|---:|-----:|
| SUCCESS | 8 | 8 |
| SAFE_FAILURE | 1 | 1 |
| UNSAFE / INVALID | 0 | 0 |

No GR regression. Remaining: `gr_schedule_table` DOCUMENT_MISSED.

## Success criteria check

| Criterion | Result |
|-----------|--------|
| UNSAFE 2건 원인 수정 | PASS (0 UNSAFE) |
| role-only IMPACTED 0 | PASS |
| malformed not exact | PASS |
| Document Macro F1 개선 | PASS (0.603 → 0.926) |
| Unsafe Failure Rate 감소 | PASS (0.083 → 0.000) |
| False Patch = 0 | PASS |
| Unsafe Auto Patch = 0 | PASS |
| Original Preservation = 1.0 | PASS |
| GR 저하 없음 | PASS |
| pytest | **1141 passed** |
| v1 immutable + new run | PASS |

권장 목표: Unsafe=0 ✓ · E2E≥0.75 ✓ · Document Macro F1≥0.70 ✓

## Root causes addressed

1. **Role-only promotion** — removed `requirements`/`design` + reqs → IMPACTED in `analyze_ec_sw`
2. **Malformed Req** — `REQ2` no longer matches `Req\.?\s*(\d+)`; parser statuses VALID_* vs MALFORMED
3. **Multi-doc propagation** — evidence scoped per `document_id`; set membership / role alone → UNRELATED

## What did not change

- PATCH node thresholds / Controlled Writer / Approval / Rollback
- General Report pack logic
- Benchmark case-id hardcoding (forbidden)
- v1 result directory

## Remaining errors (2)

| Class | Count | Cases |
|-------|------:|-------|
| DOCUMENT_MISSED | 2 | `ec_sw_semantic_only`, `gr_schedule_table` |

Next improvement cycle (not this change): semantic / schedule section recall — not False Patch.

## Functional vs Benchmark

**Functional Verification:** pytest **1141 passed** (0 failed)

**Benchmark Performance (v1.1):** Document Macro F1 **0.926** · E2E **0.917** · False Patch **0.000** · Unsafe **0.000**

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

- Diagnosis: `docs/evaluation/EC_SW_DOCUMENT_IMPACT_ERROR_DIAGNOSIS.md`
- This comparison: `docs/evaluation/DOCUMENT_SET_BENCHMARK_V1_1_COMPARISON.md`
- New run: `data/eval/results/document_set_benchmark/20260801T035304Z_298421a1/`
