# Safe Generalization Cycle 2 — Root Cause

## Scope

Run under analysis: `20260801T072116Z_cbdca939` (Auto Routing).

Unsafe cases:

| Split | Case | Gold | Pred (doc) | E2E |
|-------|------|------|------------|-----|
| development | `v2_dev_gr_missing` | UNRELATED | REVIEW_REQUIRED | UNSAFE_FAILURE |
| development | `v2_dev_gr_no_impact` | UNRELATED | REVIEW_REQUIRED | UNSAFE_FAILURE |
| holdout | `v2_hol_gr_missing` | UNRELATED | REVIEW_REQUIRED | UNSAFE_FAILURE |

EC-SW SAFE_FAILURE / node miss on table structure variants (column reorder, empty row, row shuffle, note column).

## General Report unsafe

### Pipeline

Change Request → `normalize_concepts` → template section token/concept overlap →
`review_required` nodes → optional schedule retrieval → document-level REVIEW →
E2E treats gold UNRELATED + pred REVIEW as UNSAFE_FAILURE.

### Findings

1. **Substring concept false positives**  
   `normalize_concepts` matches synonym `표` as a substring inside compact text.  
   - `표지` → TABLE  
   - `목표` → TABLE  
   - `통계표` → TABLE  

2. **Weak template section hits become document REVIEW**  
   `analyze_generic_template_doc` promotes any section REVIEW into `impacted` and, via generic fallback, into document-level `REVIEW_REQUIRED` even when the target section does not exist in the uploaded document (e.g. “부록 통계표 추가”, “참고문헌 DOI 추가”).

3. **Schedule retrieval template-only evidence**  
   When CR concept includes TABLE / schedule tokens, `collect_schedule_table_evidence` can emit synthetic schedule evidence from **template section hits alone** (no document table/heading). That evidence alone drives document REVIEW for no-impact / missing cases.

4. **Presence / compatibility alone**  
   Not sufficient by themselves for IMPACTED, but weak template overlap + generic fallback is enough for document REVIEW.

5. **Document vs node REVIEW**  
   Structurally separate lists exist, but generic fallback collapses “some node REVIEW” into “document REVIEW”, which is what E2E unsafe uses.

6. **Prediction adapter source stage**  
   Documents always recorded as `document_impact_policy`; nodes as `change_poc`, hiding real stages (`schedule_table_retrieval`, `generic_template_sections`). Attribution issue; not the sole cause of unsafe.

### Fix direction

- Boundary-safe concept matching for short Korean synonyms.  
- Explicit no-impact / target-existence policy: IMPACTED requires substantive, document-grounded evidence on a specific node (or addable virtual target → REVIEW only).  
- Do not promote template-only / presence-only evidence to document IMPACTED/REVIEW.  
- Virtual missing targets stay REVIEW / UNRELATED; never PATCH.

## EC-SW node identity

### Findings

1. **`node_id` includes physical `row_index`**  
   Format: `ec_sw_v1.mdtm.table_{ti}.row_{ri}.{hash10}`.

2. **Hash uses ordered raw cell texts**  
   Column reorder changes the joined cell string → different hash.

3. **Note / empty optional cells** participate in the hash.

4. **Same Req/Design/Test set** can yield different IDs after reorder / row move / note column.

5. **Gold labels** for metamorphic variants reuse the **base fixture** `Req. 11` legacy `node_id`, so exact match fails even when the logical row is correct.

6. **Merged cells** can duplicate cell text in python-docx extraction and alter the raw hash.

### Fix direction

- Keep `legacy_node_id` (= current `node_id`) for physical/writer compatibility.  
- Add `stable_node_id` from canonical identifier set (sorted Req/Design/Test), independent of row index / column order / note columns.  
- Prediction / evaluation match: legacy exact → stable exact → identifier set → equivalence group.  
- Writer still requires physical locator; stable ID alone is never writer-executable.

## Invariants to add

- `no_presence_only_impacted`  
- `no_template_compatibility_only_impacted`  
- `impacted_requires_specific_node_or_addable_target`  
- `missing_unsupported_not_impacted`  
- `column_order_independent_stable_id`  
- `row_position_independent_stable_id`
