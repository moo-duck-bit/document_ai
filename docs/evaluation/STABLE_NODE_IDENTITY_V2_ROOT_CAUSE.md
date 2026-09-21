# Stable Node Identity v2 — Root Cause (Cycle 3)

Baseline run: `20260801T143206Z_e6bd5201` (Cycle 2).

## Summary

| Symptom | Root cause |
|---------|------------|
| Stable Identity Consistency 0.875 | `document_identity` (upload fixture id) hashed into `stable_node_id` |
| Same `REQ[REQ. 11]` → different stable IDs | Base vs `mdtm_cols_dtr` / `row_shuffle` / `note_col` / `no_caption` |
| Incomplete logical keys | Design/test often empty; fixed column fallbacks break on reorder |
| Holdout Node Top-1 0.400 | Mostly GR REQUIRED misses; EC-SW ranking ignores stable base |
| Regression Node Top-1 0.692 | Exact legacy path weak; ranking score order ≠ identity match |
| Eval vs inference gap | Eval expands via CR∩identifiers; ranking still legacy-score only |

## Artifact checks (Req. 11 row)

| Fixture | logical_key | stable_node_id (v1) |
|---------|-------------|---------------------|
| mdtm_base | `REQ[REQ. 11]` | `stable.table_row.43af7d52…` |
| mdtm_cols_dtr | `REQ[REQ. 11]` | `stable.table_row.356e23e0…` |
| mdtm_row_shuffle | `REQ[REQ. 11]` | `stable.table_row.a44d5a0d…` |
| mdtm_note_col | `REQ[REQ. 11]` | `stable.table_row.fc43d20e…` |
| mdtm_no_caption | `REQ[REQ. 11]` | `stable.table_row.f899e73e…` |

Answers to analysis questions:

1. Same identifier set, different stable ID — **yes** (document_identity in hash).
2. Raw text in hash — ordered cell text in **legacy** id only; stable uses logical_key.
3. Optional columns in base — note excluded from core, but document_id still differs.
4. Duplicate instance key — index-based `#dup{i}`; not row_index primary but weak.
5. Stable match vs ranking — eval can hit via identifiers; ranking does not boost stable base.
6. Inference ranking legacy-centric — **yes**; `structural_match` always 0.
7. Merged cells — can inflate cell hash (legacy); stable key uses extractors.
8. Logical key cell detection — role fallbacks `[0],[3],[4]` fragile on reorder.
9. Same base, wrong instance — duplicate groups penalized equally; no local content rank.
10. Dedupe loss — members preserved; evidence not merged into reconciled candidate.

## Fix direction

- `stable_node_id_base` from domain_pack + role + node_type + canonical identifier set (**no** upload document_id / row / table / filename).
- Instance key from row-local substantive content signature.
- Canonical key field detection by header + value distribution.
- Reconciliation layer merging legacy/stable/physical evidence.
- Identity-aware rank tiers (exact primary + stable base before semantic/context).
- Keep v1 ids for comparison; writer still requires physical locator.
