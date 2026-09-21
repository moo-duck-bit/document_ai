# Real User Document Pilot v2 — Report (Product Validation Cycle 1)

> Template. Fill in the placeholders (`{{ ... }}`) after running
> `python -m document_ai.cli evaluate-pilot --json` against real participant
> sessions and copying values from the produced
> `data/pilot/real_user_document_pilot/runs/pilot_run_<timestamp>.json`.
> Do not hand-edit numbers — always regenerate from the aggregation CLI so the
> report stays traceable to a specific `run_id`.

## 0. Summary

| Field | Value |
|---|---|
| Run ID | `{{ run_id }}` |
| Generated at (UTC) | `{{ generated_at }}` |
| Sessions included | `{{ n_sessions }}` |
| **Verdict** | `{{ verdict }}` |
| Verdict reasons | `{{ verdict_reasons }}` |

Target verdict for this cycle: **`READY_FOR_REAL_USER_DOCUMENT_PILOT`**.
Possible verdicts: `READY_FOR_REAL_USER_DOCUMENT_PILOT`,
`NOT_READY_SAFETY`, `NOT_READY_COMPLETION`, `INSUFFICIENT_DATA`
(see `src/document_ai/pilot_v2/evaluate_run.py::determine_verdict`).

### Platform readiness (engineering gate — Cycle 1)

| Gate | Status |
|------|--------|
| Pilot session schema + 12 scenarios | ✅ |
| `/pilot-v2` UI + `/api/pilot-v2/*` | ✅ |
| CLI `run-pilot-session` / `evaluate-pilot` | ✅ |
| Explicit approval + copy-only writer gates | ✅ |
| Human review capture | ✅ |
| Security (path escape, no-approval write) | ✅ |
| Pilot tests (≥55) | ✅ 187 passed |
| Benchmark tuning this cycle | ❌ not done (by design) |

Participant live-run metrics below remain placeholders until real users complete sessions.

## 1. Scope

- Participants: `{{ n_participants }}` anonymous participants
  (`P001`..`P{{ n_participants:03d }}`)
- Scenarios exercised: `{{ scenario_ids_covered }}` / 12
- Domains covered: EC-SW / General Report / Business Proposal
  (`{{ domains_covered }}`)
- Date range: `{{ date_range }}`

## 2. Completion scorecard

| Metric | Value |
|---|---|
| n_sessions | `{{ completion.n_sessions }}` |
| analysis_completion_rate | `{{ completion.analysis_completion_rate }}` |
| review_reached_rate | `{{ completion.review_reached_rate }}` |
| session_completion_rate | `{{ completion.session_completion_rate }}` |
| failure_rate | `{{ completion.failure_rate }}` |
| review_fully_decided_rate | `{{ completion.review_fully_decided_rate }}` |

`session_completion_rate` must be **≥ 0.5** for the `READY_FOR_REAL_USER_DOCUMENT_PILOT`
verdict to be reachable (see `determine_verdict`).

## 3. Accuracy scorecard (from review decisions + human review)

| Metric | Value |
|---|---|
| n_review_items | `{{ accuracy.n_review_items }}` |
| approval_rate | `{{ accuracy.approval_rate }}` |
| rejection_rate | `{{ accuracy.rejection_rate }}` |
| hold_rate | `{{ accuracy.hold_rate }}` |
| edit_proposal_rate | `{{ accuracy.edit_proposal_rate }}` |
| n_sessions_with_human_review | `{{ accuracy.n_sessions_with_human_review }}` |
| human_verdict_pass_rate | `{{ accuracy.human_verdict_pass_rate }}` |
| human_verdict_distribution | `{{ accuracy.human_verdict_distribution }}` |

## 4. Writer scorecard (copy-only, gated)

| Metric | Value |
|---|---|
| n_writer_attempts | `{{ writer.n_writer_attempts }}` |
| written_copy_rate | `{{ writer.written_copy_rate }}` |
| blocked_rate | `{{ writer.blocked_rate }}` |
| original_preservation_rate | `{{ writer.original_preservation_rate }}` |
| format_structure_preservation_rate | `{{ writer.format_structure_preservation_rate }}` (N/A if writer never ran) |
| blocked_reason_counts | `{{ writer.blocked_reason_counts }}` |

`original_preservation_rate` must be **1.0** (100%) whenever `n_writer_attempts > 0`;
anything less is a release blocker regardless of other metrics.

## 5. Usability scorecard (1–5 human review scores)

| Dimension | Average |
|---|---|
| understanding | `{{ usability.avg_understanding }}` |
| document_impact | `{{ usability.avg_document_impact }}` |
| node_accuracy | `{{ usability.avg_node_accuracy }}` |
| proposal_accuracy | `{{ usability.avg_proposal_accuracy }}` |
| review_reason | `{{ usability.avg_review_reason }}` |
| diff_readability | `{{ usability.avg_diff_readability }}` |
| no_unnecessary_change | `{{ usability.avg_no_unnecessary_change }}` |
| format_preservation | `{{ usability.avg_format_preservation }}` |
| review_reason_plausibility | `{{ usability.avg_review_reason_plausibility }}` |
| trust | `{{ usability.avg_trust }}` |
| usability | `{{ usability.avg_usability }}` |
| **Overall average** | `{{ usability.overall_average_score }}` |

n_responses: `{{ usability.n_responses }}`

## 6. Safety scorecard (hard gate)

| Metric | Value |
|---|---|
| original_changed_count | `{{ safety.original_changed_count }}` |
| unauthorized_write_count | `{{ safety.unauthorized_write_count }}` |
| write_without_approval_count | `{{ safety.write_without_approval_count }}` |
| path_security_violation_count | `{{ safety.path_security_violation_count }}` |
| **safety_status** | `{{ safety.safety_status }}` |

All four counts must be **0** for `safety_status == "PASS"`. Any non-zero
count forces the overall verdict to `NOT_READY_SAFETY` regardless of
completion/usability numbers.

## 7. Qualitative notes

- Common blocked-writer reasons observed: `{{ notes_blocked_reasons }}`
- Participant feedback highlights: `{{ notes_feedback }}`
- Scenarios with the most `REJECT`/`HOLD` decisions: `{{ notes_low_confidence_scenarios }}`
- Known limitations for this cycle: `{{ notes_limitations }}`

## 8. Recommendation

`{{ recommendation_text }}`

---

Generated from `run_id = {{ run_id }}`. Regenerate this section whenever a new
`evaluate-pilot` run supersedes it; do not average across multiple `run_id`s
without noting it explicitly.
