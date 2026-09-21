# Expected Result

- Domain: `business_proposal`
- Scenario: `pilot_bp_budget`
- Talk track: 예산 표·인건비 항목을 찾아 승인 후 복사본을 만든다.
- Writer hint: `True`
- Failure / special: `wrong_table, original_modified`

Expected user path:
1. Upload document copy
2. Confirm identity / domain pack
3. Analyze change request
4. Review candidates (APPROVE / REJECT / HOLD)
5. Optional gated copy-only writer
6. Diff / validation / download / human review
