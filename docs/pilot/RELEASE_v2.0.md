# Document AI v2.0 — Pilot Release Notes

Status: **READY_FOR_PILOT_RELEASE**

## 주요 기능

- Generic template / semantic·structural locator / patch targeting
- Physical locator + Patch Contract + Controlled Writer (copy-only, gated)
- Approval · Diff · Rollback · Validation
- Document Identity + Auto / Assisted Domain Pack routing
- Domain packs: **EC-SW**, **General Report**, **Business Proposal**
- Real User Pilot UI (`/pilot-v2`) + Human Review (10 dimensions)
- Demo dataset + flagship demo runner (`run-pilot-demo`)

## 지원 문서

| Domain | Typical docs | Pilot samples |
|--------|--------------|---------------|
| EC-SW | MDSR / MDDR / MDTM-style tables | `data/pilot/demo/ec_sw/` |
| General Report | 연구·기술·중간 보고서 | `data/pilot/demo/general_report/` |
| Business Proposal | 사업·수행·연구개발 계획서 | `data/pilot/demo/business_proposal/` |

## 지원 Workflow

Upload → Identity/Routing → Change Request → Analysis → Review (승인/거절/보류) → Gated Writer → Result / Download → Human Review

## 제한 사항

- No new Domain Pack / ranking / LLM / remote embedding in this release package
- Writer does **not** apply free-form textual patches in the Pilot MVP path; gated **byte copy** of approved inputs into session `output/copies/`
- XXCS Excel/CSV bulk remains v2 roadmap (not this Pilot package)
- Participant live metrics fill after real sessions (`evaluate-pilot`)

## Known Issues

- Business Proposal labor-cell style cases may surface empty candidates / SAFE_FAILURE (deferred; no holdout tuning in Pilot finalization)
- Assisted routing may require explicit **추천대로 확정**
- Change request text is captured at session create; large edits need a new session

## Benchmark (immutable reference)

| Metric | Value |
|--------|-------|
| Holdout Document F1 | 0.956 |
| Holdout E2E | 0.957 |
| False Patch | 0 |
| Unsafe Failure | 0 |
| Original Preservation | 1.000 |

## 향후 계획

1. Live participant Pilot runs + filled evaluation report  
2. MDVP 연동 검토  
3. Writer textual apply (capability-scoped, still approval-gated)  
4. Optional Knowledge Graph / LLM free_text (out of Pilot scope)

## How to run

See [REAL_USER_PILOT_GUIDE.md](./REAL_USER_PILOT_GUIDE.md).
