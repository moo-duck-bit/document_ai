# Document Identity + Auto Routing — Generalization Comparison

Evaluation report comparing Document Set Benchmark v2 baseline
(`20260801T062321Z_c70af996`) with the identity-resolution rerun
(`20260801T072116Z_cbdca939`).

Baseline run artifacts were not modified.

## What changed

Inference now runs:

1. Document signal extraction (filename, headings, tables, identifiers)
2. Canonical identity resolution (temporary upload ID ≠ canonical ID)
3. Domain pack routing (`explicit` / `auto` / `assisted`)
4. EC-SW upload indexing under the fixture `document_id` (fixes stem vs registry mismatch)

Filename-only evidence cannot `AUTO_SELECTED`. Conflicting user hints require `REVIEW`.

## Comparison

| Metric | v2 Baseline | Auto Routing | Delta |
|--------|------------:|-------------:|------:|
| Development Document F1 | 0.353 | 0.811 | +0.458 |
| Holdout Document F1 | 0.416 | 0.900 | +0.484 |
| Development Node Top-1 | 0.250 | 0.429 | +0.179 |
| Holdout Node Top-1 | 0.300 | 0.600 | +0.300 |
| Development E2E | 0.516 | 0.703 | +0.187 |
| Holdout E2E | 0.550 | 0.850 | +0.300 |
| Development Unsafe | 0.065 | 0.054 | −0.011 |
| Holdout Unsafe | 0.050 | 0.050 | 0.000 |
| Wrong Auto-route Rate | N/A | 0.000 | — |
| Canonical ID Accuracy | N/A | 0.988 | — |
| Pack Top-1 Accuracy | N/A | 1.000 | — |
| Table Structure Robustness | 0.000 | 1.000 | +1.000 |

### Regression (must hold)

| Metric | Baseline | New |
|--------|---------:|----:|
| Document Macro F1 | 1.000 | 1.000 |
| Required Node Top-1 | 1.000 | 1.000 |
| E2E Success | 1.000 | 1.000 |
| False Patch | 0.000 | 0.000 |
| Unsafe Failure | 0.000 | 0.000 |

### Identity / routing

| Metric | Value |
|--------|------:|
| Document Type Accuracy | 0.988 |
| Document Role Accuracy | 0.988 |
| Canonical Document ID Accuracy | 0.988 |
| Short ID Accuracy | 0.988 |
| Filename Independence (auto) | 1.000 |
| Pack Top-1 | 1.000 |
| Pack Recall@3 | 1.000 |
| Auto-selection Precision | 1.000 |
| Auto-selection Coverage | 0.543 |
| Wrong Auto-route Rate | 0.000 |
| Fixture→Canonical Match | 0.988 |
| Registry Alignment | 1.000 |

### Robustness

| Metric | Value |
|--------|------:|
| Table structure decision consistency | 1.000 |
| Table structure identity consistency | 0.875 |
| File-order identity consistency | 1.000 |
| Heading variation identity consistency | 1.000 |
| Filename variation identity consistency | 0.000 (no matching pairs scored) |

### Domain snapshot (new run)

| Domain | Doc hit | E2E | Unsafe |
|--------|--------:|----:|-------:|
| EC-SW | 0.932 | 0.750 | 0.000 |
| General Report | 0.880 | 0.880 | 0.120 |
| Business Proposal | 1.000 | 1.000 | 0.000 |

## Remaining errors

- **Identity**: rare mismatches when fixture domain expectation ≠ primary resolved role (~1.2%).
- **Routing**: no wrong auto-routes observed.
- **Indexing / nodes**: several EC-SW SAFE_FAILUREs remain when gold node IDs (from base matrix hash) differ after table structure transforms; document IMPACTED often correct.
- **Unsafe**: General Report `missing` / `no_impact` cases still surface as UNSAFE_FAILURE (false REVIEW / status mismatch) — most affected domain for unsafe rate.

## Safety

| Check | Result |
|-------|--------|
| Original / examples / freeze changed | 0 |
| Unauthorized writer | 0 |
| Unsafe auto patch | 0 |
| Wrong auto-route → writer | 0 |
| Holdout protocol | UNSEALED (post-freeze) |
| Baseline v2 run immutable | yes (`20260801T062321Z_c70af996`) |

## Artifacts

- New run: `data/eval/results/document_set_benchmark_v2/20260801T072116Z_cbdca939/`
- Identity metrics: `identity_metrics.json`, `pack_routing_metrics.json`, `document_id_alignment_metrics.json`, `table_structure_identity_robustness.json`
- Package: `src/document_ai/document_identity/`
