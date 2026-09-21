# Document Set Benchmark v1.4 — Node Ranking Precision

**Verdict:** `READY_FOR_DOCUMENTSET_BENCHMARK_V1_4_RERUN`

| | v1.3 | v1.4 |
|--|------|------|
| Run ID | `20260801T052854Z_1accfb51` | `20260801T055229Z_b4532405` |
| Focus | Eligibility calibration | Exact-ID ranking + structural alignment |

Prior runs (`v1`–`v1.3`) were **not** overwritten.

## Root cause (summary)

See `NODE_RANKING_V1_4_ROOT_CAUSE_ANALYSIS.md`.

1. **Neighbor-row ranking:** Exact PATCH rows scored via lexical `overlap` (~0.22); weak REVIEW neighbors (~0.25) ranked higher.
2. **Identifier type weighting:** Design/test IDs from CR were not fed into MDTM change POC; design-only fell back to wrong adjacent row.
3. **Template/document alignment:** Heading/paragraph ids vs template section ids had no evaluation equivalence bridge; schedule heading outscored template section (0.7).

## Changes

| Area | Change |
|------|--------|
| Query intent | `domain_packs/ec_sw/query_intent.py` — REQUIREMENT/DESIGN/TEST/MIXED/NONE |
| Match matrix | Row-local exact matches; LOCAL_CELL only for exact |
| Rank tiers | TIER_1…5; primary exact ≫ semantic; `final_score` |
| Neighbor handling | evidence_scope + neighbor_penalty; origins on identifiers |
| Node alignment | `template/node_alignment.py` — HEADING/PARAGRAPH/TABLE ↔ section |
| Structural groups | evaluation vs patch equivalence separated; group Hit expands |
| Adapter | Prefers `metadata.final_score` over raw overlap |

## Benchmark comparison

| Metric | v1.3 | v1.4 | Delta |
|--------|-----:|-----:|------:|
| Required Node Top-1 | 0.385 | **1.000** | **+0.615** |
| Required Recall@3 | 0.923 | **1.000** | **+0.077** |
| Required Recall@5 | 0.923 | **1.000** | **+0.077** |
| Required MRR | 0.641 | **1.000** | **+0.359** |
| Ambiguous Group Hit@1 | 0.000 | **1.000** | **+1.000** |
| Optional Grounding Coverage | 0.500 | 0.500 | 0.000 |
| Node Label Coverage | 1.000 | 1.000 | 0.000 |
| Node Decision Macro F1 | 0.644 | **0.667** | **+0.023** |
| Document Macro F1 | 1.000 | **1.000** | 0.000 |
| E2E Success Rate | 1.000 | **1.000** | 0.000 |
| False Patch Rate | 0.000 | **0.000** | 0.000 |
| Unsafe Failure Rate | 0.000 | **0.000** | 0.000 |
| Original Preservation | 1.000 | **1.000** | 0.000 |

### Domain notes

- EC-SW Required Top-1 / Recall@3 / MRR: **1.000** (incl. `ec_sw_design_id_only` @1)
- General Report Ambiguous Group Hit@1: **1.000** (schedule + duplicate heading)
- Optional Grounding: **0.500** (semantic-only remains document-level by design)

## Safety / regression

| Check | Result |
|-------|--------|
| pytest | **1277 passed** |
| Writer scope | unchanged |
| Gold read during inference | false |
| Case-id hardcode in ranking modules | none |
| Semantic-only / table-only PATCH | 0 |
| Desktop / examples / Freeze | unchanged |

## Remaining errors

| Class | Count | Notes |
|-------|------:|-------|
| Required Top-1 misses | **0** | |
| Required Recall@3 misses | **0** | |
| Ambiguous Group misses | **0** | |
| Optional ungrounded | 1 | `ec_sw_semantic_only` DOCUMENT_LEVEL_ONLY (intentional) |

## Artifacts

- New run: `data/eval/results/document_set_benchmark/20260801T055229Z_b4532405/`
- Root cause: `docs/evaluation/NODE_RANKING_V1_4_ROOT_CAUSE_ANALYSIS.md`
- EC-SW ranking: `output/document_set/ec_sw/ec_sw_*.json` (per workflow)
- GR alignment: `node_alignments.json`, `structural_equivalence_groups.json`
