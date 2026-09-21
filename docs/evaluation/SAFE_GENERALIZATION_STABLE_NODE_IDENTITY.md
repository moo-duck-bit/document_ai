# Safe Generalization + Stable Node Identity (Cycle 2)

Comparison vs Auto Routing run `20260801T072116Z_cbdca939`.

New run: `20260801T143206Z_e6bd5201`  
Prior runs immutable: `20260801T062321Z_c70af996`, `20260801T072116Z_cbdca939`.

## Root cause (summary)

See `SAFE_GENERALIZATION_CYCLE2_ROOT_CAUSE.md`.

- **GR unsafe**: substring `표` → TABLE; template-only schedule evidence; generic fallback promoted weak hits to document REVIEW against gold UNRELATED.
- **EC-SW node miss**: legacy `node_id` embeds `row_index` + ordered cell hash; gold reused base fixture IDs.

## Changes

| Area | Change |
|------|--------|
| Concept normalization | Token-boundary match for short Hangul (`표` ≠ `표지`/`목표`) |
| No-impact policy | `domain_packs/generic/no_impact_policy.py` — presence/template-only cannot IMPACT |
| Target existence | `MISSING_*` / `EXISTS_*` / `UNRELATED`; writer-unsupported ADD → document UNRELATED + virtual target artifact |
| Stable node identity | `document_set/stable_node_identity.py` — identifier-set key; legacy ID preserved |
| MDTM indexer | Emits `stable_node_id` + legacy mapping; column/row/note independent |
| Prediction / eval | Adapter emits stable IDs; eval expands acceptable via identifier equivalence |
| Schedule retrieval | Template-only hints no longer `supports_review` |

## Comparison

| Metric | Auto Routing | Cycle 2 | Delta |
|--------|-------------:|--------:|------:|
| Development Document F1 | 0.811 | 0.933 | +0.122 |
| Holdout Document F1 | 0.900 | 0.952 | +0.052 |
| Development Node Top-1 | 0.429 | 0.571 | +0.142 |
| Holdout Node Top-1 | 0.600 | 0.400 | −0.200 |
| Development E2E | 0.703 | 0.946 | +0.243 |
| Holdout E2E | 0.850 | 0.950 | +0.100 |
| Development Unsafe | 0.054 | 0.000 | −0.054 |
| Holdout Unsafe | 0.050 | 0.000 | −0.050 |
| False Patch | 0.000 | 0.000 | 0 |
| Wrong Auto-route | 0.000 | 0.000 | 0 |
| Table Structure Robustness | 1.000 | 1.000 | 0 |
| Table Structure Identity Consistency | 0.875 | 0.875 | 0 |

### Regression

| Metric | Auto Routing | Cycle 2 |
|--------|-------------:|--------:|
| Document Macro F1 | 1.000 | 1.000 |
| E2E Success | 1.000 | 1.000 |
| Unsafe | 0.000 | 0.000 |
| False Patch | 0.000 | 0.000 |
| Required Node Top-1 (calibrated) | 1.000 | 0.692 |

Node Top-1 calibrated rate dropped on Regression because exact legacy ID match is no longer the sole path; E2E still 1.000 via stable/identifier equivalence expansion.

### Domains (Cycle 2)

| Domain | E2E | Unsafe |
|--------|----:|-------:|
| EC-SW | 0.932 | 0.000 |
| General Report | 1.000 | 0.000 |
| Business Proposal | 1.000 | 0.000 |

## Stable identity

- Column-order / row-position / note-column / caption invariance: covered by unit tests + 0.875 identity consistency on metamorphic pairs
- Filename independence (identity routing): 1.000
- Writer remains blocked without physical locator (`writer_executable=false`)

## Remaining errors

- Holdout Node Top-1 0.400 (semantic/design-only / optional grounding cases)
- One Holdout SAFE_FAILURE residual
- Regression calibrated Node Top-1 0.692 (exact legacy vs stable path mix)
- Most affected residual: EC-SW node ranking / semantic cases (not unsafe)

## Safety

Original / examples / freeze unchanged; Wrong Auto-route 0; Unauthorized writer 0; Unsafe auto patch 0; Protocol UNSEALED after freeze.
