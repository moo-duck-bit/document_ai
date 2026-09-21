# XXCS Quality Improvement Report

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## Summary

This sprint improves XXCS generation quality for the EC-SW document set without changing Platform Runtime, Planner, Memory, or Goal Orchestrator. The work keeps the MDSR -> MDDR -> XXCS harness flow additive and preserves `hospital_reservation` as the frozen holdout without adding XXCS to that holdout.

## Root Cause

The baseline XXCS pipeline generated security items, but quality was limited by three issues:

- `linked_design_ids` was not computed from the actual Requirement -> Design relationship, so validation could not prove design traceability.
- The Word skeleton contains merged result rows; rendering separate columns could overwrite structured fields and lose method/result/link data.
- Validation used a coarse test completeness metric and did not distinguish empty fields from explicit `NOT_EXECUTED`.

## Data Model Changes

Each generated security item now keeps legacy keys while adding structured fields:

| Field | Purpose |
|---|---|
| `security_test_id` | Stable item ID such as `IA-04-T01` |
| `security_category` | IA, UC, SI, DC, or RA |
| `title` | Traceability title from MDSR security traceability |
| `requirement` | Security requirement ID |
| `linked_req_ids` | Normalized `Req. N` list |
| `linked_design_ids` | Normalized MDDR design block IDs |
| `test_method` | Rule-generated verification method |
| `test_procedure` | Planned verification procedure |
| `expected_result` | Expected verification condition |
| `actual_result` | Explicit execution status and result text |
| `satisfaction` | `PASS`, `FAIL`, `NOT_EXECUTED`, `NOT_APPLICABLE`, or `REVIEW_REQUIRED` |
| `evidence` | Evidence reference or explicit `NOT_COLLECTED` |
| `reviewer_note` | Human review guidance |
| `provenance` | Link rule and execution truth |

Backward-compatible keys (`req_id`, `test_result`, `applied`, `notes`, `linked_reqs`) remain present.

## Linking Strategy

The link calculation uses Req IDs before any text similarity:

1. Read each security test's `linked_req_ids`.
2. Normalize IDs such as `Req. 3`.
3. Search `design_items.json` for matching `req_id` / design block IDs.
4. Merge matching design IDs in deterministic order.
5. Remove duplicates.
6. Store the rule in `provenance.linked_design_rule`.

Example:

| Security ID | Linked Req IDs | Linked Design IDs |
|---|---|---|
| `IA-04` | `Req. 3`, `Req. 4`, `Req. 102`, `Req. 105`, `Req. 205` | `Req. 3`, `Req. 4`, `Req. 102`, `Req. 105`, `Req. 205` |

## Render And Extract

The renderer now writes structured result blocks that include method, procedure, expected result, actual result, linked requirements, and linked designs. Because the current XXCS skeleton contains merged cells, critical fields are also recoverable from the notes path.

The extractor now handles:

- security IDs written as `IA-04`, `IA 04`, or `IA04`
- table-contained test rows
- comma, semicolon, slash, and newline separated Req/Design lists
- `satisfaction` and `actual_result`
- labeled blocks such as `시험방법`, `절차`, `예상결과`, `실제결과`

## Validation Metrics

XXCS validation now reports separate metrics:

- `security_coverage`
- `linked_requirement_coverage`
- `linked_design_coverage`
- `test_method_completeness`
- `procedure_completeness`
- `expected_result_completeness`
- `actual_result_completeness`
- `satisfaction_completeness`
- `evidence_completeness`

`NOT_EXECUTED` is treated as an explicit, truthful value. It is not treated as a PASS and is distinct from an empty field.

## Before And After

Latest successful `lab_ec_sw` validation after force generation and provisional gold refresh:

| Metric | Before | After |
|---|---:|---:|
| MDSR validation | 100.0 | 100.0 |
| MDDR validation | 92.0 | 92.0 |
| XXCS validation | 77.1 | 98.4 |
| Integrated validation | 90.5 | 96.5 |
| Security coverage | 1.0 | 1.0 |
| Linked requirement coverage | 1.0 | 1.0 |
| Linked design coverage | 0.0 | 0.912 |
| Test completeness | 0.63 | 1.0 |
| Harness benchmark overall | 91.7 | 93.5 |

Completeness detail after improvement:

| Metric | Value |
|---|---:|
| Test method completeness | 1.0 |
| Procedure completeness | 1.0 |
| Expected result completeness | 1.0 |
| Actual result completeness | 1.0 |
| Satisfaction completeness | 1.0 |
| Evidence completeness | 1.0 |

## Skeleton Dependency

Current skeleton measurements:

| File | Size |
|---|---:|
| `data/templates/ec_sw/template_xxcs_skeleton.docx` | 25,236,996 bytes |
| `data/cases/lab_ec_sw/output_xxcs.docx` | 25,238,103 bytes |
| `data/examples/ec_sw/security_tests_mindrium_xa.json` | 55,777 bytes |

The template has 111 ZIP entries, including 92 `word/media` entries. Media accounts for about 24,127,391 uncompressed bytes and 23,520,706 compressed bytes. The safe direction is to keep this skeleton as fallback while preparing a lightweight XXCS skeleton that removes unnecessary media after visual comparison and human review. The current sprint did not delete or replace the existing template.

## Human Review Items

The generated XXCS is a structured test plan, not evidence of real security execution. Human review should focus on:

- whether each `linked_req_ids` list is correct for the project
- whether each `linked_design_ids` mapping is acceptable
- whether `NOT_EXECUTED` items should become executed test results
- whether evidence files/screenshots/logs should replace `NOT_COLLECTED`
- whether `NOT_APPLICABLE` items have sufficient rationale

## Human-approved XXCS Gold

The current gold remains provisional. To build human-approved XXCS gold:

1. Generate MDSR, MDDR, and XXCS for a train case.
2. Have a reviewer update actual test results, satisfaction, and evidence.
3. Store reviewed DOCX and review result metadata.
4. Promote with `document-bootstrap-gold --approve` only after review.
5. Keep `hospital_reservation` holdout frozen and do not add XXCS to that holdout without a separate holdout protocol update.

## Remaining Limitations

- `NOT_EXECUTED` is intentionally not a PASS; actual test result integration remains future work.
- The current 25MB skeleton dependency is still present.
- XXCS gold is provisional until human-approved review.
- Some Korean text appears mojibake in Windows terminal output, but DOCX/JSON files are written as UTF-8/Word content and tests validate structured extraction.

## Recommended Next Sprint

Prioritize real test result integration next. XXCS human review should run in parallel for gold approval, but the biggest remaining technical gap is replacing generated `NOT_EXECUTED` plans with executed results, evidence references, and reviewer-approved satisfaction.

