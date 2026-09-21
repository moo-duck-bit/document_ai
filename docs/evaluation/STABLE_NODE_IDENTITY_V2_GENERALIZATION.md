# Stable Node Identity v2 + Identity-aware Ranking (Cycle 3)

Comparison vs Cycle 2 run `20260801T143206Z_e6bd5201`.

New run: `20260801T152942Z_03c260f2`  
Immutable priors: `20260801T062321Z_c70af996`, `20260801T072116Z_cbdca939`, `20260801T143206Z_e6bd5201`.

## Root cause (summary)

See `STABLE_NODE_IDENTITY_V2_ROOT_CAUSE.md`.

- v1 `stable_node_id` hashed upload `document_identity` → same `REQ[REQ. 11]` differed across fixtures.
- Ranking ignored stable base; `rank_tier == 0` was sorted as 99 via `or 99`.
- Incomplete design/test extraction under column reorder.

## Changes

| Area | Change |
|------|--------|
| Stable Identity v2 | Base excludes document_id / row / table / filename; dual v1+v2 ids |
| Canonical key fields | Header + body distribution role detection |
| Duplicate handling | Instance signature; members preserved |
| Reconciliation | Merge by stable base; no cross-identifier merge |
| Identity-aware ranking | TIER_0..6; stable base before semantic; tier-0 sort fix |
| Eval | Match on `stable_node_id_base`; stable Top-1 metrics |

## Comparison

| Metric | Cycle 2 | Cycle 3 | Delta |
|--------|--------:|--------:|------:|
| Stable Identity Consistency | 0.875 | 1.000 | +0.125 |
| Stable Base Identity Consistency | N/A | 1.000 | — |
| Development Document F1 | 0.933 | 0.933 | 0 |
| Holdout Document F1 | 0.952 | 0.952 | 0 |
| Development Node Top-1 | 0.571 | 0.619 | +0.048 |
| Holdout Node Top-1 | 0.400 | 0.400 | 0 |
| Development E2E | 0.946 | 0.946 | 0 |
| Holdout E2E | 0.950 | 0.950 | 0 |
| Development Unsafe | 0.000 | 0.000 | 0 |
| Holdout Unsafe | 0.000 | 0.000 | 0 |
| False Patch | 0.000 | 0.000 | 0 |
| Stable Node Top-1 | N/A | 0.703 | — |
| Stable Recall@3 | N/A | 0.703 | — |
| Logical Base Match | N/A | 0.703 | — |

### Regression

| Metric | Cycle 2 | Cycle 3 |
|--------|--------:|--------:|
| Document Macro F1 | 1.000 | 1.000 |
| E2E Success | 1.000 | 1.000 |
| Unsafe | 0.000 | 0.000 |
| Required Node Top-1 | 0.692 | 0.692 |

### Domains (Cycle 3)

| Domain | E2E | Unsafe | Required Top-1 (domain) |
|--------|----:|-------:|------------------------:|
| EC-SW | 0.932 | 0.000 | 0.788 |
| General Report | 1.000 | 0.000 | 0.000 |
| Business Proposal | 1.000 | 0.000 | 0.000 |

## Remaining

- Holdout Node Top-1 still 0.400 — driven by General Report REQUIRED node ranking (out of Cycle 3 EC-SW focus).
- Exact instance match rate 0.000 in aggregate metric (instance flags rarely set on top-1).
- filename_variation_identity_consistency remains 0.0 (document-level short_id metric; stable base is filename-invariant by construction).

## Safety

Original / examples / freeze unchanged; Wrong Auto-route 0; Unauthorized writer 0; Unsafe auto patch 0; Stable-ID-only writer 0; Protocol OK.
