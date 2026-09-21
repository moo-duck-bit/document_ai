# Expected Result

- Domain: `ec_sw`
- Scenario: `pilot_ec_semantic`
- Talk track: ID 없이 정책 문구만 있을 때 REVIEW가 뜨는 흐름을 보여준다.
- Writer hint: `False`
- Failure / special: `semantic_only, auto_write_without_approval`

Expected user path:
1. Upload document copy
2. Confirm identity / domain pack
3. Analyze change request
4. Review candidates (APPROVE / REJECT / HOLD)
5. Optional gated copy-only writer
6. Diff / validation / download / human review
