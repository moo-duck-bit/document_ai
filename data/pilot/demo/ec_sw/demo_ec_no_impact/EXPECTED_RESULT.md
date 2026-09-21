# Expected Result

- Domain: `ec_sw`
- Scenario: `pilot_ec_no_impact`
- Talk track: 문서와 무관한 요청은 영향이 없거나 Writer가 막혀야 한다.
- Writer hint: `False`
- Failure / special: `no_impact, false_positive_write`

Expected user path:
1. Upload document copy
2. Confirm identity / domain pack
3. Analyze change request
4. Review candidates (APPROVE / REJECT / HOLD)
5. Optional gated copy-only writer
6. Diff / validation / download / human review
