# EC-SW Document Impact Error Diagnosis (Benchmark v1)

**Benchmark run:** `20260801T033458Z_209e1bb9`  
**Focus:** DOCUMENT_FALSE_POSITIVE → UNSAFE_FAILURE (2)

## Pipeline (actual)

```
Change Request
  → extract_requirement_ids (mdtm_schema.REQ_RE)
  → run_document_set_observational / MDTM Change POC
  → analyze_ec_sw aggregates impacted_documents
  → workflow.impacted_documents
  → prediction_adapter → DocumentImpactPrediction
```

## Error case A — malformed Req format

| Field | Value |
|-------|-------|
| Case (label only) | bad Req format / `REQ2 …` style CR |
| Expected document | MDTM → UNRELATED |
| Predicted | MDTM → IMPACTED |
| Identifier extraction | `REQ_RE = Req\.?\s*(\d+)` matches **REQ2 → Req. 2** |
| Exact node evidence | MDTM row for Req. 2 → PATCH_CANDIDATE |
| Role promotion | N/A (single doc) |
| Root function | `mdtm_schema.extract_requirement_ids` / `REQ_RE` |
| Adapter | marks MDTM IMPACTED from patch_candidates |

**Fix candidate:** stricter identifier parser; REQ2 without separator → MALFORMED, not exact evidence.

## Error case B — MDTM-only multi-document

| Field | Value |
|-------|-------|
| Expected | MDTM IMPACTED; MDSR stub UNRELATED |
| Predicted | both IMPACTED |
| Exact evidence | MDTM nodes only |
| Role promotion | **YES** — `analyze_ec_sw` lines 55–58 |
| Code | `if role in {requirements, design} and reqs: impacted.append(doc_id)` |
| Adapter | uploaded stub in `impacted_documents` → IMPACTED |

**Fix candidate:** remove role-only promotion; require substantive evidence per document.

## Aggregation path

1. MDTM candidates → add `"MDTM"` to impacted (correct when exact match)
2. **Bug:** any upload with role `requirements`/`design` + non-empty `reqs` → IMPACTED
3. Adapter: `did in impacted` → IMPACTED (faithful to workflow; fix upstream)

## Do not change

- Node PATCH_CANDIDATE policy thresholds (keep False Patch = 0)
- Physical Locator / Patch Contract / Controlled Writer
- Approval / Rollback / original protection
- General Report pack analysis
- Benchmark case-id hardcoding / gold reads

## Fix order

1. Identifier parser (VALID / MALFORMED / …)
2. DocumentImpactEvidence + decision policy
3. `analyze_ec_sw` uses policy; drop role-only append
4. Adapter prefers explicit `document_impact_decisions` when present
5. Artifacts + regression tests + Benchmark v1.1
