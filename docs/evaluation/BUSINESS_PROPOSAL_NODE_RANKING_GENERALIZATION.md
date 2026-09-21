# Business Proposal Node Ranking — Generalization (Cycle 5)

**Verdict:** `READY_FOR_BUSINESS_PROPOSAL_NODE_BENCHMARK_RERUN`

| Item | Value |
|------|-------|
| Baseline (Cycle 4) | `20260801T163826Z_ab762b81` |
| New run (Cycle 5) | `20260801T181011Z_e7fe9ba3` |
| Pytest | 1562 passed |

## Metric comparison

| Metric | Cycle 4 | Cycle 5 | Delta |
|--------|--------:|--------:|------:|
| Holdout Document F1 | 0.952 | 0.952 | 0.000 |
| Holdout Node Top-1 | 0.700 | 0.700 | 0.000 |
| Development Node Top-1 | 0.810 | 0.810 | 0.000 |
| Holdout E2E | 0.950 | 0.950 | 0.000 |
| General Report Node Top-1 | 1.000 | 1.000 | 0.000 |
| Business Proposal Required Node Top-1 | 0.000 | 0.000 | 0.000 |
| Business Proposal Required case count | (implicit 0) | **0** | — |
| EC-SW Stable Identity | 1.000 | 1.000 | 0.000 |
| Regression Node Top-1 | 1.000 | 1.000 | 0.000 |
| Development Unsafe | 0.000 | 0.000 | 0.000 |
| Holdout Unsafe | 0.000 | 0.000 | 0.000 |
| False Patch | 0.000 | 0.000 | 0.000 |

## Root cause (Required Top-1 still 0)

All Business Proposal impactable cases remain **`OPTIONAL` with empty gold nodes**.

```
required_top1_hit_rate = hits / count(mode==REQUIRED)
```

Denominator = 0 → reported 0.0. This is a **label-mode gap**, not a ranking failure after Cycle 5.

Label audit (proposals only, gold not mutated):

- `output/document_set/business_proposal/business_proposal_node_label_audit.json`
- `output/document_set/business_proposal/business_proposal_proposed_label_changes.json`

Proposed gold primaries (template IDs): `business_proposal_v1.{schedule,budget,risks,organization,expected_outcomes}`.

## Proxy: intent grounding (no gold read)

Against CR→preferred template mapping on 10 impactable OPTIONAL cases in the Cycle 5 run:

| Proxy metric | Value |
|--------------|------:|
| Intent Grounding Top-1 | **1.000** |
| Intent Grounding Recall@3 | **1.000** |
| n cases | 10 |

Every schedule/budget/risk/org/effect/en/dup case ranked the matching `business_proposal_v1.*` section at Top-1.

Artifact: `business_proposal_intent_grounding_metrics.json` (run dir + `output/document_set/business_proposal/`).

## What changed

- Domain pack `src/document_ai/domain_packs/business_proposal/` (concepts, intent, roles, alignment, match, ranking, validation, label audit)
- `proposal_table_retrieval` for schedule/budget/org/KPI tables (PATCH forbidden)
- BP path in `analyze_generic_template_doc` (GR path unchanged)
- Concept synonyms: EXPECTED_EFFECT, expanded BUDGET/RISK/ORG
- Prediction adapter metadata fields; `required_case_count` in domain metrics
- Cycle 5 summary artifacts in evaluator / report builder

## Safety

| Check | Result |
|-------|--------|
| Original / examples / Freeze | unchanged |
| Unauthorized writer | 0 |
| Unsafe auto patch | 0 |
| Writer scope | unchanged (`writer_executable=False`, `supports_patch=False`) |
| Gold / case hard-code | none |
| Immutable prior runs | preserved |

## Remaining

1. Promote BP OPTIONAL → REQUIRED with proposed template gold (separate ticket; not done here).
2. After label promotion, re-measure official Required Node Top-1 / Recall@3 / MRR.
3. Holdout Node Top-1 unchanged at 0.700 (BP OPTIONAL does not enter calibrated REQUIRED denominator).

## Next gate

Official Required BP metrics need label promotion. Ranking + alignment + table retrieval are ready for that remeasure.
