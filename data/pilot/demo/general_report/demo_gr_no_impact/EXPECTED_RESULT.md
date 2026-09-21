# Expected Result

- Domain: `general_report`
- Scenario: `pilot_gr_no_impact`
- Talk track: 표지 색상처럼 본문과 무관한 요청의 대조 케이스.
- Writer hint: `False`
- Failure / special: `no_impact, false_positive_write`

Expected user path:
1. Upload document copy
2. Confirm identity / domain pack
3. Analyze change request
4. Review candidates (APPROVE / REJECT / HOLD)
5. Optional gated copy-only writer
6. Diff / validation / download / human review
