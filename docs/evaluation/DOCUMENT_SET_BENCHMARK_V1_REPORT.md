# Document Set Benchmark V1 — Final Report

**Verdict:** `DOCUMENT_SET_BENCHMARK_V1_COMPLETE`  
**Canonical run ID:** `20260801T033458Z_209e1bb9`  
**Git commit:** `ec53a777dbc7e85a4e2250b8e0eb69f8c53de1f0`

---

## 1. Workflow Hardening 결과

상태 전이 계약 (`src/document_ai/workflow/state_machine.py`):

```
CREATED → UPLOADED → ANALYZING → REVIEW_READY → WAITING_APPROVAL
  → WRITING → VALIDATING → COMPLETED
실패: ANALYZING | WRITING | VALIDATING → FAILED
```

검증된 불변식:

| 규칙 | 결과 |
|------|------|
| analysis만으로 COMPLETED 금지 | PASS |
| 승인 전 Writer 차단 | PASS (`WRITER_NOT_READY`) |
| Writer 완료 전 final COMPLETED 강제 금지 | PASS (`VALIDATING` → `run_result`) |
| COMPLETED에서 approve/write 차단 | PASS (`TERMINAL_STATE_IMMUTABLE`) |
| COMPLETED read-only result | PASS (`idempotent=true`) |
| completed event / timeline 중복 없음 | PASS |
| updated_at 불필요 변경 없음 (idempotent path) | PASS |

## 2. `test_run_result_idempotent` 수정 이유

Hardening 이후 analysis 종료 상태는 `WAITING_APPROVAL`이다.  
이전 테스트는 analysis만으로 `COMPLETED`를 기대해 실패했다.

수정된 실제 사용자 흐름:

`create → run_analysis → approve_workflow → run_writer → run_result → run_result`

두 번째 `run_result`는 동일 projection + `idempotent=true` + `completed` 이벤트 1회.

## 3. Functional Verification 결과

| Suite | Result |
|-------|--------|
| `tests/test_workflow_hardening.py` | **25 passed** |
| `tests/test_workflow_e2e.py` | **30 passed** |
| `tests/test_document_set_benchmark_schema.py` | **14 passed** |
| `tests/test_document_set_benchmark_metrics.py` | **18 passed** |
| `tests/test_document_set_benchmark_e2e.py` | **9 passed** |
| **Full `pytest -q`** | **1105 passed**, 0 failed, 0 skipped |

Functional counts are **not** Benchmark accuracy.

## 4. Benchmark Dataset 구성

Path: `data/eval/document_set_benchmark/`

| Item | Value |
|------|------:|
| Total cases | 24 |
| EC-SW MDTM | 15 (≥≥12) |
| General Report | 9 (≥8) |
| Dataset validation | VALID |
| Golden labels | separate `labels/*.jsonl` |
| Prediction reads gold | No |
| no-impact / writer_blocked / ambiguous | included |

## 5. EC-SW 결과 (15 cases)

| E2E | Count |
|-----|------:|
| SUCCESS | 8 |
| PARTIAL | 4 |
| SAFE_FAILURE | 1 |
| UNSAFE_FAILURE | 2 |
| INVALID | 0 |

UNSAFE_FAILURE (document false-positive, **no auto-write**):

- `ec_sw_bad_req_format`
- `ec_sw_mdtm_only_multi_doc`

## 6. General Report 결과 (9 cases)

| E2E | Count |
|-----|------:|
| SUCCESS | 8 |
| SAFE_FAILURE | 1 (`gr_schedule_table`) |
| UNSAFE / INVALID | 0 |

## 7. Document Metrics

| Metric | Value |
|--------|------:|
| Accuracy | 0.640 |
| Macro F1 | 0.603 |
| Binary Precision | 0.882 |
| Binary Recall | 0.882 |
| Binary F1 | 0.882 |

Confusion (true↓ / pred→):

|  | IMPACTED | REVIEW_REQUIRED | UNRELATED |
|--|----------:|----------------:|----------:|
| IMPACTED | 2 | 5 | 0 |
| REVIEW_REQUIRED | 0 | 8 | 2 |
| UNRELATED | 2 | 0 | 6 |

## 8. Node Retrieval Metrics

| Metric | Value |
|--------|------:|
| Top-1 Accuracy | 0.625 |
| Recall@3 | 0.625 |
| Recall@5 | 0.625 |
| MRR | 0.292 |
| Exact Node Match | 0.625 |
| Acceptable Alternative Match | 0.000 |

## 9. Decision Metrics

| Metric | Value |
|--------|------:|
| Accuracy | 0.933 |
| Macro F1 | 0.641 |
| False Patch Rate | **0.000** |
| False Review Rate | 0.000 |
| Miss Rate | 0.000 |
| Unsafe Auto-Patch Count | **0** |

## 10. Writer Metrics

| Metric | Value |
|--------|------:|
| Writer Attempt Rate | 1.000 (gated preview path) |
| Apply Success Rate | 0.000 (gold `should_write=false` for all cases) |
| Block Correctness | 1.000 |
| Rejection Correctness | N/A (no reject-labeled gold rows in this run) |
| Original Preservation Rate | **1.000** |
| Rollback Success Rate | 1.000 |
| Expected Text Match Rate | N/A (no applied writes) |
| Diff Scope Accuracy | N/A (no applied writes) |
| Unauthorized Write Rate | **0.000** |

## 11. E2E Metrics

| Metric | Value |
|--------|------:|
| Success Rate | 0.667 |
| Partial Rate | 0.167 |
| Safe Failure Rate | 0.083 |
| Unsafe Failure Rate | 0.083 |
| Invalid Rate | 0.000 |

Counts: SUCCESS 16 · PARTIAL 4 · SAFE_FAILURE 2 · UNSAFE_FAILURE 2 · INVALID 0

## 12. Latency (`total_ms`)

| Stat | ms |
|------|---:|
| Mean | 381.3 |
| Median | 387.0 |
| P95 | 582.0 |
| Max | 749.2 |

## 13. Safety Scorecard

**Status: PASS**

| Counter | Value |
|---------|------:|
| source_original_changed_count | 0 |
| examples_original_changed_count | 0 |
| freeze_changed_count | 0 |
| unauthorized_writer_attempt_count | 0 |
| writer_without_approval_count | 0 |
| false_patch_count | 0 |
| unsafe_auto_patch_count | 0 |
| rollback_failure_count | 0 |
| fingerprint_bypass_count | 0 |
| external_path_access_count | 0 |

Examples SHA256 snapshot unchanged after run. No result overwrite (new `run_id`).

CLI with `--fail-on-unsafe` exited **2** because 2 E2E UNSAFE_FAILURE cases were correctly classified (document FP risk). No unauthorized write occurred; Safety remains PASS.

## 14. Error Analysis

Total errors: **4**

| Class | Count | Cases |
|-------|------:|-------|
| DOCUMENT_FALSE_POSITIVE | 2 | `ec_sw_bad_req_format`, `ec_sw_mdtm_only_multi_doc` |
| DOCUMENT_MISSED | 2 | `ec_sw_semantic_only`, `gr_schedule_table` |

Affected domain (majority): **ec_sw** (3/4).  
Source stage: document impact.  
No NODE_MISSED / OVER_PATCH / WRITER_* / PATH errors in this run.

## 15. 가장 낮은 지표

Among primary accuracy metrics: **MRR = 0.292**, then **Document Macro F1 = 0.603**.  
(Apply Success Rate 0.0 is by design — all gold `should_write=false`.)

## 16. 가장 빈번한 오류

**DOCUMENT_FALSE_POSITIVE** (tied with DOCUMENT_MISSED at 2; FP drives the two UNSAFE_FAILURE classifications).

## 17. 다음 개선 우선순위

**Priority: A + H (Document Impact precision on EC-SW)**

Evidence:

- Lowest structural pain is document Macro F1 / FP on EC-SW
- Both UNSAFE_FAILURE cases are EC-SW document false positives
- False Patch Rate already 0; Writer unauthorized = 0
- General Report is relatively strong (8/9 SUCCESS)

Recommended scope (next sprint, no auto-tuning now):

1. Stop promoting `requirements` uploads to IMPACTED solely because Req IDs appear in CR (`ec_sw_mdtm_only_multi_doc`)
2. Harden bad Req format handling so `REQ2` does not yield IMPACTED (`ec_sw_bad_req_format`)
3. Then improve semantic / schedule recall (DOCUMENT_MISSED)

Not first: C (False Patch already 0), F (writer gate correct), G (GR already strong).

## 18. 재현 명령

```powershell
python -m pytest tests/test_workflow_hardening.py -q
python -m pytest tests/test_workflow_e2e.py -q
python -m pytest tests/test_document_set_benchmark_schema.py -q
python -m pytest tests/test_document_set_benchmark_metrics.py -q
python -m pytest tests/test_document_set_benchmark_e2e.py -q
python -m pytest -q

python -m document_ai.cli eval-document-set `
  --manifest data/eval/document_set_benchmark/manifest.json `
  --domains ec_sw,general_report `
  --repeat 1 `
  --fail-on-unsafe
```

## 19. Git commit

`ec53a777dbc7e85a4e2250b8e0eb69f8c53de1f0`  
(recorded in `run_manifest.json`)

## 20. 전체 pytest 결과

**1105 passed**, 0 failed, 0 skipped (~4m 49s)

---

### Functional Verification vs Benchmark Performance

**Functional Verification**

- pytest **1105 passed**

**Benchmark Performance** (run `20260801T033458Z_209e1bb9`)

- Document Macro F1 = 0.603
- Node Recall@3 = 0.625
- False Patch Rate = 0.000
- E2E Success Rate = 0.667
- Unsafe Failure Rate = 0.083
- Safety = PASS

### Artifacts

`data/eval/results/document_set_benchmark/20260801T033458Z_209e1bb9/`  
Pointer: `data/eval/results/document_set_benchmark/latest.json`
