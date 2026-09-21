# XXCS Quality Diagnosis

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## Scope

This diagnosis covers `lab_ec_sw` XXCS generation and validation quality using:

- `data/cases/lab_ec_sw/security_tests.json`
- `data/cases/lab_ec_sw/design_items.json`
- `data/cases/lab_ec_sw/requirements.json`
- `data/cases/lab_ec_sw/output_xxcs.docx`
- `data/cases/lab_ec_sw/validation_report.json`
- `data/templates/ec_sw/template_xxcs_skeleton.docx`
- `data/examples/ec_sw/security_tests_mindrium_xa.json`

Baseline metrics before this improvement sprint:

| Metric | Baseline |
|---|---:|
| XXCS validation | 77.1 |
| Test completeness | 0.63 |
| Linked requirement coverage | 1.0 |
| Linked design coverage | 0.0 |
| Security coverage | 1.0 |
| Harness benchmark overall | 91.7 |

## Findings

### Source JSON Missing Or Mis-shaped `linked_design`

`security_tests.json` had legacy keys (`req_id`, `test_result`, `applied`, `satisfaction`, `notes`) and a string-form `linked_design_ids`. In older generated payloads, linked design values were copied from a broad design list instead of being computed from each security item's linked requirements. This meant the JSON could contain link-looking text without reliable per-test provenance.

Root cause: `linked_design_ids` was not derived from `security test -> linked_req_ids -> design_items.req_id`.

### Render Dropped Link And Field Structure

The XXCS skeleton contains tables where some body rows behave as merged cells. Filling multiple logical columns (`시험결과`, `적용`, `만족`, `비고`) could overwrite the same underlying Word cell. Depending on table structure, either the result text or the notes text survived, but not always both.

Impact:

- `linked_design_ids` could exist in JSON but disappear from extracted DOCX data.
- `test_method`, `test_procedure`, `expected_result`, and `satisfaction` could be lost after render.
- Repeated patch/fill could produce inconsistent apparent completeness.

### Extractor Could Not Round-trip Rich Fields

The extractor handled basic table rows but did not reliably recover:

- `IA-04`, `IA 04`, `IA04` style ID variants.
- linked Req/Design lists split by comma, semicolon, or newline.
- structured cells containing `시험방법`, `절차`, `예상결과`, `실제결과`.
- explicit `NOT_EXECUTED` status from `actual_result`.

It also allowed label-only seed rows such as `시험방법` and `확인결과` to become test rows, lowering completeness and making seed-derived rows look like real execution data.

### Validation Matched Coverage But Not Design Traceability

Validation already captured `security_coverage` and `linked_requirement_coverage`, but `linked_design_coverage` was effectively 0.0 because generated DOCX extraction did not preserve design links. The matcher also treated empty values and explicit non-execution status too similarly for completeness.

### Result And Evidence Fields Were Ambiguous

The previous flow used `만족`/`PASS`-like values even when the system had only generated a test plan. This made completeness look partly filled but blurred the distinction between:

- planned test item
- actual executed result
- not executed
- not applicable
- review required

## Diagnosis Summary

| Area | Problem | Required Fix |
|---|---|---|
| Data model | Legacy fields only, weak per-test design provenance | Add structured fields and keep legacy keys |
| Linking | Design links not computed from Req IDs | Compute `linked_design_ids` from `linked_req_ids` intersecting `design_items.req_id` |
| Render | Merged cells overwrite structured values | Write deterministic structured content and duplicate critical fields in recoverable cells |
| Extract | ID variants and structured fields not round-tripped | Normalize security IDs and parse labeled field blocks |
| Validation | Completeness too coarse | Split method/procedure/expected/actual/satisfaction/evidence metrics |
| Execution truth | Planned tests could look like PASS | Use `NOT_EXECUTED` and explicit evidence placeholders |
| Skeleton | 25MB DOCX dependency | Keep fallback, document size/media dependency, consider lightweight template next |

