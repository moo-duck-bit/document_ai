# Document Set Benchmark v1.3 — Node Grounding Calibration

**Verdict:** `READY_FOR_DOCUMENTSET_BENCHMARK_V1_3_RERUN`

| | v1.2 | v1.3 |
|--|------|------|
| Run ID | `20260801T041708Z_7a6edf9a` | `20260801T052854Z_1accfb51` |
| Focus | Safe document recall | Node evaluation eligibility + calibrated metrics |

Prior runs (`v1`, `v1.1`, `v1.2`) were **not** overwritten.

---

## 1. Why Node Metric Calibration Was Needed

v1.2 achieved Document Macro F1 **1.000** and E2E **1.000**, but Legacy Node Top-1 stayed at **0.625**.

Root cause was **label/metric definition**, not only retrieval:

- Cases with **empty node gold** (document-level REVIEW only) still entered the retrieval denominator.
- When safe-recall added legitimate REVIEW candidates, empty-gold + non-empty ranks scored as **miss**.
- Cases with **no node grounding expected** (no-impact) scored as **perfect** when both gold and preds were empty — inflating the same legacy average.

Calibration separates **evaluable grounding** from **document-only** and **unlabeled** cases.

## 2. Legacy Node Metric Limitation

Legacy metrics average all 24 cases with historical rules:

- Empty gold + empty preds → hit  
- Empty gold + any pred → miss  

So Legacy Top-1 mixes:

| Bucket | Effect on Legacy |
|--------|------------------|
| NOT_APPLICABLE empty | Inflates score |
| OPTIONAL with REVIEW nodes | Deflates score |
| REQUIRED ranking errors | Real misses |

Legacy remains for **run continuity only**.

## 3. Node Evaluation Eligibility

| Mode | Count | Strict Top-1? |
|------|------:|:-------------:|
| REQUIRED | 13 | Yes |
| OPTIONAL | 2 | No |
| AMBIGUOUS | 2 | Group metrics |
| NOT_APPLICABLE | 7 | No |
| UNLABELED | 0 | — |

Schema: `labels/node_evaluation_eligibility.jsonl`  
Audit: `docs/evaluation/DOCUMENT_SET_NODE_LABEL_AUDIT_V1_3.md`

## 4. Gold Label Audit

- Total 24 / `LABEL_COMPLETE` 24 / UNLABELED 0  
- Automatic gold mutation: **0**  
- Prediction-driven gold edits: **0**  
- Fixture-justified AMBIGUOUS gold: schedule section + duplicate results group  
- `ec_sw_semantic_only` kept **OPTIONAL** without inventing MDTM row gold  

## 5. Stable Node Reference

Match order (no free semantic similarity):

1. Exact node_id  
2. Stable locator (document / type / locator / section)  
3. Identifier match  
4. Text hash  
5. Acceptable group  

## 6. Required Metrics (n=13)

| Metric | Value |
|--------|------:|
| Required Node Top-1 | 0.385 |
| Required Recall@3 | **0.923** |
| Required Recall@5 | **0.923** |
| Required MRR | 0.641 |

Interpretation: gold is usually in top-3; **rank-1 competition** among nearby MDTM rows is the main gap (not empty-gold artifact).

## 7. Ambiguous Metrics (n=2)

| Metric | Value |
|--------|------:|
| Ambiguous Group Hit@1 | 0.000 |
| Ambiguous Group Recall@3 | 0.500 |
| Ambiguous Group Recall@5 | 1.000 |
| Group MRR | 0.267 |

Schedule heading nodes and paragraph duplicates often outrank template section ids at top-1.

## 8. Optional Grounding Metrics (n=2)

| Metric | Value |
|--------|------:|
| Optional Grounding Coverage | 0.500 |
| Specific Node Evidence Rate | 0.500 |
| Review Without Node Rate | 0.500 |

`ec_sw_semantic_only`: document REVIEW without forced node candidates (by design).  
`gr_semantic_similar`: has a node candidate (coverage credit).

## 9. Label Coverage

| Metric | Value |
|--------|------:|
| Node Label Coverage | **1.000** |
| Required Case Coverage | 0.542 |
| Unlabeled Case Count | **0** |
| Strict denominator | 13 |

## 10. Decision Metric Separation

| Metric | Level | Value | Denominator |
|--------|-------|------:|-------------|
| Document Decision Macro F1 | document status | **1.000** | document gold rows (n=25) |
| Node Decision Macro F1 | node status | **0.644** | cases **with node gold** (n=16) |
| Legacy “Decision Macro F1” | historically node-aligned | ~0.641–0.644 | same family as node |

**Important:** The long-standing ~0.641 figure is **Node Decision Macro F1**, not Document Decision. Document Decision is already 1.000 after v1.2. Empty-gold cases do **not** enter Node Decision pairs.

## 11. v1.2 vs v1.3

| Metric | v1.2 Legacy | v1.3 Legacy | v1.3 Calibrated |
|--------|------------:|------------:|----------------:|
| Node Top-1 | 0.625 | 0.625 | — |
| Recall@3 | 0.625 | 0.625 | — |
| Recall@5 | 0.625 | 0.625 | — |
| MRR | 0.292 | 0.314 | — |
| Required Node Top-1 | N/A | N/A | **0.385** |
| Required Recall@3 | N/A | N/A | **0.923** |
| Required Recall@5 | N/A | N/A | **0.923** |
| Required MRR | N/A | N/A | **0.641** |
| Ambiguous Group Hit@1 | N/A | N/A | 0.000 |
| Optional Grounding Coverage | N/A | N/A | 0.500 |
| Node Label Coverage | N/A | N/A | **1.000** |

Calibrated Recall@3 (**0.923**) ≫ Legacy Recall@3 (**0.625**) on the correct denominator.

## 12. Document / E2E Safety Regression

| Metric | v1.2 | v1.3 |
|--------|-----:|-----:|
| Document Macro F1 | 1.000 | **1.000** |
| E2E Success Rate | 1.000 | **1.000** |
| False Patch Rate | 0.000 | **0.000** |
| Unsafe Failure Rate | 0.000 | **0.000** |
| Original Preservation | 1.000 | **1.000** |
| EC-SW document success | 15/15 | **15/15** |
| General Report success | 9/9 | **9/9** |
| Semantic-only PATCH | 0 | **0** |
| Table-only PATCH | 0 | **0** |

## 13. Remaining Node Retrieval Errors

| Class | Count | Dominant cause |
|-------|------:|----------------|
| Required Top-1 miss (but ≤@3) | 7 | Adjacent MDTM row ranked higher |
| Required miss @3/@5 | 1 | `ec_sw_design_id_only` wrong row |
| Ambiguous Hit@1 miss | 2 | Heading/paragraph ids vs template section id |
| Optional ungrounded | 1 | semantic-only document-level REVIEW |

## 14. Dataset Limitations

- MDTM row gold is single-hash id; nearby rows share Req-family scores  
- GR fixture headings may not share the template `general_report_v1.*` node_id namespace  
- OPTIONAL cases intentionally lack unique row gold  

## 15. Next Improvement Priority

1. **Ranking** for exact-ID REQUIRED (prefer exact identifier match over neighbor rows) — not metric gaming  
2. Align GR schedule/heading predictions with stable section references / acceptable groups  
3. Keep OPTIONAL document-level REVIEW without forcing node gold  

---

## Functional vs Benchmark

**Functional Verification:** pytest **1232 passed** (includes ≥35 new calibration tests)

**Benchmark Performance (v1.3):** Document Macro F1 **1.000** · E2E **1.000** · False Patch **0** · Unsafe **0** · Label Coverage **1.000** · Required Recall@3 **0.923**
