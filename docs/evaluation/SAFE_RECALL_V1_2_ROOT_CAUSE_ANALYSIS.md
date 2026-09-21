# Safe Recall v1.2 — Root Cause Analysis

**Benchmark baseline:** v1.1 `20260801T035304Z_298421a1`  
**Remaining SAFE_FAILURE:** 2 (DOCUMENT_MISSED)

## 1. EC-SW semantic-only

| Field | Value |
|-------|-------|
| Expected | MDTM → REVIEW_REQUIRED (nodes gold empty) |
| Predicted (v1.1) | MDTM → UNRELATED |
| Valid Req IDs | none |
| MDTM Change POC | 0 PATCH / 0 REVIEW (token overlap vs row text = 0) |
| Row text reality | Mostly `Req. N` + section IDs; description cell often empty |
| Drop stage | No `SEMANTIC_SECTION_MATCH` evidence → document policy UNRELATED |
| Adapter | Faithful to decisions |

**Fix:** Domain-concept semantic review (AUTH/ACCESS/SECURITY + requirement-intent) → REVIEW only, `supports_patch=false`. No exact-ID / role-only IMPACTED.

**Do not change:** PATCH thresholds, Writer, malformed policy, exact Req path.

## 2. General Report schedule/table

| Field | Value |
|-------|-------|
| Expected | REPORT_BASE → REVIEW_REQUIRED |
| CR | schedule/table + time token (e.g. Q4) |
| Template | `general_report_v1` has **no schedule section** (schedule lives on business_proposal) |
| Paragraph gate | needs ≥2 shared tokens; heading `일정` skipped (len&lt;8); `2026` alone insufficient |
| Tables | not scanned in `analyze_generic_template_doc` |
| Drop stage | candidate generation / section token overlap |

**Fix:** Concept normalization (SCHEDULE/TABLE/TIMELINE/…) + table/heading/time-unit retrieval → REVIEW only. Add schedule locator section to general report template. No new PATCH.

**Do not change:** methodology/results success paths beyond additive REVIEW; Writer; PATCH policy.

## 3. Success definition for these cases

REVIEW_REQUIRED at **document** level clears DOCUMENT_MISSED.  
Node gold is empty → prefer limited REVIEW node candidates (provenance) without inventing PATCH.
