# MDDR Quality Improvement Report

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


**Date:** 2026-07-14  
**Branch:** `feature/ai-engineering-platform`  
**Scope:** MDDR extract / match / render consistency only (Platform Runtime untouched)

---

## 1. Problem

`lab_ec_sw` MDDR validation was **75.3** with design block coverage **5.3%**, despite gold and generated sharing the same 38 Req IDs (count match 1.0, text similarity 1.0).

Diagnosis: [`docs/mddr_validation_diagnosis.md`](mddr_validation_diagnosis.md)

**Root cause:** Mindrium-style blocks store design body in one paragraph as `Req. N\n<body>`. The extractor’s `\s*` consumed the newline and put the body into `title_suffix`, while coverage only counted non-empty `design_description` → 2/38 ≈ 5.3%.

Secondary: section-prefixed headings (`4.2.1 Req. 1`) unsupported; coverage was content-fill, not Req-ID match.

---

## 2. Modules changed

| Module | Change |
|--------|--------|
| `src/document_ai/learn/extract_design_items.py` | First-line / body split; section prefixes; table + paragraph; unified `_design_text_from_item`; deep text |
| `src/document_ai/validation/runner.py` | Req-ID primary coverage; similarity on unified design text |
| `src/document_ai/render/design_items.py` | Shared heading parser; duplicate insert guard; Mindrium one-paragraph shape |
| `src/document_ai/render/mddr.py` | Completeness check uses same heading/body parsing |
| `tests/test_mddr_design_quality.py` | Extraction, matching, duplicate, lab targets, force-generate |
| `docs/mddr_validation_diagnosis.md` | Pre-fix diagnosis |

**Not modified:** Platform Runtime / Planner / Memory / Impact Pipeline.

---

## 3. Before / After — MDDR & coverage (`lab_ec_sw`)

| Metric | Before | After | Target |
|--------|-------:|------:|--------|
| MDDR validation score | 75.3 | **92.0** | ≥ 85 |
| Design block coverage | 5.3% | **100%** | ≥ 50% |
| Content fill rate | ~5.3% | **100%** | — |
| Matched Req IDs | 38/38 | 38/38 | — |
| Validation overall | 87.5 | **95.9** | — |
| MDSR validation | 99.8 | 99.8 | — |

Coverage is now **gold Req IDs present in generated** (section numbers ignored). Content fill rate is reported separately.

---

## 4. force-generate

| Mode | Quality overall | Consistency | Validation overall | Status |
|------|----------------:|------------:|-------------------:|:------:|
| Before (historical) | 70.0 FAIL | 0.0 | 87.5 | FAIL |
| After `--force-generate` | **96.8 PASS** | 100.0 | **95.9** | **PASS** |

Observations:

- Brand tokens (`JM-web` / `JM-api` / `JM-admin`) allowed via `product_code` in quality analyzer (prior fix).
- Render starts from empty template each generate → no stale DOCX merge.
- Duplicate Req insert blocked when heading already exists.
- residual_text remains **84.0** (placeholder / figure tokens) — expected, not blocking PASS.

---

## 5. Benchmark (reproducible)

```powershell
python -m document_ai.cli project-validate --case data/cases/lab_ec_sw --force-generate
python -m document_ai.cli harness-benchmark
python -m pytest -q
```

| Case | Quality | Validation | Benchmark score | Status |
|------|--------:|-----------:|----------------:|:------:|
| lab_ec_sw | 96.8 | 95.9 | 96.3 | PASS |
| inventory_mgmt | 96.8 | — | 96.8 | PASS |
| hospital_reservation | 95.3 | — | 95.3 | PASS |
| jm_collection | 96.8 | 96.0 | 96.4 | PASS |

**Harness benchmark overall: 96.2** (was 94.1) — 4 passed / 0 failed.

**Tests: 237 passed** (was 229; +8 MDDR quality tests).

---

## 6. Human review remaining

- [ ] Residual `XX-XX-XXXX` / figure·table placeholders (residual_text 84)
- [ ] MDDR narrative beyond per-Req blocks (overview diagrams still placeholder captions)
- [ ] Independent human-reviewed gold for `lab_ec_sw` (still uses `jm_collection` proxy)
- [ ] Spot-check free_text design prose for domain terminology on non-ecommerce cases
- [ ] XXCS design/test linkage not yet in this validation loop

---

## 7. Reuse for XXCS later

Patterns that transfer:

1. **ID-first coverage** — match `IA-` / `UC-` / `SI-` by normalized ID; section numbers ignored.
2. **Unified body text** — heading suffix + cell fields + following paragraphs → one design/test string for similarity.
3. **Duplicate-safe patch** — never insert a second block when ID already present in DOCX.
4. **One-paragraph Mindrium shape** — `ID\nbody` must round-trip through extractor and renderer with the same parser (`_parse_req_heading`).

Suggested XXCS next step: share `_parse_req_heading`-style helpers under `document_ai.learn` for security test IDs, then reuse `_compare_design_blocks` skeleton as `_compare_test_blocks`.

---

## 8. Recommended next Sprint priority

1. **Independent Gold** — highest leverage for credible research numbers (remove jm_collection proxy bias).
2. **XXCS** — reuse ID-first coverage after gold exists.
3. **Retrieval 고도화** — valuable for free_text, lower urgency now that structural MDDR scoring is healthy.
