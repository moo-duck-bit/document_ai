# Before vs After — Scenario-001 B3v2 Rerun

| Metric / Behavior | Frozen Baseline | B3v2 Rerun |
|---|---|---|
| Overall result | PARTIAL | PARTIAL |
| Retrieval Top-1 | (1, 'Req. 203', 'MDSR', 1.0) | (1, 'Req. 203', 'MDSR', 1.0) |
| Retrieval identical order/scores | — | `True` |
| IMPACTED count | 0 | 6 |
| UNCERTAIN count | 7 | 1 |
| NOT_IMPACTED count | 8 | 8 |
| Change types | (none / legacy) | `{'EXTEND_EXISTING': 6, 'NOT_RELATED': 8, 'NEW_REQUIREMENT_CANDIDATE': 1}` |
| NEW_REQUIREMENT flag | `True` | `False` |
| NEW_REQUIREMENT proposal file | false (flag only) | `False` |
| B4 CONSISTENT | 0 | 0 |
| B4 CONFLICT | 0 | 0 |
| B4 NEEDS_REVIEW | 0 | 4 |
| B5 PATCHED | 0 | 0 |
| MDSR patched IDs | `[]` | `[]` |
| MDDR patched IDs | `[]` | `[]` |
| Human review needed | yes | yes |

## Candidate-level judgment changes

| ID | Doc | Rank | Baseline | B3v2 | change_type | concepts (sample) |
|----|-----|-----:|----------|------|-------------|-------------------|
| Req. 203 | MDSR | 1 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING | 쉽게, 의료진이, 환자를, 환자의 |
| Req. 204 | MDSR | 2 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING | 의료진이, 최근, 환자의 |
| Req. 100 | MDSR | 3 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING | 대시보드에서, 의료진이, 해당, 환자를 |
| Req. 11 | MDDR | 4 | UNCERTAIN | **NOT_IMPACTED** | NOT_RELATED | 상태는 |
| Req. 17 | MDDR | 5 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING | 기록을_기준으로 |
| Req. 204 | MDDR | 6 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING | 해당, 환자를, 환자의 |
| Req. 110 | MDSR | 7 | NOT_IMPACTED | **IMPACTED** | EXTEND_EXISTING | 기록을, 대시보드에서 |
| Req. 108 | MDSR | 8 | UNCERTAIN | **NOT_IMPACTED** | NOT_RELATED | 과제 |
| Req. 16 | MDDR | 9 | NOT_IMPACTED | **NOT_IMPACTED** | NOT_RELATED | 기록을, 동안 |
| Req. 17 | MDSR | 10 | NOT_IMPACTED | **NOT_IMPACTED** | NOT_RELATED | 기준으로 |
| Req. 12 | MDSR | 11 | NOT_IMPACTED | **NOT_IMPACTED** | NOT_RELATED | 비활성, 자동 |
| Req. 12 | MDDR | 12 | NOT_IMPACTED | **NOT_IMPACTED** | NOT_RELATED | 비활성, 자동 |
| Req. 18 | MDDR | 13 | NOT_IMPACTED | **NOT_IMPACTED** | NOT_RELATED | 기준으로 |
| Req. 2 | MDSR | 14 | NOT_IMPACTED | **UNCERTAIN** | NEW_REQUIREMENT_CANDIDATE | 식별할, 해당 |
| Req. 3 | MDDR | 15 | NOT_IMPACTED | **NOT_IMPACTED** | NOT_RELATED | 과제, 해당 |

## Answers to comparison questions

1. Retrieval changed? **No** (identical rank/id/doc/hybrid: `True`).
2. B3 judgments changed? **Yes** — IMPACTED rose from 0→6; UNCERTAIN 7→1.
3. Why? Domain-independent evidence gates replaced lockout-theme-only IMPACTED paths.
4. Evidence supports? See per-candidate matched_concepts / behavioral_overlap in impact_judgments.json.
5. False positives? Suspects with empty evidence: `none by empty-evidence check` — still review IMPACTED set vs CR (inactive-patient) for over-broad IMPACTED.
6. Zero-IMPACTED fallback? IMPACTED=6 so proposal emit expected false; actual file exists=`False` (must be false when IMPACTED>0).
7. Downstream bottleneck? **Yes — B4**: IMPACTED MDSR → NEEDS_REVIEW (0 CONSISTENT) → B5 NEEDS_REVIEW / no PATCHED. Lockout-shaped consistency gate is the next bottleneck.

B3 path classification: `PATH_A_partial_or_full`

