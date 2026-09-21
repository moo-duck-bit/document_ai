# Expected Result

- Domain: `business_proposal`
- Scenario: `pilot_bp_no_impact`
- Talk track: 셀 단위 고위험 변경은 자동 승인 없이 REVIEW/차단을 강조한다.
- Writer hint: `False`
- Failure / special: `no_impact, auto_write_labor_cell, benchmark_case_hardcoding`

Expected user path:
1. Upload document copy
2. Confirm identity / domain pack
3. Analyze change request
4. Review candidates (APPROVE / REJECT / HOLD)
5. Optional gated copy-only writer
6. Diff / validation / download / human review
