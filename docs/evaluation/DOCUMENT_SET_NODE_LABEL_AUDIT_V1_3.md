# Document Set Node Label Audit v1.3

**Scope:** 24 Document Set Benchmark cases  
**Method:** Rule-based fixture / change-request interpretation (not prediction-driven)  
**Automatic gold mutation:** **0**

## Mode distribution

| Mode | Count | Policy |
|------|------:|--------|
| REQUIRED | 13 | Strict node metrics denominator |
| OPTIONAL | 2 | Document REVIEW OK; no strict Top-1 |
| AMBIGUOUS | 2 | Acceptable groups required |
| NOT_APPLICABLE | 7 | Excluded from node retrieval |
| UNLABELED | 0 | Official v1.3 target |

## Audit rules (human-interpretable)

| Pattern | Mode | Rationale |
|---------|------|-----------|
| Exact Req / Design / Test ID → MDTM row | REQUIRED | Concrete TABLE_ROW grounding |
| Multi-doc MDTM Req | REQUIRED | Same |
| Writer-gated exact Req | REQUIRED | Node still required; write gated |
| Semantic-only (no Req ID; sparse MDTM text) | OPTIONAL | Document REVIEW; no unique row gold |
| Schedule / duplicate heading | AMBIGUOUS | Section alternatives from fixture+template |
| No-impact / malformed / missing section / empty context | NOT_APPLICABLE | Document-level only |

## Label issues

Expected after eligibility generation:

- `LABEL_COMPLETE` for nearly all cases
- `UNLABELED` = 0
- `NODE_GOLD_MISSING` on REQUIRED = 0
- Predictions with candidates but empty gold on OPTIONAL cases are **diagnostics only** (`prediction_seen_but_ignored_for_gold`) — do not invent row gold

## Proposed changes (not auto-applied)

See `data/eval/document_set_benchmark/proposed_label_changes.json`:

1. `gr_schedule_table` — add AMBIGUOUS gold `general_report_v1.schedule` from fixture 일정 heading + template schedule section  
2. `ec_sw_semantic_only` — OPTIONAL, **no** invented MDTM row gold  

Both `from_prediction: false`.

## Artifacts

- `labels/node_evaluation_eligibility.jsonl`
- `labels/node_impacts.jsonl` (enriched metadata; AMBIGUOUS gold added where fixture-justified)
- `proposed_label_changes.json`
- Per-run: `node_label_audit.json`, stamped `node_label_audit_<timestamp>.json` under results

## Non-goals

- Do not raise Node Recall by widening candidates unbounded  
- Do not mark OPTIONAL as REQUIRED because a model emitted a node  
- Do not case-id-special-case product inference code  
