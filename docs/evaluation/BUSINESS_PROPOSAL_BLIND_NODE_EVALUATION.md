# Business Proposal Node Gold Labeling & Blind Evaluation (Cycle 6)

Baseline: Cycle 5 run `20260801T181011Z_e7fe9ba3` (see
[`BUSINESS_PROPOSAL_NODE_RANKING_CYCLE5_ROOT_CAUSE.md`](./BUSINESS_PROPOSAL_NODE_RANKING_CYCLE5_ROOT_CAUSE.md))
· Cycle 4 run `20260801T163826Z_ab762b81`.

Target verdict: **`READY_FOR_BUSINESS_PROPOSAL_BLIND_NODE_EVALUATION`**

---

## 1. Executive summary

Cycle 5 found that `business_proposal` had **zero `REQUIRED` node-evaluation
cases** — every BP case was pre-labeled `OPTIONAL` (or `NOT_APPLICABLE` for
`no_impact` cases) as a generation-time placeholder, so
`required_top1_hit_rate` for the domain was a `0/0` denominator artifact, not
a real ranking-quality signal.

Cycle 6 closes that gap by building **real, independent, structure-derived
node gold** — REQUIRED / AMBIGUOUS / OPTIONAL / NOT_APPLICABLE — for every BP
case (12 pre-existing + 10 newly added), so the domain finally has a
meaningful REQUIRED denominator for the existing (unmodified) ranking /
structural-match / retrieval / query-intent pipeline to be scored against.

| Mode | Count |
|------|------:|
| REQUIRED | 14 |
| AMBIGUOUS | 4 |
| OPTIONAL | 2 |
| NOT_APPLICABLE | 2 |
| **Total** | **22** |

Pass1/Pass2 agreement: **1.0** (raw, mode, and reference agreement). Gold
validation status: **VALID**. Holdout re-sealed: **yes**.

## 2. Background & motivation

- Cycle 4 (`20260801T163826Z_ab762b81`) established the v2 generalization
  harness (dev/holdout split, sealed holdout protocol, robustness suite).
- Cycle 5 (`20260801T181011Z_e7fe9ba3`) diagnosed the BP `REQUIRED`
  zero-denominator problem and shipped `business_proposal_proposed_label_changes.json`
  as a **proposal only** — explicitly not auto-applied, to avoid mixing
  prediction output into gold.
- Cycle 6 (this document) is the "future ticket" that Cycle 5 deferred:
  produce independent gold so the domain's `REQUIRED` metric is real.

## 3. Scope & critical constraints

Cycle 6 is **labeling and metrics-wiring only**. It explicitly does **not**:

- Change ranking / `structural_match` / `proposal_table_retrieval` /
  `query_intent` scoring logic.
- Auto-apply `business_proposal_proposed_label_changes.json`.
- Use prediction Top-1 as gold (gold is derived from document structure +
  `change_request` text only, inspected via `python-docx`).
- Overwrite the Cycle 5 (`20260801T181011Z_e7fe9ba3`) or Cycle 4
  (`20260801T163826Z_ab762b81`) result directories.
- Modify `data/examples` / `data/freeze`.
- Change writer scope (all BP cases remain `should_write=False`, `GATED`).

## 4. Gold labeling methodology

Gold is produced by a **deterministic, prediction-blind policy**:

1. `document_inventory.py` re-parses the case's DOCX (`python-docx`) into
   headings / paragraphs / tables with stable indices
   (`heading_{i:04d}`, `paragraph_{i:04d}`, `table_{ti:02d}`), grouped into
   heading-bounded sections, each tagged with canonical concepts from static
   dictionaries (`domain_packs.business_proposal.concepts`,
   `template.concept_normalization`).
2. `policy.py` resolves the change request's target concept (from tags first,
   then text), finds matching section(s) in the *inventory only*, and applies
   fixed rules (§6) — no ranking/embedding/LLM call is involved.
3. Two independent passes (`labeling_pass.py`) run the *same* policy function
   but Pass 2 **re-derives the inventory from the DOCX file again** rather
   than reusing Pass 1's in-memory result, so a regression in either the scan
   or the policy would surface as a Pass1/Pass2 disagreement.
4. `validation.py` rejects/flags structurally inconsistent rows before they
   can be sealed (§8).

## 5. Package architecture

```
src/document_ai/evaluation/business_proposal_gold/
├── __init__.py
├── schema.py                 # BusinessProposalGoldRow / PrimaryReference dataclasses
├── document_inventory.py     # DOCX → headings/paragraphs/tables/sections (structure only)
├── policy.py                 # deterministic REQUIRED/AMBIGUOUS/OPTIONAL/NOT_APPLICABLE rules
├── labeling_pass.py          # Pass1/Pass2 + disagreement/agreement metrics
├── validation.py             # gold row + CR/table-alignment validation rules
├── protocol.py                # draft/review/sealed dirs, hashing, seal, static "no sealed-read" check
├── project_to_benchmark.py   # merge gold into node_evaluation_eligibility.jsonl / node_impacts.jsonl
├── official_metrics.py       # gold-based REQUIRED node metrics + prediction-only proxy metric
├── error_analysis.py         # miss taxonomy (WRONG_TEMPLATE_NODE, HEADING_INSTEAD_OF_TABLE, ...)
└── audit.py                  # old-mode → new-mode case decision table (PROMOTE/DEMOTE/KEEP/NEW_CASE)
```

Orchestrator: `scripts/build_business_proposal_node_gold_cycle6.py`.

## 6. Deterministic policy rules

| Situation | Mode | Notes |
|-----------|------|-------|
| Tag in `no_impact` set | `NOT_APPLICABLE` | Cover/off-topic edits with no structural counterpart. |
| No canonical concept resolves from tags/text | `OPTIONAL` | Virtual target; avoids inventing structure. |
| Concept resolves, no matching section in the document | `OPTIONAL` | Template id offered as the (unrealized) review target. |
| Concept matches exactly one section, one representative node | `REQUIRED` | Representative = best-scoring physical node (table > content paragraph > heading > boilerplate paragraph), gated by `table_intent`/`paragraph_intent` from `query_intent`. |
| `ADD` operation onto an **existing** section | `AMBIGUOUS` | Augmenting vs. treating as new addition are both plausible. |
| Concept matches **>1** section | `AMBIGUOUS` | Group = all matching section headings + template id. |
| Case tagged as scope-ambiguous (`schedule_section`, `risk_amb`) | `AMBIGUOUS` (forced) | Explicit whole-section-vs-node ambiguity fixtures. |

Primary-reference priority is **Stable > Template > Physical**: the template
node id (`business_proposal_v1.*`) is used as the *projected* evaluation
primary for cross-run identity stability; the physical node
(table/paragraph/heading) is recorded in `primary_reference.document_node_id`
and always included in `acceptable_node_ids` / `acceptable_node_groups`, so
either representation resolves the evaluation.

## 7. Two-pass labeling & disagreement detection

`labeling_pass.run_pass1` / `run_pass2` label every BP case independently.
`detect_disagreements` compares substantive fields (mode, primary reference,
acceptable groups, physical type, operation) — ignoring `labeled_by` /
`labeled_at` / free-text rationale. `agreement_metrics` reports raw, mode, and
reference agreement rates.

Result for the full 22-case BP set: **raw = mode = reference = 1.0**
(0 disagreements) — the deterministic policy is fully reproducible from
structure + change_request alone.

## 8. Validation rules

`validation.py` rejects/flags:

- `REQUIRED` with no primary reference, or a `VIRTUAL`-only primary.
- `AMBIGUOUS` with no acceptable group, or a group of size < 2.
- `UPDATE` operation resolved to a `VIRTUAL`-only reference.
- A `TABLE`-location row whose physical type isn't `TABLE`.
- Empty rationale, or a rationale that references a prediction artifact
  (ranking results, `node_ranking`, `structural_match_matrix`,
  `proposed_label_changes`, `top-1`, etc.) — a tripwire against accidentally
  gold-washing model output.
- A change request with **literal** table wording ("표"/"테이블"/"table")
  resolved to a paragraph-only physical node (reject for `REQUIRED`, warn
  otherwise). This check is deliberately narrower than
  `BusinessProposalQueryIntent.table_intent` — SCHEDULE/BUDGET/KPI concepts
  are `table_intent=True` by domain-pack convention even when the document
  only has a paragraph, which is legitimate `REQUIRED` gold, not a mismatch.
- Node ids (physical or group members) that don't exist in that case's own
  document inventory ("wrong document" guard).

Current sealed set: **0 validation issues** (`VALID`).

## 9. Fixtures & cases added

New fixtures (`data/eval/document_set_benchmark_v2/fixtures/business_proposal/`),
built with `python-docx`:

| Fixture | Content |
|---------|---------|
| `proposal_schedule_table.docx` | 일정 heading + schedule table (단계/기간/시작/종료) |
| `proposal_org_table.docx` | 수행 조직 heading + role table (조직/역할/담당) |
| `proposal_kpi.docx` | 기대 효과 heading + KPI table (KPI/목표/지표) |
| `proposal_deliverables.docx` | 산출물 heading + deliverable list paragraphs |

New development cases: `v2_dev_bp_sched_table`, `v2_dev_bp_labor_cell`,
`v2_dev_bp_kpi`, `v2_dev_bp_deliverable`, `v2_dev_bp_market_add`,
`v2_dev_bp_style_overall`, `v2_dev_bp_schedule_section`.

New holdout cases: `v2_hol_bp_org_table`, `v2_hol_bp_effect_para`,
`v2_hol_bp_risk_amb`.

`document_impacts.jsonl` / `writer_expectations.jsonl` were extended for all
10 new cases (`GATED`, `should_write=False`, matching the existing BP writer
scope — unchanged).

## 10. Gold content summary & case audit

Pre-Cycle6 baseline (from `generate_document_set_benchmark_v2.py`): **every**
pre-existing BP case was labeled `OPTIONAL` (or `NOT_APPLICABLE` for
`no_impact`) as a placeholder — there was no real mode distinction. The
Cycle 6 case-label audit (`business_proposal_case_label_audit.json`) records
the decision for every case against that baseline:

| Decision | Count |
|----------|------:|
| `PROMOTE_TO_REQUIRED` | 8 |
| `PROMOTE_TO_AMBIGUOUS` | 2 |
| `NEW_CASE_REQUIRED` | 6 |
| `NEW_CASE_AMBIGUOUS` | 2 |
| `NEW_CASE_OPTIONAL` | 2 |
| `KEEP_NOT_APPLICABLE` | 2 |

By split: 15 development BP cases, 7 holdout BP cases labeled.

## 11. Protocol: draft / review / sealed + holdout reseal

```
data/eval/document_set_benchmark_v2/business_proposal_node_gold/
├── draft/business_proposal_node_gold_draft.jsonl       # Pass 1 output
├── review/business_proposal_node_gold_review.jsonl     # Pass 2 output
├── sealed/business_proposal_node_gold_final.jsonl       # agreed + validated rows
├── business_proposal_node_gold_manifest.json            # {n_rows, sealed_files, aggregate_hash, status}
├── business_proposal_node_gold_hashes.json               # per-file sha256
├── business_proposal_label_disagreements.json
├── business_proposal_labeling_summary.json               # counts + agreement metrics + verdict
├── business_proposal_case_label_audit.json
└── validation_report.json
```

Hashing/sealing reuses `document_set_v2.holdout_protocol` primitives
(`hash_label_dir`, `_sha256_bytes`) for a consistent audit story with the
main v2 holdout seal. `protocol.prediction_code_must_not_read_sealed_bp_gold`
statically greps prediction/analysis/domain-pack source files for references
to `business_proposal_node_gold/sealed`; the real
`prediction_adapter.py`, `workflow/analysis.py`,
`domain_packs/business_proposal/*.py`, and
`document_set/proposal_table_retrieval.py` are clean (see test suite, §14).

After projecting gold into the benchmark labels (§12), the holdout label
directory is **re-sealed** via `write_seal_manifest`, producing a fresh
`holdout_label_manifest.json` with `status: SEALED` and a new
`aggregate_hash`.

## 12. Benchmark projection

`project_to_benchmark.gold_row_to_projection` maps each sealed gold row into:

- `node_evaluation_eligibility.jsonl`: `primary_node_id` = template id
  (Stable > Template > Physical), `acceptable_node_ids` includes the physical
  node + all group members, `acceptable_node_groups` mirrors the gold row's
  groups.
- `node_impacts.jsonl` (only for `REQUIRED`/`AMBIGUOUS`): `node_id` = the
  physical node, `gold_status = REVIEW_REQUIRED`.

Projection **merges** into `development/labels/` and
`holdout/sealed_labels/` — non-BP rows for every other case_id are read back
unchanged and rewritten as-is; only BP case_ids are replaced.

## 13. Evaluator wiring (metrics only)

`document_set_v2/evaluator.py` now additionally computes, from the *existing*
calibrated-case / `rank_nodes` primitives (no scoring logic changes):

| Artifact | Source |
|----------|--------|
| `business_proposal_official_node_metrics.json` | `official_metrics.compute_official_business_proposal_metrics` — REQUIRED-only Top-1/R@3/R@5/MRR, `N/A` (not `0.0`) when the denominator is zero. |
| `business_proposal_proxy_metrics.json` | `official_metrics.compute_proxy_intent_grounding_metrics` — CR→preferred-template vs. prediction, **does not read gold**. |
| `business_proposal_label_coverage.json` | Sealed-gold coverage / mode counts vs. total BP case count. |
| `business_proposal_label_agreement.json` | Copied from the gold-build summary's Pass1/Pass2 agreement metrics. |
| `business_proposal_node_errors.json` | `error_analysis.build_error_report` miss-taxonomy over REQUIRED cases. |
| `business_proposal_node_evaluation_summary.json` | Rollup of the above. |
| `business_proposal_blind_evaluation_manifest.json` | Sealed-gold manifest + holdout BP case ids + `prediction_reads_sealed_bp_gold: false`. |
| `cycle6_generalization_summary.json` | Dev-vs-holdout official Top-1 + gap, baseline run ids, verdict. |

The pre-existing `business_proposal_node_metrics.json` (legacy
`domain_breakdown`-derived proxy) is retained unchanged in shape, with its
stale "zero-denominator until promoted" note updated to point at the new
official-metrics artifact.

## 14. Test coverage

5 new test files, **80 tests**, all passing:

| File | Focus | Tests |
|------|-------|------:|
| `test_business_proposal_gold_schema.py` | dataclass round-trips/defaults | 9 |
| `test_business_proposal_gold_policy.py` | REQUIRED/AMBIGUOUS/OPTIONAL/NOT_APPLICABLE rules | 13 |
| `test_business_proposal_gold_inventory_and_validation.py` | DOCX scan + validation rules | 18 |
| `test_business_proposal_gold_protocol_and_labeling_pass.py` | draft/review/seal, Pass1/Pass2, static sealed-read check | 17 |
| `test_business_proposal_gold_project_and_metrics.py` | projection, official/proxy metrics, error taxonomy, audit | 21 (incl. 2 combined) |

`test_real_prediction_code_paths_do_not_read_sealed_bp_gold` runs the static
protocol check against the actual `prediction_adapter.py`,
`workflow/analysis.py`, `domain_packs/business_proposal/*.py`, and
`document_set/proposal_table_retrieval.py` files in this repo.

Existing `tests/test_benchmark_v2_*.py` (52 tests) pass unchanged, and
`validate_benchmark_v2` reports `VALID` for the full manifest after the new
fixtures/cases/labels are added.

## 15. Results (Cycle 6 blind run)

| Item | Value |
|------|-------|
| Run ID | `20260801T192542Z_5a685d77` |
| Protocol | SEAL → predict → freeze → UNSEAL (`protocol_ok: true`) |
| Pytest | 1653 passed |
| Verdict | **`READY_FOR_BUSINESS_PROPOSAL_BLIND_NODE_EVALUATION`** |

### Official Gold-based metrics (BP REQUIRED, n=14)

| Metric | Value |
|--------|------:|
| Required Top-1 | **0.929** |
| Recall@3 | **0.928** |
| Recall@5 | **0.929** |
| MRR | **0.929** |
| Holdout Required Top-1 (n=5) | **1.000** |
| Development Required Top-1 (n=9) | **0.889** |
| Ambiguous Group Hit@1 (calibrated) | **1.000** |
| Label Coverage | **1.000** |

Single REQUIRED miss: `v2_dev_bp_labor_cell` (SAFE_FAILURE, empty node candidates) — ranking/candidate gap deferred to a future cycle (gold unchanged).

### Proxy Intent-grounding metrics (no gold; n=22 including OPTIONAL/NA)

| Metric | Value |
|--------|------:|
| Intent Grounding Top-1 | 0.273 |
| Intent Grounding Recall@3 | 0.636 |

Proxy is lower than Cycle 5’s impactable-only 1.0 because OPTIONAL/ADD/no-impact cases are included and do not always map to a preferred template. **Do not mix with official metrics.**

### Safety / overall regression vs Cycle 5

| Metric | Cycle 5 | Cycle 6 | Notes |
|--------|--------:|--------:|-------|
| Holdout Document F1 | 0.952 | **0.956** | held / slight ↑ |
| Holdout Node Top-1 | 0.700 | **0.800** | ↑ as BP REQUIRED enters denom |
| Holdout E2E | 0.950 | **0.957** | held |
| Development Unsafe | 0.000 | **0.000** | |
| Holdout Unsafe | 0.000 | **0.000** | |
| False Patch | 0.000 | **0.000** | |
| GR Required Top-1 | 1.000 | **1.000** | |
| EC-SW Stable Identity | 1.000 | **1.000** | |
| Regression Node Top-1 | 1.000 | **1.000** | |
| Original / Examples / Freeze | 0 | **0** | |
| Writer scope | unchanged | unchanged | |

Development E2E (all domains) 0.946 → 0.886 reflects new BP SAFE_FAILURE cases (`labor_cell`, `market_add`, `style_overall`); Unsafe remains 0.

### Agreement & protocol

- Evaluation Mode / Node Reference / Raw Agreement: **1.000**
- Disagreements: **0**
- Gold sealed: yes · Prediction frozen: yes · Gold read during inference: **false**
- Automatic Gold mutation: **0** · Proposed labels auto-applied: **0**

### Next development priority

Cycle 7 (ranking only if needed): investigate `v2_dev_bp_labor_cell` empty-candidate SAFE_FAILURE and OPTIONAL ADD grounding — **without mutating sealed gold in place**.
