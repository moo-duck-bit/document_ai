# B3 Impact Judgment

- created_at: `2026-07-22T21:51:30Z`
- patch: not executed
- expected_impact_used_in_judgment: `false`

Summary: {'IMPACTED': 6, 'NOT_IMPACTED': 9, 'UNCERTAIN': 0}

| ID | Doc | Judgment | Rank | Reason (short) |
|----|-----|----------|-----:|----------------|
| Req. 105 | MDDR | **IMPACTED** | 1 | CR lockout policy aligns with block lock/limit cues (shared=['계정 잠금', '로그인 실패', '연속', '잠금'], lock_po |
| Req. 103 | MDSR | **IMPACTED** | 2 | CR requires audit of lock/unlock events; block is audit-primary ('감사 기록 생성 및 관리') covering login aut |
| Req. 103 | MDDR | **IMPACTED** | 3 | CR requires audit of lock/unlock events; block is audit-primary ('감사 기록 생성 및 관리') covering login aut |
| Req. 101 | MDSR | **NOT_IMPACTED** | 4 | Access-control-primary block ('권한에 따른 API 접근 통제') with incidental auth/audit overlap ['감사', '감사 기록', |
| Req. 6 | MDSR | **IMPACTED** | 5 | CR lockout policy aligns with block lock/limit cues (shared=['로그인 실패'], lock_policy=True); lex=0.316 |
| Req. 110 | MDSR | **NOT_IMPACTED** | 6 | Only generic auth/audit/UX overlap ['감사', '감사 기록', '사용자'] without lockout-policy cues in the block;  |
| Req. 102 | MDDR | **NOT_IMPACTED** | 7 | Only generic auth/audit/UX overlap ['감사', '감사 기록', '로그', '로그인', '사용자'] without lockout-policy cues i |
| Req. 105 | MDSR | **IMPACTED** | 8 | CR lockout policy aligns with block lock/limit cues (shared=[], lock_policy=True); lex=0.197 sem=0.1 |
| Req. 2 | MDSR | **NOT_IMPACTED** | 9 | Only generic auth/audit/UX overlap ['감사', '로그', '사용자', '안내'] without lockout-policy cues in the bloc |
| Req. 102 | MDSR | **NOT_IMPACTED** | 10 | Only generic auth/audit/UX overlap ['로그', '로그인', '사용자', '안내'] without lockout-policy cues in the blo |
| Req. 101 | MDDR | **NOT_IMPACTED** | 11 | Access-control-primary block ('권한에 따른 API 접근 통제') with incidental auth/audit overlap ['감사', '감사 기록', |
| Req. 100 | MDSR | **NOT_IMPACTED** | 12 | Only generic auth/audit/UX overlap ['감사', '감사 기록'] without lockout-policy cues in the block; lex=0.2 |
| Req. 6 | MDDR | **IMPACTED** | 13 | CR lockout policy aligns with block lock/limit cues (shared=['로그인 실패'], lock_policy=True); lex=0.150 |
| Req. 2 | MDDR | **NOT_IMPACTED** | 14 | Only generic auth/audit/UX overlap ['감사', '로그', '사용자', '안내', '알림'] without lockout-policy cues in th |
| Req. 206 | MDSR | **NOT_IMPACTED** | 15 | Only generic auth/audit/UX overlap ['로그', '로그인', '사용자'] without lockout-policy cues in the block; le |
