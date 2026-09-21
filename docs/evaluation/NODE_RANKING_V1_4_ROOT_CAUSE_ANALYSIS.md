# Node Ranking v1.4 — Root Cause Analysis

**Scope:** Document Set Benchmark v1.3 calibrated node misses  
**Method:** Artifact inspection of run `20260801T052854Z_1accfb51` + MDTM index inspection  
**No prediction-driven gold edits.**

## 3-1. MDTM adjacent-row ranking

### Observed pattern (Required Top-1 misses)

Example `ec_sw_exact_req_single` (gold = `…row_0003…`, Req. 2):

| Rank | Status | Score | Node | Reasons |
|-----:|--------|------:|------|---------|
| 1 | REVIEW_REQUIRED | 0.25 | row_0002 (Req. 1) | semantic_or_lexical_overlap_only |
| 2 | PATCH_CANDIDATE | 0.22 | row_0003 (Req. 2) | exact_requirement_id_match |

**Root causes:**

1. **Identifier type weighting missing in score path**  
   `prediction_adapter` used `metadata.overlap` (token Jaccard) as the node score. Exact Req match rows often have *low* lexical overlap with the CR, so weak semantic REVIEW neighbors outranked PATCH.

2. **No rank tier**  
   Exact primary identifier and semantic overlap competed in a single scalar (~0–1). Exact match did not dominate.

3. **Design/test query IDs not extracted into change POC**  
   `observational` → `run_mdtm_change_poc` did not parse design/test IDs from the CR. For `설계 ID 4.2.2…`, only weak text overlap fired — wrong adjacent row (`4.2.1` / Req. 1) became the sole REVIEW candidate.

4. **Neighbor context**  
   Indexer already scopes identifiers to **row-local cells** (good). Leakage was primarily **scoring**, not OOXML merge inheritance. Still need explicit `identifier_origin` / evidence_scope so adjacent context can never count as exact.

5. **Tie-break**  
   When scores tied near zero, alphabetical `node_id` preferred earlier rows (`row_0002` before `row_0003`).

### Expected vs predicted score gap

Exact row should sit in **TIER_1 (~100+)**; semantic-only neighbors in **TIER_4/5 (~10–35)**. Prior gap was ~0.03 in the wrong direction.

## 3-2. Ambiguous template / structure alignment

### Observed pattern

| Case | Gold | Top-1 prediction |
|------|------|------------------|
| `gr_schedule_table` | `general_report_v1.schedule` | `heading_0007` (일정) |
| `gr_duplicate_heading` | `general_report_v1.results` | `paragraph_*` |

**Root causes:**

1. Heading/paragraph nodes and template section nodes are **separate identity spaces**.
2. Schedule heading scores (~0.95–1.0) exceeded template section hint score (0.7).
3. Ambiguous group metrics compared **raw node_ids** without a validated equivalence bridge.
4. No explicit `equivalent_for_evaluation` vs `equivalent_for_patch` split.

## Implications for v1.4

| Fix | Addresses |
|-----|-----------|
| QueryIntent + design/test extraction | design_id_only miss @3 |
| IdentifierMatchMatrix + Rank Tier | Required Top-1 / MRR |
| final_score in adapter | score path inversion |
| NodeAlignment + group expansion | Ambiguous Hit@1 |
| Template score boost when aligned | ranking among schedule candidates |

Optional grounding for semantic-only remains document-level by design (no forced node inventing).
