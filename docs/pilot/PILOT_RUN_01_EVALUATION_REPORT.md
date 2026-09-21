# Pilot Evaluation Report — pilot_run_01

**Verdict: REAL_USER_PILOT_RUN_01_COMPLETE**

Generated: 2026-08-01T23:47:40Z  
Participant: `P001`  
Writer: OFF (`CONTROLLED_WRITER_ENABLED=false`)

## Sessions

| Domain | Count |
|--------|------:|
| EC-SW | 3 |
| General Report | 3 |
| Business Proposal | 3 |
| **Total** | **9** |

## Completion

- PASS: 8
- PARTIAL: 1
- FAIL: 0
- Session Completion Rate: 1.0

## Accuracy

- Human Document Agreement: 0.889
- Human Node Agreement: 0.889
- Proposal Acceptance Rate: 0.222
- Review Agreement Rate: 1.0

## Usability

- Mean Trust: 3.778
- Mean Usability: 4.0

| Dimension | Mean |
|-----------|-----:|
| understanding | 5.0 |
| document_impact | 4.667 |
| node_accuracy | 4.667 |
| proposal_accuracy | 3.111 |
| review_reason | 3.889 |
| diff_readability | 3.889 |
| no_unnecessary_change | 5.0 |
| format_preservation | 5.0 |
| trust | 3.778 |
| usability | 4.0 |

## Timing

- Mean: 1957.0 ms
- Median: 1825.0 ms
- Max: 2729.0 ms
- Reanalysis Request Rate: 0.0

## Safety

- Original changed: 0
- Unauthorized writer: 0
- Wrong document: 0
- Wrong node write: 0
- Path escape: 0
- Auto approve: 0
- Status: **PASS**

## Errors / Bug Candidates

- Total: 1
- Critical: 0
- Major: 1
- Minor: 0
- Most frequent: empty_or_weak_node_candidates

See `bug_candidates.jsonl` under `data/pilot/real_runs/pilot_run_01/`.

## Constraints

- Engine / Domain Pack / Ranking / Benchmark / Gold: **not modified**
- Writer capability: **not expanded**
- Issues found: recorded as bug candidates only

## Session index

- `pilot_ec_req_single_P001_20260801T234722148675` · ec_sw · pilot_ec_req_single · PASS · trust=4
- `pilot_ec_design_review_P001_20260801T234724300820` · ec_sw · pilot_ec_design_review · PASS · trust=4
- `pilot_ec_semantic_P001_20260801T234726405728` · ec_sw · pilot_ec_semantic · PARTIAL · trust=2
- `pilot_gr_methodology_P001_20260801T234728293004` · general_report · pilot_gr_methodology · PASS · trust=4
- `pilot_gr_schedule_table_P001_20260801T234730054519` · general_report · pilot_gr_schedule_table · PASS · trust=4
- `pilot_gr_conclusion_P001_20260801T234731766032` · general_report · pilot_gr_conclusion · PASS · trust=4
- `pilot_bp_budget_P001_20260801T234733594109` · business_proposal · pilot_bp_budget · PASS · trust=4
- `pilot_bp_schedule_P001_20260801T234736340403` · business_proposal · pilot_bp_schedule · PASS · trust=4
- `pilot_bp_risk_P001_20260801T234738596194` · business_proposal · pilot_bp_risk · PASS · trust=4
