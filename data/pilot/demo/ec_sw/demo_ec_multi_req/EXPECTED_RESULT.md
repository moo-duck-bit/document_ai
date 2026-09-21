# Expected Result

- Domain: `ec_sw`
- Scenario: `pilot_ec_design_review`
- Talk track: 여러 요구사항 ID가 함께 언급될 때 후보를 나란히 검토한다.
- Writer hint: `True`
- Failure / special: `only_one_req_updated_silently, original_modified`

Expected user path:
1. Upload document copy
2. Confirm identity / domain pack
3. Analyze change request
4. Review candidates (APPROVE / REJECT / HOLD)
5. Optional gated copy-only writer
6. Diff / validation / download / human review
